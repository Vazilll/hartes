package actor

import (
	"context"
	"fmt"
	"sync"
	"sync/atomic"
	"time"
)

// SubagentActor is a concurrent actor executing in its own goroutine with a bounded inbox.
type SubagentActor struct {
	spec              TaskSpec
	status            ActorStatus
	mu                sync.RWMutex
	inbox             chan SubagentMessage
	ctx               context.Context
	cancel            context.CancelFunc
	events            *RingBuffer
	seqCounter        atomic.Int64
	messagesProcessed atomic.Int64
	startTime         time.Time
	endTime           time.Time
	err               error
	results           map[string]any
	done              chan struct{}
}

// NewSubagentActor constructs a new actor in CREATED state.
func NewSubagentActor(parentCtx context.Context, spec TaskSpec) *SubagentActor {
	if spec.MailboxCap <= 0 {
		spec.MailboxCap = 256
	}
	if spec.TimeoutSec <= 0 {
		spec.TimeoutSec = 300
	}

	ctx, cancel := context.WithTimeout(parentCtx, time.Duration(spec.TimeoutSec)*time.Second)

	return &SubagentActor{
		spec:      spec,
		status:    StatusCreated,
		inbox:     make(chan SubagentMessage, spec.MailboxCap),
		ctx:       ctx,
		cancel:    cancel,
		events:    NewRingBuffer(512),
		startTime: time.Now(),
		results:   make(map[string]any),
		done:      make(chan struct{}),
	}
}

// Start transitions actor state from CREATED to RUNNING and launches loop goroutine.
func (a *SubagentActor) Start() error {
	a.mu.Lock()
	if a.status != StatusCreated {
		st := a.status
		a.mu.Unlock()
		return fmt.Errorf("actor already started (status=%s)", st)
	}
	a.status = StatusRunning
	a.startTime = time.Now()
	a.mu.Unlock()

	a.Emit(EventState, "Actor started in running state", map[string]any{
		"role":    a.spec.Role,
		"timeout": a.spec.TimeoutSec,
	})

	go a.loop()
	return nil
}

// loop is the internal actor event loop running in its dedicated goroutine.
func (a *SubagentActor) loop() {
	defer func() {
		if r := recover(); r != nil {
			a.mu.Lock()
			a.status = StatusFailed
			a.err = fmt.Errorf("panic in actor loop: %v", r)
			a.endTime = time.Now()
			a.mu.Unlock()
			a.Emit(EventError, fmt.Sprintf("Panic caught in actor loop: %v", r), nil)
		}
		a.cancel()
		close(a.done)
	}()

	for {
		select {
		case <-a.ctx.Done():
			a.mu.Lock()
			if a.status == StatusRunning || a.status == StatusPaused {
				if a.ctx.Err() == context.DeadlineExceeded {
					a.status = StatusFailed
					a.err = fmt.Errorf("execution timed out after %d seconds", a.spec.TimeoutSec)
					a.Emit(EventError, "Execution timed out", nil)
				} else {
					a.status = StatusCancelled
					a.Emit(EventState, "Actor context cancelled", nil)
				}
				a.endTime = time.Now()
			}
			a.mu.Unlock()
			return

		case msg, ok := <-a.inbox:
			if !ok {
				return
			}
			a.processMessage(msg)
		}
	}
}

// processMessage handles an incoming SubagentMessage.
func (a *SubagentActor) processMessage(msg SubagentMessage) {
	a.messagesProcessed.Add(1)

	switch msg.Type {
	case MsgShutdown:
		a.mu.Lock()
		a.status = StatusCompleted
		a.endTime = time.Now()
		a.mu.Unlock()
		a.Emit(EventState, "Actor received shutdown signal and completed cleanly", map[string]any{
			"sender": msg.Sender,
		})
		a.cancel()

	case MsgHeartbeat:
		a.Emit(EventLog, "Heartbeat acknowledged", map[string]any{
			"sender": msg.Sender,
		})

	case MsgInstruction:
		content := msg.Content
		if content == "" && msg.Payload != nil {
			if text, ok := msg.Payload["content"].(string); ok {
				content = text
			}
		}
		a.Emit(EventLog, fmt.Sprintf("Instruction received from %s: %s", msg.Sender, content), msg.Payload)
		a.Emit(EventProgress, "Executing instruction", map[string]any{
			"step": "executing",
		})
		a.Emit(EventOutput, fmt.Sprintf("Result for instruction: %s", content), map[string]any{
			"processed": true,
		})

	case MsgFeedback:
		a.Emit(EventLog, fmt.Sprintf("Feedback received from %s", msg.Sender), msg.Payload)

	case MsgToolResult:
		a.mu.Lock()
		if a.results == nil {
			a.results = make(map[string]any)
		}
		a.results[msg.ID] = msg.Payload
		a.mu.Unlock()
		a.Emit(EventOutput, "Tool result recorded", msg.Payload)

	default:
		a.Emit(EventLog, fmt.Sprintf("Message received (%s) from %s", msg.Type, msg.Sender), msg.Payload)
	}
}

// Send attempts to deliver a message to the actor's buffered inbox channel.
// Returns an error if the actor is not RUNNING/PAUSED or if the inbox is full (backpressure).
func (a *SubagentActor) Send(msg SubagentMessage) error {
	a.mu.RLock()
	st := a.status
	a.mu.RUnlock()

	if st != StatusRunning && st != StatusPaused {
		return fmt.Errorf("cannot send to actor %s in status %s", a.spec.ID, st)
	}

	select {
	case a.inbox <- msg:
		return nil
	default:
		return fmt.Errorf("mailbox full for actor %s (cap=%d)", a.spec.ID, cap(a.inbox))
	}
}

// Cancel terminates the actor immediately.
func (a *SubagentActor) Cancel(reason string) {
	a.mu.Lock()
	if a.status == StatusRunning || a.status == StatusPaused || a.status == StatusCreated {
		a.status = StatusCancelled
		a.endTime = time.Now()
		if reason == "" {
			reason = "manual cancellation"
		}
		a.Emit(EventState, "Actor cancelled: "+reason, map[string]any{"reason": reason})
	}
	a.mu.Unlock()
	a.cancel()
}

// Emit records a new event into the actor's ring buffer with an incrementing sequence number.
func (a *SubagentActor) Emit(evtType EventType, content string, meta map[string]any) {
	seq := a.seqCounter.Add(1)
	evt := SubagentEvent{
		Seq:       seq,
		Timestamp: time.Now(),
		Type:      evtType,
		Content:   content,
		Metadata:  meta,
	}
	a.events.Push(evt)
}

// Status returns current actor status.
func (a *SubagentActor) Status() ActorStatus {
	a.mu.RLock()
	defer a.mu.RUnlock()
	return a.status
}

// Spec returns the actor's task specification.
func (a *SubagentActor) Spec() TaskSpec {
	return a.spec
}

// Events returns the ring buffer reference.
func (a *SubagentActor) Events() *RingBuffer {
	return a.events
}

// InboxDepth returns current number of queued messages in mailbox.
func (a *SubagentActor) InboxDepth() int {
	return len(a.inbox)
}

// InboxCap returns capacity of mailbox.
func (a *SubagentActor) InboxCap() int {
	return cap(a.inbox)
}

// MessagesProcessed returns total number of messages processed.
func (a *SubagentActor) MessagesProcessed() int64 {
	return a.messagesProcessed.Load()
}

// UptimeMs returns execution uptime in milliseconds.
func (a *SubagentActor) UptimeMs() int64 {
	a.mu.RLock()
	defer a.mu.RUnlock()

	if a.startTime.IsZero() {
		return 0
	}
	if !a.endTime.IsZero() {
		return a.endTime.Sub(a.startTime).Milliseconds()
	}
	return time.Since(a.startTime).Milliseconds()
}

// Error returns error if actor failed.
func (a *SubagentActor) Error() error {
	a.mu.RLock()
	defer a.mu.RUnlock()
	return a.err
}

// ToMap returns summary telemetry map for MCP serialization.
func (a *SubagentActor) ToMap() map[string]any {
	a.mu.RLock()
	defer a.mu.RUnlock()

	var errMsg *string
	if a.err != nil {
		s := a.err.Error()
		errMsg = &s
	}

	uptime := int64(0)
	if !a.startTime.IsZero() {
		if !a.endTime.IsZero() {
			uptime = a.endTime.Sub(a.startTime).Milliseconds()
		} else {
			uptime = time.Since(a.startTime).Milliseconds()
		}
	}

	return map[string]any{
		"id":                 a.spec.ID,
		"name":               a.spec.Name,
		"role":               a.spec.Role,
		"status":             string(a.status),
		"inbox_depth":        len(a.inbox),
		"inbox_cap":          cap(a.inbox),
		"messages_processed": a.messagesProcessed.Load(),
		"events_count":       a.events.Len(),
		"uptime_ms":          uptime,
		"created_at":         a.startTime.Format(time.RFC3339),
		"error":              errMsg,
	}
}
