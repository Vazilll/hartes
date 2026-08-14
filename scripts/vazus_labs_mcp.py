import sys
import os
import socket
import asyncio
import tempfile
import uuid
import subprocess
import shutil
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("vazus-labs")

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

@mcp.tool()
async def vazus_labs_dispatch(role: str, task: str, complexity: str = "high", max_iterations: int = 3) -> str:
    """
    Dispatch a laboratory AI agent (e.g. 'rlm_code_engineer') for asynchronous parallel execution.
    This creates a 100% isolated core with its own dynamic port and temp environment.
    """
    if role not in ["rlm_code_engineer", "open_deep_researcher"]:
        return f"Error: Unknown role '{role}'"
        
    print(f"[vazus-labs] Launching completely isolated {role} core for task: {task[:30]}...")

    if role == "rlm_code_engineer":
        port = get_free_port()
        env = os.environ.copy()
        env["AGY_ADAPTER_PORT"] = str(port)
        env["OPENAI_BASE_URL"] = f"http://127.0.0.1:{port}/v1"
        env["OPENAI_API_KEY"] = "sk-antigravity-local"
        # Use an isolated temp directory for this specific core to prevent file collisions
        temp_dir = tempfile.mkdtemp(prefix=f"vazus_{role}_{uuid.uuid4().hex[:8]}_")
        env["TMP"] = temp_dir
        env["TEMP"] = temp_dir
        
        adapter_proc = None
        try:
            # 1. Start the personal isolated proxy core
            python_exe = sys.executable
            adapter_proc = await asyncio.create_subprocess_exec(
                python_exe, "C:/vazus/scripts/agy_openai_adapter.py",
                env=env,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            
            # Give it a second to boot up on the new port
            await asyncio.sleep(2.0)
            
            # 2. Start the laboratory agent script
            agent_proc = await asyncio.create_subprocess_exec(
                python_exe, "C:/vazus/scripts/subagent_rlm_bridge.py",
                "--prompt", task,
                "--complexity", complexity,
                "--max-iterations", str(max_iterations),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await agent_proc.communicate()
            
            out_str = stdout.decode("utf-8", errors="replace")
            err_str = stderr.decode("utf-8", errors="replace")
            
            if agent_proc.returncode == 0:
                return f"=== ISOLATED AGENT CORE: {role} (SUCCESS) ===\n{out_str}"
            else:
                return f"=== ISOLATED AGENT CORE: {role} (FAILED) ===\nSTDOUT: {out_str}\nSTDERR: {err_str}"
                
        except Exception as e:
            return f"Error executing isolated core for {role}: {e}"
            
        finally:
            try:
                if 'agent_proc' in locals() and agent_proc:
                    agent_proc.kill()
            except:
                pass
            if adapter_proc:
                try:
                    adapter_proc.kill()
                except:
                    pass
            try:
                if 'temp_dir' in locals() and os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass

    elif role == "open_deep_researcher":
        port = get_free_port()
        env = os.environ.copy()
        env["AGY_ADAPTER_PORT"] = str(port)
        env["OPENAI_BASE_URL"] = f"http://127.0.0.1:{port}/v1"
        env["OPENAI_API_KEY"] = "sk-antigravity-local"
        temp_dir = tempfile.mkdtemp(prefix=f"vazus_{role}_{uuid.uuid4().hex[:8]}_")
        env["TMP"] = temp_dir
        env["TEMP"] = temp_dir
        
        adapter_proc = None
        try:
            python_exe = sys.executable
            adapter_proc = await asyncio.create_subprocess_exec(
                python_exe, "C:/vazus/scripts/agy_openai_adapter.py",
                env=env,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            
            await asyncio.sleep(2.0)
            
            agent_proc = await asyncio.create_subprocess_exec(
                python_exe, "C:/vazus/scripts/subagent_research_bridge.py",
                "--query", task,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await agent_proc.communicate()
            
            out_str = stdout.decode("utf-8", errors="replace")
            err_str = stderr.decode("utf-8", errors="replace")
            
            if agent_proc.returncode == 0:
                return f"=== ISOLATED AGENT CORE: {role} (SUCCESS) ===\n{out_str}"
            else:
                return f"=== ISOLATED AGENT CORE: {role} (FAILED) ===\nSTDOUT: {out_str}\nSTDERR: {err_str}"
                
        except Exception as e:
            return f"Error executing isolated core for {role}: {e}"
            
        finally:
            try:
                if 'agent_proc' in locals() and agent_proc:
                    agent_proc.kill()
            except:
                pass
            if adapter_proc:
                try:
                    adapter_proc.kill()
                except:
                    pass
            try:
                if 'temp_dir' in locals() and os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass

if __name__ == "__main__":
    mcp.run()
