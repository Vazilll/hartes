"""
Empirical Adversarial Stress Harness for Milestone 2:
- Stdio JSON-RPC 2.0 Fuzzing & Protocol Error Codes
- Security Path Jail Traversal Penetration
- Python GoSubagentBusClient Resilience & Fallback Behavior
"""

import json
import os
import subprocess
import sys
import time
import pytest

BINARY_PATH = r"C:\vazus\bin\subagent_bus.exe"


class StdioMcpSession:
    """Manages a raw stdio connection to subagent_bus.exe."""
    def __init__(self, binary=BINARY_PATH, extra_args=None):
        cmd = [binary] + (extra_args or [])
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )

    def send_line(self, line: str) -> str:
        if self.proc.poll() is not None:
            return f"<PROCESS_EXITED_{self.proc.returncode}>"
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()
        out = self.proc.stdout.readline()
        return out.strip()

    def close(self):
        if self.proc.poll() is None:
            try:
                self.proc.stdin.close()
                self.proc.terminate()
                self.proc.wait(timeout=2)
            except Exception:
                self.proc.kill()


def test_fuzz_jsonrpc_protocol():
    """Fuzz stdio JSON-RPC inputs and verify standard error codes and zero crashes."""
    assert os.path.isfile(BINARY_PATH), f"Binary not found at {BINARY_PATH}"
    session = StdioMcpSession()

    try:
        # 1. Malformed JSON
        resp1 = session.send_line("{bad_json:")
        data1 = json.loads(resp1)
        assert data1.get("error", {}).get("code") == -32700, f"Expected -32700 for malformed JSON, got {data1}"

        # 2. Missing jsonrpc header
        resp2 = session.send_line(json.dumps({"id": 2, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}}))
        data2 = json.loads(resp2)
        # Should either return standard error code -32600 (invalid request) or handle
        print("Missing jsonrpc response:", data2)

        # 3. Unknown method
        resp3 = session.send_line(json.dumps({"jsonrpc": "2.0", "id": 3, "method": "non_existent_method", "params": {}}))
        data3 = json.loads(resp3)
        assert data3.get("error", {}).get("code") == -32601, f"Expected -32601 for unknown method, got {data3}"

        # 4. Unknown tool call
        resp4 = session.send_line(json.dumps({
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "ghost_tool_xyz", "arguments": {}}
        }))
        data4 = json.loads(resp4)
        # Should return error (either JSON-RPC error or tool error)
        assert "error" in data4 or data4.get("result", {}).get("isError") is True, f"Expected tool error, got {data4}"

        # 5. subagent_spawn with missing required fields
        resp5 = session.send_line(json.dumps({
            "jsonrpc": "2.0", "id": 5, "method": "tools/call",
            "params": {"name": "subagent_spawn", "arguments": {"prompt": "run test"}}
        }))
        data5 = json.loads(resp5)
        # Missing 'name'
        assert data5.get("result", {}).get("isError") is True or "error" in data5, f"Expected validation error for missing name, got {data5}"

        # 6. subagent_spawn with empty strings
        resp6 = session.send_line(json.dumps({
            "jsonrpc": "2.0", "id": 6, "method": "tools/call",
            "params": {"name": "subagent_spawn", "arguments": {"name": "", "prompt": ""}}
        }))
        data6 = json.loads(resp6)
        assert data6.get("result", {}).get("isError") is True or "error" in data6, f"Expected validation error for empty strings, got {data6}"

        # 7. subagent_spawn with negative timeout
        resp7 = session.send_line(json.dumps({
            "jsonrpc": "2.0", "id": 7, "method": "tools/call",
            "params": {"name": "subagent_spawn", "arguments": {"name": "neg_actor", "prompt": "test", "timeout_sec": -50}}
        }))
        data7 = json.loads(resp7)
        # Should succeed (defaults to 300) without crashing
        assert "result" in data7, f"Expected graceful handling of negative timeout, got {data7}"

        # 8. subagent_send_message with empty subagent_id
        resp8 = session.send_line(json.dumps({
            "jsonrpc": "2.0", "id": 8, "method": "tools/call",
            "params": {"name": "subagent_send_message", "arguments": {"subagent_id": "", "content": "hi"}}
        }))
        data8 = json.loads(resp8)
        assert data8.get("result", {}).get("isError") is True or "error" in data8, f"Expected error for empty subagent_id, got {data8}"

        # 9. subagent_send_message with non-existent subagent_id
        resp9 = session.send_line(json.dumps({
            "jsonrpc": "2.0", "id": 9, "method": "tools/call",
            "params": {"name": "subagent_send_message", "arguments": {"subagent_id": "non_existent_id", "content": "hi"}}
        }))
        data9 = json.loads(resp9)
        assert data9.get("result", {}).get("isError") is True or "error" in data9, f"Expected error for non-existent subagent_id, got {data9}"

        # 10. subagent_poll_events with empty subagent_id
        resp10 = session.send_line(json.dumps({
            "jsonrpc": "2.0", "id": 10, "method": "tools/call",
            "params": {"name": "subagent_poll_events", "arguments": {"subagent_id": ""}}
        }))
        data10 = json.loads(resp10)
        assert data10.get("result", {}).get("isError") is True or "error" in data10, f"Expected error for empty subagent_id in poll, got {data10}"

        # 11. subagent_cancel with empty subagent_id
        resp11 = session.send_line(json.dumps({
            "jsonrpc": "2.0", "id": 11, "method": "tools/call",
            "params": {"name": "subagent_cancel", "arguments": {"subagent_id": ""}}
        }))
        data11 = json.loads(resp11)
        assert data11.get("result", {}).get("isError") is True or "error" in data11, f"Expected error for empty cancel id, got {data11}"

        # 12. Post-fuzz recovery: verify server is fully operational
        resp_post = session.send_line(json.dumps({
            "jsonrpc": "2.0", "id": 12, "method": "tools/list", "params": {}
        }))
        data_post = json.loads(resp_post)
        assert "tools" in data_post.get("result", {}), f"Server failed to recover after fuzzing: {data_post}"
        assert session.proc.poll() is None, "Server process died after fuzzing"

    finally:
        session.close()


def test_path_jail_directory_traversals():
    """Verify Fail-Closed path jail strictly rejects all non-whitelisted paths."""
    forbidden = [
        r"C:\Windows",
        r"C:\Windows\System32",
        "C:\\",
        "D:\\",
        r"C:\Program Files",
        r"..\..\..\etc",
        r"C:\vazus\..\Windows",
        r"C:\vazus\..\..\..\Windows",
        "C:/vazus/../Windows",
        r"c:\vazus\..\windows\system32",
        r"C:\vazus\..",
        r"C:\vazus\..\..",
        r"\\?\C:\Windows",
        r"C:\vazus_evil",
        r"C:\vazus2",
        os.path.join(os.path.expanduser("~"), ".gemini_evil"),
    ]

    for p in forbidden:
        proc = subprocess.run([BINARY_PATH, "--workdir", p], input="", capture_output=True, text=True, timeout=5)
        # Should exit with code 1 and access denied
        assert proc.returncode == 1, f"Path traversal not blocked for {p}: exit code was {proc.returncode} (allowed into jail!)"
        assert "access denied" in proc.stderr.lower(), f"Expected access denied error for {p}, got: {proc.stderr}"


def test_python_adapter_resilience_missing_binary():
    """Verify GoSubagentBusClient and dispatcher handle missing binary gracefully."""
    from vazus_core.workers.subagent_auto_trigger import GoSubagentBusClient, SubagentBackgroundDispatcher, TaskSpec

    client = GoSubagentBusClient(binary_path=r"C:\nonexistent\subagent_bus.exe")
    assert not client.is_available()

    with pytest.raises(RuntimeError) as exc_info:
        client.call_tool("subagent_list", {})
    assert "not available" in str(exc_info.value)

    # Now verify SubagentBackgroundDispatcher cleanly falls back to subprocess when USE_GO_SUBAGENT_BUS=1
    old_env = os.environ.get("USE_GO_SUBAGENT_BUS")
    try:
        os.environ["USE_GO_SUBAGENT_BUS"] = "1"
        dispatcher = SubagentBackgroundDispatcher()
        dispatcher.go_client = client  # Point to unavailable client

        spec = TaskSpec(
            subagent_name="code_engineer",
            prompt="print('fallback test')",
            dry_run=True,  # dry run so we don't start heavy process
            background=True
        )
        handle = dispatcher.dispatch(spec)
        assert handle is not None
        assert handle.backend == "subprocess"
    finally:
        if old_env is None:
            os.environ.pop("USE_GO_SUBAGENT_BUS", None)
        else:
            os.environ["USE_GO_SUBAGENT_BUS"] = old_env


def test_python_adapter_resilience_killed_mid_session():
    """Verify GoSubagentBusClient recovers or errors cleanly when binary is killed mid-session."""
    from vazus_core.workers.subagent_auto_trigger import GoSubagentBusClient

    client = GoSubagentBusClient(binary_path=BINARY_PATH)
    assert client.is_available()

    # Call a tool to ensure process is booted
    res1 = client.call_tool("subagent_list", {})
    assert "subagents" in res1
    assert client._proc is not None

    # Kill process externally
    client._proc.kill()
    client._proc.wait(timeout=2)
    assert client._proc.poll() is not None

    # Next call should either cleanly raise RuntimeError and clean up proc, or re-spawn
    try:
        res2 = client.call_tool("subagent_list", {})
        # If it auto-respawned:
        assert "subagents" in res2
    except RuntimeError as e:
        # If it raised RuntimeError cleanly:
        assert "Go subagent bus" in str(e)
    finally:
        client.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
