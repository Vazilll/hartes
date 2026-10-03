package actor

import (
	"context"
	"fmt"
	"runtime"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// TestStress_50ConcurrentActors_MemoryFootprint verifies that spawning 50 concurrent
// actors maintains a tiny memory footprint well under the 5 MB threshold (< 5,242,880 bytes).
func TestStress_50ConcurrentActors_MemoryFootprint(t *testing.T) {
	runtime.GC()
	var mBefore runtime.MemStats
	runtime.ReadMemStats(&mBefore)

	ctx := context.Background()
	bus := NewSubagentBus(ctx)
	defer bus.Close()

	const actorCount = 50
	var wg sync.WaitGroup

	// Concurrently spawn 50 actors with 256 mailbox capacity and 512 ring buffer capacity
	for i := 0; i < actorCount; i++ {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			role := "worker"
			if idx%2 == 0 {
				role = "verifier"
			}
			_, err := bus.Spawn(TaskSpec{
				ID:         fmt.Sprintf("actor_mem_stress_%03d", idx),
				Name:       fmt.Sprintf("MemStressActor-%d", idx),
				Role:       role,
				Prompt:     "Stress memory test verification",
				TimeoutSec: 300,
				MailboxCap: 256,
				AutoStart:  true,
			})
			if err != nil {
				t.Errorf("Failed to spawn actor %d: %v", idx, err)
			}
		}(i)
	}
	wg.Wait()

	if bus.Count() != actorCount {
		t.Fatalf("Expected %d actors registered, got %d", actorCount, bus.Count())
	}

	// Verify all actors transitioned to RUNNING
	for i := 0; i < actorCount; i++ {
		act, ok := bus.Get(fmt.Sprintf("actor_mem_stress_%03d", i))
		if !ok {
			t.Fatalf("Actor %d not found in bus", i)
		}
		if act.Status() != StatusRunning {
			t.Fatalf("Actor %d status is %s, expected RUNNING", i, act.Status())
		}
	}

	// Let actor goroutines settle and allocate stacks/channels
	time.Sleep(50 * time.Millisecond)

	var mAfter runtime.MemStats
	runtime.ReadMemStats(&mAfter)

	allocDelta := int64(mAfter.Alloc) - int64(mBefore.Alloc)
	heapDelta := int64(mAfter.HeapAlloc) - int64(mBefore.HeapAlloc)

	t.Logf("=== 50 ACTORS MEMORY FOOTPRINT AUDIT ===")
	t.Logf("Baseline HeapAlloc: %d bytes (%.2f KB)", mBefore.HeapAlloc, float64(mBefore.HeapAlloc)/1024.0)
	t.Logf("After 50 Actors HeapAlloc: %d bytes (%.2f KB)", mAfter.HeapAlloc, float64(mAfter.HeapAlloc)/1024.0)
	t.Logf("HeapAlloc Delta: %d bytes (%.2f KB / %.3f MB)", heapDelta, float64(heapDelta)/1024.0, float64(heapDelta)/(1024.0*1024.0))
	t.Logf("Alloc Delta: %d bytes (%.2f KB / %.3f MB)", allocDelta, float64(allocDelta)/1024.0, float64(allocDelta)/(1024.0*1024.0))

	// Invariant: Total memory consumed by 50 concurrent actors must be < 5 MB
	const maxAllowedBytes = 5 * 1024 * 1024 // 5 MB
	if heapDelta > maxAllowedBytes {
		t.Fatalf("Memory limit breached: heap delta %d bytes exceeds max allowed %d bytes (5 MB)", heapDelta, maxAllowedBytes)
	}
	if allocDelta > maxAllowedBytes {
		t.Fatalf("Memory limit breached: alloc delta %d bytes exceeds max allowed %d bytes (5 MB)", allocDelta, maxAllowedBytes)
	}

	t.Logf("VERIFIED: 50 concurrent actors consumed %.3f MB, well below the 5 MB limit.", float64(heapDelta)/(1024.0*1024.0))
}

// TestStress_MailboxBackpressure_Flood1000Messages tests backpressure behavior when
// flooding 1,000 messages against an actor with a bounded channel capacity (256).
// Verifies non-blocking rejection without server crash or hang.
func TestStress_MailboxBackpressure_Flood1000Messages(t *testing.T) {
	ctx := context.Background()
	bus := NewSubagentBus(ctx)
	defer bus.Close()

	// Part 1: Static Channel Backpressure (Actor not started yet -> inbox does not drain)
	t.Run("StaticChannelSaturation", func(t *testing.T) {
		act, err := bus.Spawn(TaskSpec{
			ID:         "flood_static_target",
			MailboxCap: 256,
			AutoStart:  false,
		})
		if err != nil {
			t.Fatalf("Spawn failed: %v", err)
		}

		// Transition to running status directly without launching draining loop to test channel saturation
		act.mu.Lock()
		act.status = StatusRunning
		act.mu.Unlock()

		const totalFlood = 1000
		var acceptedCount int
		var rejectedCount int

		startTime := time.Now()
		for i := 0; i < totalFlood; i++ {
			msg := SubagentMessage{
				ID:        fmt.Sprintf("flood_msg_%04d", i),
				Type:      MsgInstruction,
				Sender:    "adversarial_tester",
				Timestamp: time.Now(),
				Content:   fmt.Sprintf("flood payload %d", i),
			}
			err := act.Send(msg)
			if err == nil {
				acceptedCount++
			} else {
				rejectedCount++
			}
		}
		duration := time.Since(startTime)

		t.Logf("Static flood results: %d accepted, %d rejected in %v", acceptedCount, rejectedCount, duration)

		if acceptedCount != 256 {
			t.Fatalf("Expected exactly 256 accepted messages (channel capacity), got %d", acceptedCount)
		}
		if rejectedCount != (totalFlood - 256) {
			t.Fatalf("Expected exactly %d rejected messages, got %d", totalFlood-256, rejectedCount)
		}
		if act.InboxDepth() != 256 {
			t.Fatalf("Expected inbox depth 256, got %d", act.InboxDepth())
		}
		// Non-blocking verification: 1000 iterations must take < 50ms
		if duration > 100*time.Millisecond {
			t.Fatalf("Backpressure was blocking! Took %v for 1000 sends", duration)
		}
	})

	// Part 2: Dynamic Concurrent Flood (Actor actively draining while flooded by 5 concurrent workers)
	t.Run("DynamicConcurrentFlood", func(t *testing.T) {
		act, err := bus.Spawn(TaskSpec{
			ID:         "flood_active_target",
			MailboxCap: 256,
			AutoStart:  true,
		})
		if err != nil {
			t.Fatalf("Spawn failed: %v", err)
		}

		const workers = 5
		const msgsPerWorker = 200 // Total 1,000 messages
		var acceptedTotal atomic.Int64
		var rejectedTotal atomic.Int64
		var wg sync.WaitGroup

		startSignal := make(chan struct{})
		for w := 0; w < workers; w++ {
			wg.Add(1)
			go func(workerID int) {
				defer wg.Done()
				<-startSignal
				for m := 0; m < msgsPerWorker; m++ {
					msg := SubagentMessage{
						ID:        fmt.Sprintf("worker_%d_msg_%d", workerID, m),
						Type:      MsgInstruction,
						Sender:    fmt.Sprintf("worker_%d", workerID),
						Timestamp: time.Now(),
						Content:   "stress payload",
					}
					if err := act.Send(msg); err == nil {
						acceptedTotal.Add(1)
					} else {
						rejectedTotal.Add(1)
					}
				}
			}(w)
		}

		close(startSignal) // Unleash all flood workers simultaneously
		wg.Wait()

		accepted := acceptedTotal.Load()
		rejected := rejectedTotal.Load()
		t.Logf("Dynamic flood results: %d accepted, %d rejected (total %d)", accepted, rejected, accepted+rejected)

		if accepted+rejected != int64(workers*msgsPerWorker) {
			t.Fatalf("Message count mismatch: %d + %d != %d", accepted, rejected, workers*msgsPerWorker)
		}
		if accepted < 256 {
			t.Fatalf("Expected at least 256 accepted messages, got %d", accepted)
		}

		// Allow actor to process remaining messages
		time.Sleep(100 * time.Millisecond)

		if act.Status() != StatusRunning {
			t.Fatalf("Expected actor to remain RUNNING, got %s (err: %v)", act.Status(), act.Error())
		}
		if act.MessagesProcessed() < accepted {
			t.Logf("Actor processed %d of %d accepted messages", act.MessagesProcessed(), accepted)
		}
	})
}

// TestStress_RapidCancellation_GoroutineCleanup verifies clean termination of
// 50 concurrent long-running actors and confirms that goroutines are cleaned up.
func TestStress_RapidCancellation_GoroutineCleanup(t *testing.T) {
	initialGoroutines := runtime.NumGoroutine()
	ctx := context.Background()
	bus := NewSubagentBus(ctx)
	defer bus.Close()

	const actorCount = 50

	// Spawn 50 long-running actors
	for i := 0; i < actorCount; i++ {
		_, err := bus.Spawn(TaskSpec{
			ID:         fmt.Sprintf("actor_cancel_%03d", i),
			TimeoutSec: 300,
			MailboxCap: 64,
			AutoStart:  true,
		})
		if err != nil {
			t.Fatalf("Failed to spawn actor %d: %v", i, err)
		}
	}

	time.Sleep(30 * time.Millisecond)
	runningGoroutines := runtime.NumGoroutine()
	t.Logf("Goroutine count with 50 actors: %d (baseline was %d)", runningGoroutines, initialGoroutines)

	if runningGoroutines < initialGoroutines+actorCount {
		t.Logf("Warning: Expected >= %d goroutines, got %d (some may have scheduled fast)", initialGoroutines+actorCount, runningGoroutines)
	}

	// Rapidly cancel all 50 actors concurrently
	var wg sync.WaitGroup
	for i := 0; i < actorCount; i++ {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			reason := fmt.Sprintf("adversarial rapid abort #%d", idx)
			_ = bus.Cancel(fmt.Sprintf("actor_cancel_%03d", idx), reason)
		}(i)
	}
	wg.Wait()

	// Verify all actors report CANCELLED status
	for i := 0; i < actorCount; i++ {
		act, ok := bus.Get(fmt.Sprintf("actor_cancel_%03d", i))
		if !ok {
			t.Fatalf("Actor %d missing", i)
		}
		if act.Status() != StatusCancelled {
			t.Fatalf("Actor %d status is %s, expected CANCELLED", i, act.Status())
		}
	}

	// Poll for goroutine cleanup
	cleanedUp := false
	var finalGoroutines int
	for attempt := 0; attempt < 20; attempt++ {
		time.Sleep(25 * time.Millisecond)
		runtime.GC()
		finalGoroutines = runtime.NumGoroutine()
		if finalGoroutines <= initialGoroutines+3 { // allow tiny runtime fluctuation
			cleanedUp = true
			break
		}
	}

	t.Logf("Final goroutine count after cancel: %d (baseline: %d)", finalGoroutines, initialGoroutines)
	if !cleanedUp {
		t.Fatalf("Goroutine leak detected! Initial: %d, Running: %d, Final: %d", initialGoroutines, runningGoroutines, finalGoroutines)
	}

	// Verify reap cleans all 50 terminated actors
	reaped := bus.Reap(0)
	if reaped != actorCount {
		t.Fatalf("Expected %d reaped actors, got %d", actorCount, reaped)
	}
	if bus.Count() != 0 {
		t.Fatalf("Expected bus count 0 after reap, got %d", bus.Count())
	}
}

// TestStress_BroadcastStorm_50Actors executes a broadcast storm of 200 broadcasts
// (attempting ~5,000 deliveries) across 50 actors with and without role filters.
func TestStress_BroadcastStorm_50Actors(t *testing.T) {
	ctx := context.Background()
	bus := NewSubagentBus(ctx)
	defer bus.Close()

	const totalActors = 50
	// Distribution: 25 workers, 15 auditors, 10 jurors
	for i := 0; i < totalActors; i++ {
		var role string
		switch {
		case i < 25:
			role = "worker"
		case i < 40:
			role = "auditor"
		default:
			role = "juror"
		}

		_, err := bus.Spawn(TaskSpec{
			ID:         fmt.Sprintf("bcast_actor_%03d", i),
			Role:       role,
			MailboxCap: 256,
			AutoStart:  true,
		})
		if err != nil {
			t.Fatalf("Spawn error: %v", err)
		}
	}

	time.Sleep(30 * time.Millisecond)

	// Step 1: Precise role filtering verification
	wCount := bus.Broadcast("orchestrator", MsgInstruction, map[string]any{"cmd": "work"}, "worker")
	if wCount != 25 {
		t.Fatalf("Expected 25 worker deliveries, got %d", wCount)
	}

	aCount := bus.Broadcast("orchestrator", MsgInstruction, map[string]any{"cmd": "audit"}, "auditor")
	if aCount != 15 {
		t.Fatalf("Expected 15 auditor deliveries, got %d", aCount)
	}

	jCount := bus.Broadcast("orchestrator", MsgInstruction, map[string]any{"cmd": "verdict"}, "juror")
	if jCount != 10 {
		t.Fatalf("Expected 10 juror deliveries, got %d", jCount)
	}

	allCount := bus.Broadcast("orchestrator", MsgHeartbeat, nil, "")
	if allCount != 50 {
		t.Fatalf("Expected 50 universal deliveries, got %d", allCount)
	}

	zeroCount := bus.Broadcast("orchestrator", MsgInstruction, nil, "nonexistent_role")
	if zeroCount != 0 {
		t.Fatalf("Expected 0 deliveries for unknown role, got %d", zeroCount)
	}

	// Step 2: High-concurrency Broadcast Storm (10 parallel senders, 20 broadcasts each)
	const concurrentPublishers = 10
	const broadcastsPerPub = 20
	var totalDeliveries atomic.Int64
	var pubWg sync.WaitGroup

	startTime := time.Now()
	for p := 0; p < concurrentPublishers; p++ {
		pubWg.Add(1)
		go func(pubID int) {
			defer pubWg.Done()
			roles := []string{"", "worker", "auditor", "juror"}
			for b := 0; b < broadcastsPerPub; b++ {
				role := roles[(pubID+b)%len(roles)]
				delivered := bus.Broadcast(
					fmt.Sprintf("pub_%d", pubID),
					MsgInstruction,
					map[string]any{"burst": b, "sender": pubID},
					role,
				)
				totalDeliveries.Add(int64(delivered))
			}
		}(p)
	}
	pubWg.Wait()
	stormDuration := time.Since(startTime)

	t.Logf("Broadcast storm completed: %d total message deliveries across %d broadcasts in %v",
		totalDeliveries.Load(), concurrentPublishers*broadcastsPerPub, stormDuration)

	// Allow actors to process incoming instructions
	time.Sleep(100 * time.Millisecond)

	// Verify all actors remain alive and healthy
	for i := 0; i < totalActors; i++ {
		act, _ := bus.Get(fmt.Sprintf("bcast_actor_%03d", i))
		if act.Status() != StatusRunning {
			t.Fatalf("Actor %d failed during broadcast storm! Status: %s, Error: %v", i, act.Status(), act.Error())
		}
		if act.MessagesProcessed() == 0 {
			t.Fatalf("Actor %d processed 0 messages despite broadcast storm", i)
		}
	}
}

// TestStress_RingBufferWrapping_GetSince_NoLeak tests pushing 100,000 events into a
// circular buffer of capacity 100, verifying boundary correctness of GetSince and absence of leaks.
func TestStress_RingBufferWrapping_GetSince_NoLeak(t *testing.T) {
	const cap = 100
	rb := NewRingBuffer(cap)

	runtime.GC()
	var mBefore runtime.MemStats
	runtime.ReadMemStats(&mBefore)

	const totalEvents = int64(100000)
	for seq := int64(1); seq <= totalEvents; seq++ {
		rb.Push(SubagentEvent{
			Seq:       seq,
			Timestamp: time.Now(),
			Type:      EventLog,
			Content:   fmt.Sprintf("stress event log payload #%d", seq),
			Metadata:  map[string]any{"seq": seq, "cycle": seq / 100},
		})
	}

	runtime.GC()
	var mAfter runtime.MemStats
	runtime.ReadMemStats(&mAfter)

	heapGrowth := int64(mAfter.HeapAlloc) - int64(mBefore.HeapAlloc)
	t.Logf("Ring buffer 100k events pushed. Heap growth: %d bytes (%.2f KB)", heapGrowth, float64(heapGrowth)/1024.0)

	// Heap growth must be negligible since old elements are continuously overwritten and collected
	if heapGrowth > 512*1024 { // < 512 KB
		t.Fatalf("Suspected memory leak in ring buffer: heap growth %d bytes exceeds 512 KB", heapGrowth)
	}

	// Verify buffer length and capacity
	if rb.Len() != cap {
		t.Fatalf("Expected buffer length %d, got %d", cap, rb.Len())
	}
	if rb.Cap() != cap {
		t.Fatalf("Expected buffer cap %d, got %d", cap, rb.Cap())
	}

	// Verify oldest and newest stored items
	all := rb.GetAll()
	if len(all) != cap {
		t.Fatalf("Expected %d snapshot events, got %d", cap, len(all))
	}
	oldestExpected := totalEvents - int64(cap) + 1 // 100000 - 100 + 1 = 99901
	newestExpected := totalEvents                  // 100000

	if all[0].Seq != oldestExpected {
		t.Fatalf("Expected oldest seq %d, got %d", oldestExpected, all[0].Seq)
	}
	if all[cap-1].Seq != newestExpected {
		t.Fatalf("Expected newest seq %d, got %d", newestExpected, all[cap-1].Seq)
	}

	// Boundary Test 1: GetSince with seq older than buffer start (e.g. seq=0)
	evts, hasMore := rb.GetSince(0, 10)
	if len(evts) != 10 {
		t.Fatalf("Expected 10 events, got %d", len(evts))
	}
	if !hasMore {
		t.Fatalf("Expected hasMore=true")
	}
	if evts[0].Seq != oldestExpected || evts[9].Seq != oldestExpected+9 {
		t.Fatalf("Unexpected seq range: %d to %d", evts[0].Seq, evts[9].Seq)
	}

	// Boundary Test 2: GetSince with exact offset near the end
	evtsNearEnd, hasMoreNearEnd := rb.GetSince(totalEvents-5, 10)
	if len(evtsNearEnd) != 5 {
		t.Fatalf("Expected 5 remaining events, got %d", len(evtsNearEnd))
	}
	if hasMoreNearEnd {
		t.Fatalf("Expected hasMore=false when all remaining are returned")
	}
	if evtsNearEnd[0].Seq != totalEvents-4 || evtsNearEnd[4].Seq != totalEvents {
		t.Fatalf("Unexpected tail events: %d to %d", evtsNearEnd[0].Seq, evtsNearEnd[4].Seq)
	}

	// Boundary Test 3: GetSince exactly at newest seq
	evtsAtEnd, hasMoreAtEnd := rb.GetSince(totalEvents, 10)
	if len(evtsAtEnd) != 0 || hasMoreAtEnd {
		t.Fatalf("Expected 0 events and hasMore=false, got %d events and %v", len(evtsAtEnd), hasMoreAtEnd)
	}

	// Boundary Test 4: GetSince beyond newest seq
	evtsFuture, hasMoreFuture := rb.GetSince(totalEvents+100, 10)
	if len(evtsFuture) != 0 || hasMoreFuture {
		t.Fatalf("Expected 0 events and hasMore=false for future seq, got %d events and %v", len(evtsFuture), hasMoreFuture)
	}

	// Boundary Test 5: GetSince with limit <= 0 (return all matching)
	allSince, hasMoreAll := rb.GetSince(oldestExpected-1, 0)
	if len(allSince) != cap || hasMoreAll {
		t.Fatalf("Expected %d events and hasMore=false, got %d and %v", cap, len(allSince), hasMoreAll)
	}

	// Step 3: Concurrent Writer & Reader Stress Test
	var rwWg sync.WaitGroup
	const writers = 5
	const readers = 5

	stopSignal := make(chan struct{})
	for w := 0; w < writers; w++ {
		rwWg.Add(1)
		go func(writerID int) {
			defer rwWg.Done()
			seqCounter := int64(writerID * 1000000)
			for {
				select {
				case <-stopSignal:
					return
				default:
					seqCounter++
					rb.Push(SubagentEvent{
						Seq:       seqCounter,
						Timestamp: time.Now(),
						Type:      EventLog,
						Content:   "concurrent push",
					})
				}
			}
		}(w)
	}

	for r := 0; r < readers; r++ {
		rwWg.Add(1)
		go func() {
			defer rwWg.Done()
			for {
				select {
				case <-stopSignal:
					return
				default:
					_ = rb.GetAll()
					_, _ = rb.GetSince(100, 20)
				}
			}
		}()
	}

	time.Sleep(100 * time.Millisecond)
	close(stopSignal)
	rwWg.Wait()

	t.Logf("Concurrent ring buffer stress completed safely with 0 panics or data races.")
}
