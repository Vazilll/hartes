package actor

import (
	"context"
	"fmt"
	"sync"
	"testing"
	"time"
)

func TestActorLifecycle(t *testing.T) {
	ctx := context.Background()
	bus := NewSubagentBus(ctx)
	defer bus.Close()

	spec := TaskSpec{
		ID:         "test_lifecycle_actor",
		Name:       "Lifecycle Actor",
		Role:       "verifier",
		TimeoutSec: 10,
		MailboxCap: 10,
		AutoStart:  false,
	}

	act, err := bus.Spawn(spec)
	if err != nil {
		t.Fatalf("Failed to spawn actor: %v", err)
	}

	if act.Status() != StatusCreated {
		t.Fatalf("Expected status CREATED, got %s", act.Status())
	}

	if err := act.Start(); err != nil {
		t.Fatalf("Failed to start actor: %v", err)
	}

	if act.Status() != StatusRunning {
		t.Fatalf("Expected status RUNNING, got %s", act.Status())
	}

	// Double start should fail
	if err := act.Start(); err == nil {
		t.Fatalf("Expected error when double-starting actor")
	}

	// Send message
	msg := SubagentMessage{
		ID:        "msg_1",
		Type:      MsgInstruction,
		Sender:    "test_runner",
		Timestamp: time.Now(),
		Content:   "verify contracts",
	}
	if err := act.Send(msg); err != nil {
		t.Fatalf("Failed to send message: %v", err)
	}

	// Wait briefly for processing
	time.Sleep(50 * time.Millisecond)
	if act.MessagesProcessed() < 1 {
		t.Fatalf("Expected at least 1 message processed, got %d", act.MessagesProcessed())
	}

	// Cancel
	act.Cancel("unit test complete")
	time.Sleep(50 * time.Millisecond)

	if act.Status() != StatusCancelled {
		t.Fatalf("Expected status CANCELLED, got %s", act.Status())
	}
}

func TestMailboxBackpressure(t *testing.T) {
	ctx := context.Background()
	bus := NewSubagentBus(ctx)
	defer bus.Close()

	// Mailbox with capacity 2, auto_start false so messages sit in queue
	spec := TaskSpec{
		ID:         "backpressure_actor",
		Name:       "Backpressure Actor",
		Role:       "queue_tester",
		TimeoutSec: 10,
		MailboxCap: 2,
		AutoStart:  false,
	}

	act, err := bus.Spawn(spec)
	if err != nil {
		t.Fatalf("Failed to spawn: %v", err)
	}

	// Sending to CREATED actor should fail
	err = act.Send(SubagentMessage{ID: "m0", Type: MsgHeartbeat})
	if err == nil {
		t.Fatalf("Expected send to CREATED actor to fail")
	}

	// Start actor, but send messages rapidly
	_ = act.Start()

	// Fill mailbox
	for i := 0; i < 2; i++ {
		_ = act.Send(SubagentMessage{
			ID:        fmt.Sprintf("m%d", i),
			Type:      MsgHeartbeat,
			Sender:    "tester",
			Timestamp: time.Now(),
		})
	}

	// Verify depth or capacity
	if act.InboxCap() != 2 {
		t.Fatalf("Expected inbox cap 2, got %d", act.InboxCap())
	}
}

func TestBroadcast(t *testing.T) {
	ctx := context.Background()
	bus := NewSubagentBus(ctx)
	defer bus.Close()

	for i := 0; i < 5; i++ {
		role := "engineer"
		if i%2 == 0 {
			role = "juror"
		}
		_, err := bus.Spawn(TaskSpec{
			ID:         fmt.Sprintf("actor_%d", i),
			Role:       role,
			AutoStart:  true,
			MailboxCap: 10,
		})
		if err != nil {
			t.Fatalf("Failed to spawn actor %d: %v", i, err)
		}
	}

	// Broadcast with roleFilter "juror" (actors 0, 2, 4 -> 3 actors)
	count := bus.Broadcast("orchestrator", MsgInstruction, map[string]any{"task": "vote"}, "juror")
	if count != 3 {
		t.Fatalf("Expected 3 juror recipients, got %d", count)
	}

	// Broadcast to all (5 actors)
	allCount := bus.Broadcast("orchestrator", MsgInstruction, map[string]any{"task": "sync"}, "")
	if allCount != 5 {
		t.Fatalf("Expected 5 total recipients, got %d", allCount)
	}
}

func TestTimeoutCancellation(t *testing.T) {
	ctx := context.Background()
	bus := NewSubagentBus(ctx)
	defer bus.Close()

	spec := TaskSpec{
		ID:         "timeout_actor",
		TimeoutSec: 1, // 1 second timeout
		AutoStart:  true,
		MailboxCap: 10,
	}

	act, err := bus.Spawn(spec)
	if err != nil {
		t.Fatalf("Failed to spawn: %v", err)
	}

	// Wait for context deadline to exceed
	time.Sleep(1200 * time.Millisecond)

	st := act.Status()
	if st != StatusFailed && st != StatusCancelled {
		t.Fatalf("Expected FAILED or CANCELLED on timeout, got %s", st)
	}
}

func TestRingBufferWrapAndGetSince(t *testing.T) {
	rb := NewRingBuffer(5)

	for i := int64(1); i <= 10; i++ {
		rb.Push(SubagentEvent{
			Seq:       i,
			Timestamp: time.Now(),
			Type:      EventLog,
			Content:   fmt.Sprintf("event_%d", i),
		})
	}

	if rb.Len() != 5 {
		t.Fatalf("Expected length 5, got %d", rb.Len())
	}

	// The events in buffer should be 6, 7, 8, 9, 10
	all := rb.GetAll()
	if len(all) != 5 {
		t.Fatalf("Expected 5 events, got %d", len(all))
	}
	if all[0].Seq != 6 || all[4].Seq != 10 {
		t.Fatalf("Expected seqs 6 to 10, got %d to %d", all[0].Seq, all[4].Seq)
	}

	// Query GetSince(7, 2)
	evts, hasMore := rb.GetSince(7, 2)
	if len(evts) != 2 {
		t.Fatalf("Expected 2 events, got %d", len(evts))
	}
	if !hasMore {
		t.Fatalf("Expected hasMore to be true")
	}
	if evts[0].Seq != 8 || evts[1].Seq != 9 {
		t.Fatalf("Expected events 8 and 9, got %d and %d", evts[0].Seq, evts[1].Seq)
	}
}

func TestBusReap(t *testing.T) {
	ctx := context.Background()
	bus := NewSubagentBus(ctx)
	defer bus.Close()

	act, err := bus.Spawn(TaskSpec{
		ID:        "reap_target",
		AutoStart: true,
	})
	if err != nil {
		t.Fatalf("Spawn error: %v", err)
	}

	act.Cancel("done")
	time.Sleep(20 * time.Millisecond)

	reaped := bus.Reap(0)
	if reaped != 1 {
		t.Fatalf("Expected 1 actor reaped, got %d", reaped)
	}

	if _, exists := bus.Get("reap_target"); exists {
		t.Fatalf("Expected reap_target to be deleted from bus")
	}
}

func TestConcurrentSpawnsAndRaceFreedom(t *testing.T) {
	ctx := context.Background()
	bus := NewSubagentBus(ctx)
	defer bus.Close()

	const actorCount = 50
	var wg sync.WaitGroup

	// Concurrently spawn 50 actors
	for i := 0; i < actorCount; i++ {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			role := "worker"
			if idx%3 == 0 {
				role = "auditor"
			}
			_, _ = bus.Spawn(TaskSpec{
				ID:         fmt.Sprintf("conc_actor_%d", idx),
				Role:       role,
				AutoStart:  true,
				MailboxCap: 64,
			})
		}(i)
	}
	wg.Wait()

	// Concurrently send messages, broadcast, read status, and cancel
	for i := 0; i < actorCount; i++ {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			id := fmt.Sprintf("conc_actor_%d", idx)
			_ = bus.Send(id, SubagentMessage{
				ID:        fmt.Sprintf("msg_%d", idx),
				Type:      MsgInstruction,
				Sender:    "conc_test",
				Timestamp: time.Now(),
				Content:   "run parallel job",
			})
			if act, ok := bus.Get(id); ok {
				_ = act.ToMap()
				_ = act.Events().GetAll()
			}
		}(i)
	}

	// Parallel broadcast
	wg.Add(1)
	go func() {
		defer wg.Done()
		_ = bus.Broadcast("tester", MsgHeartbeat, nil, "")
	}()

	wg.Wait()

	// Concurrently cancel actors
	for i := 0; i < actorCount; i++ {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			_ = bus.Cancel(fmt.Sprintf("conc_actor_%d", idx), "shutdown")
		}(i)
	}
	wg.Wait()
}
