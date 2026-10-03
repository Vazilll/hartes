package actor

import (
	"sync"
)

// RingBuffer is a thread-safe circular event buffer for SubagentEvents.
type RingBuffer struct {
	mu       sync.RWMutex
	capacity int
	buf      []SubagentEvent
	start    int
	count    int
}

// NewRingBuffer allocates a new circular buffer with fixed capacity.
func NewRingBuffer(capacity int) *RingBuffer {
	if capacity <= 0 {
		capacity = 512
	}
	return &RingBuffer{
		capacity: capacity,
		buf:      make([]SubagentEvent, capacity),
	}
}

// Push adds an event to the circular buffer. Overwrites the oldest event if full.
func (r *RingBuffer) Push(evt SubagentEvent) {
	r.mu.Lock()
	defer r.mu.Unlock()

	if r.count < r.capacity {
		idx := (r.start + r.count) % r.capacity
		r.buf[idx] = evt
		r.count++
	} else {
		// Buffer is full: overwrite oldest at r.start, then advance start
		r.buf[r.start] = evt
		r.start = (r.start + 1) % r.capacity
	}
}

// GetSince returns events with Seq > sinceSeq up to limit entries.
// If limit <= 0, all events strictly newer than sinceSeq are returned.
// Returns (events, hasMore).
func (r *RingBuffer) GetSince(sinceSeq int64, limit int) ([]SubagentEvent, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	var matched []SubagentEvent
	for i := 0; i < r.count; i++ {
		idx := (r.start + i) % r.capacity
		evt := r.buf[idx]
		if evt.Seq > sinceSeq {
			if limit > 0 && len(matched) >= limit {
				return matched, true
			}
			matched = append(matched, evt)
		}
	}
	return matched, false
}

// GetAll returns a snapshot of all events currently stored in chronological order.
func (r *RingBuffer) GetAll() []SubagentEvent {
	r.mu.RLock()
	defer r.mu.RUnlock()

	res := make([]SubagentEvent, r.count)
	for i := 0; i < r.count; i++ {
		idx := (r.start + i) % r.capacity
		res[i] = r.buf[idx]
	}
	return res
}

// Len returns the current count of elements stored.
func (r *RingBuffer) Len() int {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return r.count
}

// Cap returns the maximum capacity of the ring buffer.
func (r *RingBuffer) Cap() int {
	return r.capacity
}
