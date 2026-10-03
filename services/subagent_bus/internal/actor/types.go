package actor

import (
	"time"
)

type ActorStatus string

const (
	StatusCreated   ActorStatus = "CREATED"
	StatusRunning   ActorStatus = "RUNNING"
	StatusPaused    ActorStatus = "PAUSED"
	StatusCompleted ActorStatus = "COMPLETED"
	StatusFailed    ActorStatus = "FAILED"
	StatusCancelled ActorStatus = "CANCELLED"
)

type MessageType string

const (
	MsgInstruction MessageType = "instruction"
	MsgFeedback    MessageType = "feedback"
	MsgToolResult  MessageType = "tool_result"
	MsgHeartbeat   MessageType = "heartbeat"
	MsgShutdown    MessageType = "shutdown"
)

type SubagentMessage struct {
	ID        string         `json:"id"`
	Type      MessageType    `json:"type"`
	Sender    string         `json:"sender"`
	Timestamp time.Time      `json:"timestamp"`
	Payload   map[string]any `json:"payload,omitempty"`
	Content   string         `json:"content,omitempty"`
}

type EventType string

const (
	EventLog      EventType = "log"
	EventState    EventType = "state_change"
	EventOutput   EventType = "output"
	EventError    EventType = "error"
	EventProgress EventType = "progress"
)

type SubagentEvent struct {
	Seq       int64          `json:"seq"`
	Timestamp time.Time      `json:"timestamp"`
	Type      EventType      `json:"type"`
	Content   string         `json:"content"`
	Metadata  map[string]any `json:"metadata,omitempty"`
}

type TaskSpec struct {
	ID         string         `json:"id"`
	Name       string         `json:"name"`
	Role       string         `json:"role"`
	Prompt     string         `json:"prompt"`
	Params     map[string]any `json:"params,omitempty"`
	TimeoutSec int            `json:"timeout_sec"`
	MailboxCap int            `json:"mailbox_cap"`
	AutoStart  bool           `json:"auto_start"`
}
