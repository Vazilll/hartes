package main

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// TelemetryEvent represents a single sensor telemetry packet.
type TelemetryEvent struct {
	Timestamp int64
	SensorID  string
	Value     float64
	Status    string
}

// AegisEngine defines the core interface for the telemetry pipeline.
type AegisEngine interface {
	Ingest(ctx context.Context, evt TelemetryEvent) error
	Flush() ([]TelemetryEvent, error)
	HealthCheck() bool
}

// AegisServer manages concurrent event processing with ring-buffer semantics.
type AegisServer struct {
	mu       sync.RWMutex
	capacity int
	events   []TelemetryEvent
	head     int
	tail     int
	size     int
	isClosed bool
}

// NewAegisServer constructs an isolated AegisServer with bounded capacity.
func NewAegisServer(capacity int) *AegisServer {
	if capacity <= 0 {
		capacity = 1024
	}
	return &AegisServer{
		capacity: capacity,
		events:   make([]TelemetryEvent, capacity),
	}
}

// Ingest adds a telemetry event under lock protection with overflow defense.
func (s *AegisServer) Ingest(ctx context.Context, evt TelemetryEvent) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.isClosed {
		return fmt.Errorf("server is closed")
	}

	select {
	case <-ctx.Done():
		return ctx.Err()
	default:
	}

	if s.size == s.capacity {
		// Overwrite oldest entry (ring-buffer semantics)
		s.head = (s.head + 1) % s.capacity
		s.size--
	}

	s.events[s.tail] = evt
	s.tail = (s.tail + 1) % s.capacity
	s.size++

	return nil
}

// Flush retrieves and resets currently buffered telemetry events.
func (s *AegisServer) Flush() ([]TelemetryEvent, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.size == 0 {
		return nil, nil
	}

	result := make([]TelemetryEvent, s.size)
	for i := 0; i < s.size; i++ {
		idx := (s.head + i) % s.capacity
		result[i] = s.events[idx]
	}

	s.head = 0
	s.tail = 0
	s.size = 0

	return result, nil
}

// HealthCheck verifies internal state consistency.
func (s *AegisServer) HealthCheck() bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return !s.isClosed && s.size <= s.capacity && s.size >= 0
}

func main() {
	server := NewAegisServer(512)
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	for i := 0; i < 100; i++ {
		_ = server.Ingest(ctx, TelemetryEvent{
			Timestamp: time.Now().UnixNano(),
			SensorID:  fmt.Sprintf("npu_core_%d", i%4),
			Value:     float64(i) * 1.414,
			Status:    "OK",
		})
	}

	flushed, _ := server.Flush()
	fmt.Printf("Aegis Server flushed %d events, Health: %v\n", len(flushed), server.HealthCheck())
}
