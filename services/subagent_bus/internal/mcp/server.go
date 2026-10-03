package mcp

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"

	"vazus/services/subagent_bus/internal/actor"
)

// Server wraps the mark3labs MCPServer and connects it to the SubagentBus.
type Server struct {
	bus       *actor.SubagentBus
	mcpServer *server.MCPServer
}

// NewServer initializes an MCP server exposing all 8 subagent tools and resources.
func NewServer(bus *actor.SubagentBus) *Server {
	mcpSrv := server.NewMCPServer(
		"vazus-subagent-bus",
		"1.0.0",
		server.WithToolCapabilities(true),
		server.WithResourceCapabilities(true, false),
		server.WithPromptCapabilities(false),
	)

	s := &Server{
		bus:       bus,
		mcpServer: mcpSrv,
	}

	s.registerTools()
	s.registerResources()
	return s
}

// MCPServer returns the underlying mark3labs MCPServer.
func (s *Server) MCPServer() *server.MCPServer {
	return s.mcpServer
}

func (s *Server) registerTools() {
	// 1. subagent_spawn
	s.mcpServer.AddTool(
		mcp.NewTool("subagent_spawn",
			mcp.WithDescription("Spawns a new concurrent subagent actor goroutine in the bus."),
			mcp.WithString("name", mcp.Required(), mcp.Description("Human-readable name of the subagent")),
			mcp.WithString("role", mcp.Description("Specialized role/persona (e.g. code_engineer, verifier_worker, concordia_juror)")),
			mcp.WithString("prompt", mcp.Required(), mcp.Description("Task description or prompt to execute")),
			mcp.WithString("id", mcp.Description("Optional unique ID for the subagent")),
			mcp.WithObject("params", mcp.Description("Optional parameters dictionary")),
			mcp.WithInteger("timeout_sec", mcp.Description("Execution timeout in seconds (default 300)")),
			mcp.WithInteger("mailbox_cap", mcp.Description("Bounded mailbox channel capacity (default 256)")),
			mcp.WithBoolean("auto_start", mcp.Description("Whether to automatically launch actor loop (default true)")),
		),
		s.handleSubagentSpawn,
	)

	// 2. subagent_send_message
	s.mcpServer.AddTool(
		mcp.NewTool("subagent_send_message",
			mcp.WithDescription("Sends an asynchronous message into the subagent actor's bounded channel."),
			mcp.WithString("subagent_id", mcp.Required(), mcp.Description("Target subagent ID")),
			mcp.WithString("type", mcp.Description("Message type: instruction, feedback, tool_result, heartbeat, shutdown")),
			mcp.WithString("sender", mcp.Description("Sender identifier (e.g. orchestrator, peer_actor)")),
			mcp.WithString("content", mcp.Description("Message text content")),
			mcp.WithObject("payload", mcp.Description("Optional structured payload arguments")),
		),
		s.handleSubagentSendMessage,
	)

	// 3. subagent_broadcast
	s.mcpServer.AddTool(
		mcp.NewTool("subagent_broadcast",
			mcp.WithDescription("Broadcasts a message to all active subagents matching optional role filter."),
			mcp.WithString("sender", mcp.Description("Sender identifier")),
			mcp.WithString("type", mcp.Description("Message type")),
			mcp.WithString("content", mcp.Description("Message text content")),
			mcp.WithObject("payload", mcp.Description("Structured payload arguments")),
			mcp.WithString("role_filter", mcp.Description("Only deliver to subagents with this role")),
		),
		s.handleSubagentBroadcast,
	)

	// 4. subagent_poll_events
	s.mcpServer.AddTool(
		mcp.NewTool("subagent_poll_events",
			mcp.WithDescription("Polls or streams events from the subagent's ring buffer."),
			mcp.WithString("subagent_id", mcp.Required(), mcp.Description("Target subagent ID")),
			mcp.WithInteger("since_seq", mcp.Description("Sequence number to poll strictly after (default 0)")),
			mcp.WithInteger("limit", mcp.Description("Maximum events to return (default 50)")),
			mcp.WithInteger("timeout_ms", mcp.Description("Timeout in milliseconds")),
		),
		s.handleSubagentPollEvents,
	)

	// 5. subagent_cancel
	s.mcpServer.AddTool(
		mcp.NewTool("subagent_cancel",
			mcp.WithDescription("Cancels and terminates a running subagent immediately."),
			mcp.WithString("subagent_id", mcp.Required(), mcp.Description("Target subagent ID")),
			mcp.WithString("reason", mcp.Description("Cancellation rationale")),
		),
		s.handleSubagentCancel,
	)

	// 6. subagent_get_status
	s.mcpServer.AddTool(
		mcp.NewTool("subagent_get_status",
			mcp.WithDescription("Queries real-time status and telemetry for a subagent."),
			mcp.WithString("subagent_id", mcp.Required(), mcp.Description("Target subagent ID")),
		),
		s.handleSubagentGetStatus,
	)

	// 7. subagent_list
	s.mcpServer.AddTool(
		mcp.NewTool("subagent_list",
			mcp.WithDescription("Lists all active, completed, or failed subagents."),
			mcp.WithString("status", mcp.Description("Status filter: all, active, completed, failed")),
			mcp.WithString("role", mcp.Description("Filter by role")),
		),
		s.handleSubagentList,
	)

	// 8. subagent_reap
	s.mcpServer.AddTool(
		mcp.NewTool("subagent_reap",
			mcp.WithDescription("Reaps terminated subagents (COMPLETED, FAILED, CANCELLED) to free memory."),
			mcp.WithInteger("max_age_sec", mcp.Description("Age threshold in seconds (0 for immediate)")),
		),
		s.handleSubagentReap,
	)
}

func (s *Server) registerResources() {
	s.mcpServer.AddResource(
		mcp.NewResource("subagent://bus/topology", "Bus Topology",
			mcp.WithResourceDescription("Real-time topology snapshot of active actors, mailboxes, and memory."),
			mcp.WithMIMEType("application/json"),
		),
		func(ctx context.Context, request mcp.ReadResourceRequest) ([]mcp.ResourceContents, error) {
			actors := s.bus.List("all", "")
			activeCount := 0
			for _, a := range actors {
				if a.Status() == actor.StatusRunning {
					activeCount++
				}
			}
			top := map[string]any{
				"total_actors": len(actors),
				"active":       activeCount,
				"timestamp":    time.Now().Format(time.RFC3339),
			}
			data, _ := json.Marshal(top)
			return []mcp.ResourceContents{
				mcp.TextResourceContents{
					URI:      "subagent://bus/topology",
					MIMEType: "application/json",
					Text:     string(data),
				},
			}, nil
		},
	)
}

// -----------------------------------------------------------------------------
// Tool Handlers
// -----------------------------------------------------------------------------

func (s *Server) handleSubagentSpawn(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	name := req.GetString("name", "")
	prompt := req.GetString("prompt", "")

	// Check required arguments for schema validity
	if name == "" || prompt == "" {
		return mcp.NewToolResultError("Validation error: 'name' and 'prompt' are required parameters for subagent_spawn"), nil
	}

	role := req.GetString("role", "worker")
	id := req.GetString("id", "")
	timeoutSec := req.GetInt("timeout_sec", 300)
	mailboxCap := req.GetInt("mailbox_cap", 256)
	autoStart := req.GetBool("auto_start", true)

	var params map[string]any
	if p, ok := req.GetArguments()["params"].(map[string]any); ok {
		params = p
	}

	spec := actor.TaskSpec{
		ID:         id,
		Name:       name,
		Role:       role,
		Prompt:     prompt,
		Params:     params,
		TimeoutSec: timeoutSec,
		MailboxCap: mailboxCap,
		AutoStart:  autoStart,
	}

	act, err := s.bus.Spawn(spec)
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("Failed to spawn subagent: %v", err)), nil
	}

	resp := map[string]any{
		"success":     true,
		"subagent_id": act.Spec().ID,
		"id":          act.Spec().ID,
		"name":        act.Spec().Name,
		"role":        act.Spec().Role,
		"status":      string(act.Status()),
		"created_at":  time.Now().Format(time.RFC3339),
	}
	data, _ := json.Marshal(resp)
	return mcp.NewToolResultText(string(data)), nil
}

func (s *Server) handleSubagentSendMessage(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	subagentID := req.GetString("subagent_id", "")
	if subagentID == "" {
		return mcp.NewToolResultError("Validation error: 'subagent_id' is required"), nil
	}

	msgTypeStr := req.GetString("type", "")
	if msgTypeStr == "" {
		msgTypeStr = req.GetString("message_type", "instruction")
	}
	sender := req.GetString("sender", "orchestrator")
	content := req.GetString("content", req.GetString("message", ""))

	var payload map[string]any
	if p, ok := req.GetArguments()["payload"].(map[string]any); ok {
		payload = p
	}

	msg := actor.SubagentMessage{
		ID:        fmt.Sprintf("msg_%d", time.Now().UnixNano()),
		Type:      actor.MessageType(msgTypeStr),
		Sender:    sender,
		Timestamp: time.Now(),
		Content:   content,
		Payload:   payload,
	}

	err := s.bus.Send(subagentID, msg)
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("Failed to deliver message: %v", err)), nil
	}

	act, _ := s.bus.Get(subagentID)
	queueDepth := 0
	if act != nil {
		queueDepth = act.InboxDepth()
	}

	resp := map[string]any{
		"success":     true,
		"delivered":   true,
		"subagent_id": subagentID,
		"queue_depth": queueDepth,
	}
	data, _ := json.Marshal(resp)
	return mcp.NewToolResultText(string(data)), nil
}

func (s *Server) handleSubagentBroadcast(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	sender := req.GetString("sender", "orchestrator")
	msgTypeStr := req.GetString("type", req.GetString("message_type", "instruction"))
	content := req.GetString("content", req.GetString("message", ""))
	roleFilter := req.GetString("role_filter", "")

	var payload map[string]any
	if p, ok := req.GetArguments()["payload"].(map[string]any); ok {
		payload = p
	}
	if content != "" {
		if payload == nil {
			payload = make(map[string]any)
		}
		payload["content"] = content
	}

	deliveredCount := s.bus.Broadcast(sender, actor.MessageType(msgTypeStr), payload, roleFilter)

	resp := map[string]any{
		"success":          true,
		"count":            deliveredCount,
		"recipients_count": deliveredCount,
		"delivered_count":  deliveredCount,
		"role_filter":      roleFilter,
	}
	data, _ := json.Marshal(resp)
	return mcp.NewToolResultText(string(data)), nil
}

func (s *Server) handleSubagentPollEvents(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	subagentID := req.GetString("subagent_id", "")
	if subagentID == "" {
		return mcp.NewToolResultError("Validation error: 'subagent_id' is required"), nil
	}

	sinceSeq := int64(req.GetInt("since_seq", 0))
	limit := req.GetInt("limit", req.GetInt("max_events", 50))

	act, ok := s.bus.Get(subagentID)
	if !ok {
		return mcp.NewToolResultError(fmt.Sprintf("Subagent with ID '%s' not found", subagentID)), nil
	}

	events, hasMore := act.Events().GetSince(sinceSeq, limit)
	latestSeq := sinceSeq
	if len(events) > 0 {
		latestSeq = events[len(events)-1].Seq
	}

	resp := map[string]any{
		"subagent_id": subagentID,
		"status":      string(act.Status()),
		"events":      events,
		"latest_seq":  latestSeq,
		"has_more":    hasMore,
	}
	data, _ := json.Marshal(resp)
	return mcp.NewToolResultText(string(data)), nil
}

func (s *Server) handleSubagentCancel(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	subagentID := req.GetString("subagent_id", "")
	if subagentID == "" {
		return mcp.NewToolResultError("Validation error: 'subagent_id' is required"), nil
	}

	reason := req.GetString("reason", "cancelled via MCP")

	err := s.bus.Cancel(subagentID, reason)
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("Failed to cancel subagent: %v", err)), nil
	}

	resp := map[string]any{
		"success":     true,
		"cancelled":   true,
		"subagent_id": subagentID,
		"status":      "CANCELLED",
	}
	data, _ := json.Marshal(resp)
	return mcp.NewToolResultText(string(data)), nil
}

func (s *Server) handleSubagentGetStatus(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	subagentID := req.GetString("subagent_id", "")
	if subagentID == "" {
		return mcp.NewToolResultError("Validation error: 'subagent_id' is required"), nil
	}

	act, ok := s.bus.Get(subagentID)
	if !ok {
		return mcp.NewToolResultError(fmt.Sprintf("Subagent with ID '%s' not found", subagentID)), nil
	}

	resp := act.ToMap()
	data, _ := json.Marshal(resp)
	return mcp.NewToolResultText(string(data)), nil
}

func (s *Server) handleSubagentList(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	statusFilter := req.GetString("status", "all")
	roleFilter := req.GetString("role", "")

	actors := s.bus.List(statusFilter, roleFilter)
	activeCount := 0
	listData := make([]map[string]any, len(actors))
	for i, a := range actors {
		if a.Status() == actor.StatusRunning {
			activeCount++
		}
		listData[i] = a.ToMap()
	}

	resp := map[string]any{
		"total":     len(listData),
		"active":    activeCount,
		"subagents": listData,
	}
	data, _ := json.Marshal(resp)
	return mcp.NewToolResultText(string(data)), nil
}

func (s *Server) handleSubagentReap(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	maxAgeSec := req.GetInt("max_age_sec", 3600)
	reaped := s.bus.Reap(maxAgeSec)

	resp := map[string]any{
		"success":         true,
		"reaped_count":    reaped,
		"remaining_count": s.bus.Count(),
	}
	data, _ := json.Marshal(resp)
	return mcp.NewToolResultText(string(data)), nil
}
