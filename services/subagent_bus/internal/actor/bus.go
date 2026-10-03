package actor

import (
	"context"
	"fmt"
	"strings"
	"sync"
	"time"
)

// SubagentBus is the centralized actor registry and scheduling bus.
type SubagentBus struct {
	mu     sync.RWMutex
	actors map[string]*SubagentActor
	ctx    context.Context
	cancel context.CancelFunc
}

// NewSubagentBus creates and initializes a new SubagentBus.
func NewSubagentBus(parentCtx context.Context) *SubagentBus {
	ctx, cancel := context.WithCancel(parentCtx)
	return &SubagentBus{
		actors: make(map[string]*SubagentActor),
		ctx:    ctx,
		cancel: cancel,
	}
}

// Spawn registers and optionally starts a new subagent actor.
func (b *SubagentBus) Spawn(spec TaskSpec) (*SubagentActor, error) {
	b.mu.Lock()
	defer b.mu.Unlock()

	if spec.ID == "" {
		spec.ID = fmt.Sprintf("subagent_%d_%x", time.Now().UnixNano(), time.Now().Unix()%10000)
	}
	if spec.Name == "" {
		spec.Name = spec.ID
	}
	if spec.Role == "" {
		spec.Role = "worker"
	}

	if _, exists := b.actors[spec.ID]; exists {
		return nil, fmt.Errorf("actor with ID %s already exists", spec.ID)
	}

	act := NewSubagentActor(b.ctx, spec)
	b.actors[spec.ID] = act

	if spec.AutoStart {
		if err := act.Start(); err != nil {
			delete(b.actors, spec.ID)
			return nil, fmt.Errorf("failed to auto-start actor %s: %w", spec.ID, err)
		}
	}

	return act, nil
}

// Get retrieves an actor by ID.
func (b *SubagentBus) Get(id string) (*SubagentActor, bool) {
	b.mu.RLock()
	defer b.mu.RUnlock()
	act, ok := b.actors[id]
	return act, ok
}

// Send routes a message directly to target actor's mailbox.
func (b *SubagentBus) Send(subagentID string, msg SubagentMessage) error {
	b.mu.RLock()
	act, ok := b.actors[subagentID]
	b.mu.RUnlock()

	if !ok {
		return fmt.Errorf("actor with ID %s not found", subagentID)
	}
	return act.Send(msg)
}

// Broadcast sends a message to all active actors matching optional roleFilter.
// Returns count of delivered messages.
func (b *SubagentBus) Broadcast(sender string, msgType MessageType, payload map[string]any, roleFilter string) int {
	b.mu.RLock()
	// Snapshot list of matching actors to avoid holding lock during send
	var targets []*SubagentActor
	for _, a := range b.actors {
		st := a.Status()
		spec := a.Spec()
		if st == StatusRunning && (roleFilter == "" || strings.EqualFold(spec.Role, roleFilter)) {
			targets = append(targets, a)
		}
	}
	b.mu.RUnlock()

	count := 0
	for _, a := range targets {
		msg := SubagentMessage{
			ID:        fmt.Sprintf("msg_%d_%s", time.Now().UnixNano(), a.Spec().ID),
			Type:      msgType,
			Sender:    sender,
			Timestamp: time.Now(),
			Payload:   payload,
		}
		if err := a.Send(msg); err == nil {
			count++
		}
	}
	return count
}

// Cancel terminates a specified actor.
func (b *SubagentBus) Cancel(id string, reason string) error {
	b.mu.RLock()
	act, ok := b.actors[id]
	b.mu.RUnlock()

	if !ok {
		return fmt.Errorf("actor with ID %s not found", id)
	}
	act.Cancel(reason)
	return nil
}

// List returns actors matching status and role filters.
func (b *SubagentBus) List(statusFilter string, roleFilter string) []*SubagentActor {
	b.mu.RLock()
	defer b.mu.RUnlock()

	var res []*SubagentActor
	for _, a := range b.actors {
		st := string(a.Status())
		role := a.Spec().Role

		statusMatch := statusFilter == "" || statusFilter == "all" || strings.EqualFold(st, statusFilter)
		if statusFilter == "active" {
			statusMatch = (st == string(StatusRunning) || st == string(StatusCreated))
		} else if statusFilter == "completed" {
			statusMatch = (st == string(StatusCompleted))
		} else if statusFilter == "failed" {
			statusMatch = (st == string(StatusFailed) || st == string(StatusCancelled))
		}

		roleMatch := roleFilter == "" || strings.EqualFold(role, roleFilter)

		if statusMatch && roleMatch {
			res = append(res, a)
		}
	}
	return res
}

// Reap removes terminated actors (COMPLETED, FAILED, CANCELLED) older than maxAgeSec.
// If maxAgeSec <= 0, all terminated actors are removed immediately.
// Returns number of reaped actors.
func (b *SubagentBus) Reap(maxAgeSec int) int {
	b.mu.Lock()
	defer b.mu.Unlock()

	reaped := 0
	now := time.Now()
	for id, a := range b.actors {
		st := a.Status()
		if st == StatusCompleted || st == StatusFailed || st == StatusCancelled {
			shouldReap := true
			if maxAgeSec > 0 {
				a.mu.RLock()
				endTime := a.endTime
				a.mu.RUnlock()
				if !endTime.IsZero() && now.Sub(endTime) < time.Duration(maxAgeSec)*time.Second {
					shouldReap = false
				}
			}
			if shouldReap {
				delete(b.actors, id)
				reaped++
			}
		}
	}
	return reaped
}

// Count returns total number of registered actors.
func (b *SubagentBus) Count() int {
	b.mu.RLock()
	defer b.mu.RUnlock()
	return len(b.actors)
}

// Close cancels all actors and shuts down the bus context.
func (b *SubagentBus) Close() {
	b.cancel()
	b.mu.RLock()
	for _, a := range b.actors {
		a.Cancel("bus shutdown")
	}
	b.mu.RUnlock()
}
