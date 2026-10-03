package main

import (
	"context"
	"flag"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"

	"github.com/mark3labs/mcp-go/server"

	"vazus/services/subagent_bus/internal/actor"
	subagentmcp "vazus/services/subagent_bus/internal/mcp"
)

const version = "vazus-subagent-bus 1.0.0 (Go Actor Model + MCP Gateway)"

func isForbiddenPath(cleanSlash string) bool {
	// 1. Invariant AGENTS.md (root or subpaths)
	if cleanSlash == "agents.md" || strings.HasSuffix(cleanSlash, "/agents.md") || strings.Contains(cleanSlash, "/agents.md/") {
		return true
	}

	// 2. Invariant .git directory and subpaths
	if cleanSlash == ".git" || strings.HasPrefix(cleanSlash, ".git/") || strings.Contains(cleanSlash, "/.git/") || strings.HasSuffix(cleanSlash, "/.git") {
		return true
	}

	// 3. Sensitive system directories: windows/system32
	if strings.Contains(cleanSlash, "windows/system32") {
		return true
	}

	// 4. Sensitive system directories: /etc/
	if cleanSlash == "etc" || cleanSlash == "/etc" ||
		strings.HasPrefix(cleanSlash, "etc/") || strings.HasPrefix(cleanSlash, "/etc/") ||
		strings.Contains(cleanSlash, "/etc/") || strings.HasSuffix(cleanSlash, "/etc") {
		return true
	}

	return false
}

func isPathAllowed(path string) bool {
	if path == "" {
		return true
	}

	// 1. Safe expansion of leading tilde before filepath.Abs.
	// Resolves ~, ~/.gemini, ~\.gemini, etc. on Windows where filepath.Abs
	// treats tildes as literal directory names relative to current working directory.
	if path == "~" {
		home, err := os.UserHomeDir()
		if err != nil {
			return false
		}
		path = home
	} else if strings.HasPrefix(path, "~/") || strings.HasPrefix(path, "~\\") {
		home, err := os.UserHomeDir()
		if err != nil {
			return false
		}
		path = filepath.Join(home, path[2:])
	}

	abs, err := filepath.Abs(path)
	if err != nil {
		return false
	}
	clean := strings.ToLower(filepath.Clean(abs))

	// Normalize Windows path separators and strip extended UNC / device prefixes
	cleanSlash := filepath.ToSlash(clean)
	cleanSlash = strings.TrimPrefix(cleanSlash, "//?/")
	cleanSlash = strings.TrimPrefix(cleanSlash, "//./")

	// 2. Reject invariant protected targets unconditionally (must strictly precede whitelist checks)
	if isForbiddenPath(cleanSlash) {
		return false
	}

	// 3. Allow C:\vazus root and subpaths with strict delimiter check
	if cleanSlash == "c:/vazus" || strings.HasPrefix(cleanSlash, "c:/vazus/") {
		return true
	}

	// 4. Allow ~/.gemini root and subpaths with strict delimiter check
	home, err := os.UserHomeDir()
	if err == nil {
		geminiPath := filepath.ToSlash(strings.ToLower(filepath.Clean(filepath.Join(home, ".gemini"))))
		geminiPath = strings.TrimPrefix(geminiPath, "//?/")
		geminiPath = strings.TrimPrefix(geminiPath, "//./")
		if cleanSlash == geminiPath || strings.HasPrefix(cleanSlash, geminiPath+"/") {
			return true
		}
	}

	return false
}

func main() {
	var (
		transport   string
		port        int
		sseAddr     string
		timeout     int
		workdir     string
		showVersion bool
	)

	flag.StringVar(&transport, "transport", "stdio", "Transport protocol to use: stdio or sse")
	flag.IntVar(&port, "port", 8085, "HTTP port for SSE transport")
	flag.StringVar(&sseAddr, "sse-addr", "", "Explicit SSE address to bind to (e.g. 127.0.0.1:8085)")
	flag.IntVar(&timeout, "timeout", 300, "Default actor execution timeout in seconds")
	flag.StringVar(&workdir, "workdir", "", "Working directory path constraint")
	flag.BoolVar(&showVersion, "version", false, "Print version information and exit")

	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "Usage: %s [flags]\n\nFlags:\n", os.Args[0])
		flag.PrintDefaults()
	}

	flag.Parse()

	if showVersion {
		fmt.Println(version)
		os.Exit(0)
	}

	// Fail-closed path jail verification
	if workdir != "" {
		if !isPathAllowed(workdir) {
			fmt.Fprintf(os.Stderr, "Error: access denied: path '%s' is outside workspace jail (C:\\vazus or ~/.gemini)\n", workdir)
			os.Exit(1)
		}
	}

	// Root context with graceful signal handling
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()

	// Initialize bus and MCP gateway
	bus := actor.NewSubagentBus(ctx)
	defer bus.Close()
	defer os.Stdout.Sync()

	mcpGateway := subagentmcp.NewServer(bus)

	if sseAddr != "" || transport == "sse" {
		addr := sseAddr
		if addr == "" {
			addr = fmt.Sprintf("127.0.0.1:%d", port)
		}
		sseServer := server.NewSSEServer(mcpGateway.MCPServer())
		fmt.Fprintf(os.Stderr, "[SubagentBus] Starting MCP SSE listener on http://%s/sse\n", addr)
		if err := sseServer.Start(addr); err != nil && err != http.ErrServerClosed {
			fmt.Fprintf(os.Stderr, "[SubagentBus] SSE Server error: %v\n", err)
			os.Exit(1)
		}
		return
	}

	// Default Stdio JSON-RPC 2.0 transport
	if err := server.ServeStdio(mcpGateway.MCPServer()); err != nil {
		fmt.Fprintf(os.Stderr, "[SubagentBus] Stdio Server exited with error: %v\n", err)
		os.Exit(1)
	}
	bus.Close()
	_ = os.Stdout.Sync()
	os.Exit(0)
}
