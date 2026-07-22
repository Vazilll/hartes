import os
import sys
import json
import glob
import time
import socket
import subprocess
from pathlib import Path

# Try to import streamlit. If not installed, print a helpful message.
try:
    import streamlit as st
except ImportError:
    print("Error: Streamlit is not installed in the current environment.")
    print("Please install it using: C:/vazus/pyenv/.venv/Scripts/pip.exe install streamlit")
    sys.exit(1)

# Paths Configuration
WORKSPACE_DIR = Path("C:/vazus/pyenv")
LOGS_DIR = WORKSPACE_DIR / "logs"
MEMORY_INDEX_PATH = LOGS_DIR / "memory_index.json"
REGISTRY_PATH = WORKSPACE_DIR / "rlm_prompts.json"
MANIFEST_PATH = WORKSPACE_DIR / "rlm_tools" / "manifest.json"
ADAPTER_SCRIPT = WORKSPACE_DIR / "scripts" / "agy_openai_adapter.py"
PYTHON_EXE = WORKSPACE_DIR / ".venv" / "Scripts" / "python.exe"

# Sync codebase AST to SQLite dnts.db at startup
try:
    sys.path.append(str(WORKSPACE_DIR / "scripts"))
    import sync_ast_to_sqlite
    sync_ast_to_sqlite.sync()
except Exception as e:
    print(f"Startup database sync failed: {e}")

# 1. Page Configuration
st.set_page_config(
    page_title="AI Agent Scaffolding Monitor",
    page_icon="🍊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Premium Basalt/Titanium Theme CSS Injection
st.markdown("""
<style>
    /* Global Background and Colors */
    .stApp {
        background-color: #0f1011;
        color: #e3e4e6;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #151719;
        border-right: 1px solid #2d3035;
    }
    
    /* Headers styling */
    h1, h2, h3, h4, h5, h6 {
        color: #f1f2f4;
        font-weight: 600;
        letter-spacing: -0.02em;
    }
    
    /* Custom divider */
    .premium-divider {
        height: 1px;
        background: linear-gradient(90deg, rgba(226,135,67,0.1) 0%, rgba(45,48,53,1) 50%, rgba(226,135,67,0.1) 100%);
        margin: 20px 0;
    }
    
    /* Cards for Iterations */
    .iteration-card {
        background-color: #17181c;
        border: 1px solid #282a30;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }
    
    /* Badge styling */
    .badge-amber {
        background-color: rgba(226, 135, 67, 0.15);
        color: #e28743;
        border: 1px solid rgba(226, 135, 67, 0.3);
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: bold;
        display: inline-block;
    }
    
    .badge-green {
        background-color: rgba(46, 160, 67, 0.15);
        color: #3fb950;
        border: 1px solid rgba(46, 160, 67, 0.3);
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: bold;
        display: inline-block;
    }
    
    /* Console-style logs output */
    .console-box {
        background-color: #0b0c0d;
        border: 1px solid #1f2124;
        border-radius: 6px;
        font-family: 'Fira Code', 'Courier New', Courier, monospace;
        padding: 12px;
        color: #a9b2c3;
        font-size: 0.85rem;
        white-space: pre-wrap;
        margin-top: 10px;
    }

    /* Buttons styling */
    div.stButton > button {
        background-color: #1d1f21;
        color: #f1f2f4;
        border: 1px solid #33373e;
        border-radius: 6px;
        transition: all 0.2s ease;
    }
    div.stButton > button:hover {
        border-color: #e28743;
        color: #e28743;
        background-color: #242629;
    }
</style>
""", unsafe_allow_html=True)

# 3. Adapter Management Functions
def check_adapter_status():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(('127.0.0.1', 5001)) == 0

def stop_adapter():
    try:
        import psutil
        terminated_count = 0
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline')
                if cmdline and any('agy_openai_adapter.py' in part for part in cmdline):
                    proc.terminate()
                    terminated_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, FileNotFoundError):
                continue
        return f"Terminated {terminated_count} adapter processes via psutil."
    except Exception as e:
        try:
            powershell_exe = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
            if not os.path.exists(powershell_exe):
                powershell_exe = "powershell"
            cmd = [powershell_exe, "-Command", "Get-CimInstance Win32_Process -Filter \"CommandLine like '%agy_openai_adapter.py%'\" | ForEach-Object { $_.Terminate() }"]
            r = subprocess.run(cmd, capture_output=True, text=True)
            return f"Stopped adapter server via PowerShell Get-CimInstance. Output: {r.stdout.strip()} (psutil error: {e})"
        except Exception as ex:
            return f"Failed to stop adapter: {e} (Fallback error: {ex})"

def start_adapter():
    try:
        if not PYTHON_EXE.exists() or not ADAPTER_SCRIPT.exists():
            return "Error: Python executable or adapter script not found."
        subprocess.Popen([str(PYTHON_EXE), str(ADAPTER_SCRIPT)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "Start signal sent."
    except Exception as e:
        return f"Error starting adapter: {e}"

# 4. Sidebar Content
st.sidebar.markdown("<h2 style='text-align: center; color: #e28743;'>🍊 TELEMETRY</h2>", unsafe_allow_html=True)
st.sidebar.markdown("<div class='premium-divider'></div>", unsafe_allow_html=True)

# Adapter Status
is_active = check_adapter_status()
status_html = "<span class='badge-green'>RUNNING</span>" if is_active else "<span class='badge-amber'>STOPPED</span>"
st.sidebar.markdown(f"**OpenAI Adapter (Port 5001):** {status_html}", unsafe_allow_html=True)

col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("Start"):
        res = start_adapter()
        st.sidebar.toast(res)
        time.sleep(1.0)
        st.rerun()
with col2:
    if st.button("Stop"):
        res = stop_adapter()
        st.sidebar.toast(res)
        time.sleep(1.0)
        st.rerun()

st.sidebar.markdown("<div class='premium-divider'></div>", unsafe_allow_html=True)

# Project Info
st.sidebar.subheader("System Info")
st.sidebar.text(f"Workspace: {WORKSPACE_DIR}")
if REGISTRY_PATH.exists():
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        reg = json.load(f)
    st.sidebar.text(f"Prompt Size: {len(reg.get('RLM_SYSTEM_PROMPT', ''))} chars")

# Refresh Controls
st.sidebar.markdown("<div class='premium-divider'></div>", unsafe_allow_html=True)
if st.sidebar.button("↻ Force UI Refresh", use_container_width=True):
    st.rerun()

if st.sidebar.button("Sync Codebase AST to dnts.db", use_container_width=True):
    try:
        import sync_ast_to_sqlite
        sync_ast_to_sqlite.sync()
        st.sidebar.success("Database synchronized successfully!")
        time.sleep(1.0)
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Sync failed: {e}")

# 5. Main Title & Tabs
st.markdown("<h1 style='color: #f1f2f4;'>Agent Scaffolding & Evolution Monitor</h1>", unsafe_allow_html=True)
st.markdown("<p style='color: #8a8f98;'>Real-time analysis, memory consolidation, and rollout visualization</p>", unsafe_allow_html=True)
st.markdown("<div class='premium-divider'></div>", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["🚀 Live Rollout Monitor", "🧠 Memory Index", "🧬 System Prompts", "🛠️ Compiled Tools"])

# TAB 1: Live Rollout Monitor
with tab1:
    st.subheader("Trace Log Viewer")
    
    # Locate log files
    log_files = glob.glob(str(LOGS_DIR / "rlm_*.jsonl")) + glob.glob(str(LOGS_DIR / "eval_*.jsonl"))
    if not log_files:
        st.warning("No RLM execution logs found in logs/ directory.")
    else:
        # Sort by modification time (newest first)
        log_files.sort(key=os.path.getmtime, reverse=True)
        log_options = {os.path.basename(p): p for p in log_files}
        
        selected_log_name = st.selectbox("Select Rollout Log File:", list(log_options.keys()))
        selected_log_path = log_options[selected_log_name]
        
        # Read selected log file lines
        try:
            with open(selected_log_path, "r", encoding="utf-8") as f:
                lines = [json.loads(line) for line in f if line.strip()]
        except Exception as e:
            st.error(f"Error reading log file: {e}")
            lines = []
            
        if lines:
            metadata = lines[0] if lines[0].get("type") == "metadata" else {}
            iterations = [l for l in lines if l.get("type") == "iteration"]
            
            # Metadata Box
            if metadata:
                st.markdown(
                    f"**Model:** `{metadata.get('root_model')}` | "
                    f"**Max Depth:** `{metadata.get('max_depth')}` | "
                    f"**Timestamp:** `{metadata.get('timestamp')}`"
                )
            
            # Display each turn
            for it in iterations:
                iter_num = it.get("iteration")
                response = it.get("response", "")
                code_blocks = it.get("code_blocks", [])
                final_answer = it.get("final_answer")
                
                # Split response into planning / code if code block is present
                plan_text = response
                if "```repl" in response:
                    parts = response.split("```repl", 1)
                    plan_text = parts[0].strip()
                
                st.markdown(f"### Turn {iter_num}")
                
                # Plan Card
                st.markdown(f"""
                <div class="iteration-card">
                    <strong style="color: #e28743;">Reasoning & Plan:</strong><br/>
                    {plan_text.replace(chr(10), '<br/>')}
                </div>
                """, unsafe_allow_html=True)
                
                # Executed Code and Outputs
                if code_blocks:
                    for cb_idx, cb in enumerate(code_blocks):
                        code = cb.get("code", "")
                        res_obj = cb.get("result", {})
                        stdout = res_obj.get("stdout", "")
                        stderr = res_obj.get("stderr", "")
                        
                        st.markdown("**Executed REPL Code:**")
                        st.code(code, language="python")
                        
                        if stdout.strip() or stderr.strip():
                            st.markdown("**REPL Console Output:**")
                            console_content = ""
                            if stdout.strip():
                                console_content += stdout.strip()
                            if stderr.strip():
                                if console_content:
                                    console_content += "\n"
                                console_content += f"[ERROR] {stderr.strip()}"
                                
                            st.markdown(f"<div class='console-box'>{console_content}</div>", unsafe_allow_html=True)
                
                # Check for final answer in this iteration
                if final_answer:
                    st.markdown(f"<h4>Final Answer:</h4>", unsafe_allow_html=True)
                    st.success(final_answer)
                
                st.markdown("---")

# TAB 2: Memory Index
with tab2:
    st.subheader("Experience Replay Memory Index")
    
    if not MEMORY_INDEX_PATH.exists():
        st.warning("Memory index does not exist yet. Run the memory indexer first.")
    else:
        try:
            with open(MEMORY_INDEX_PATH, "r", encoding="utf-8") as f:
                index = json.load(f)
        except Exception as e:
            st.error(f"Error reading memory index: {e}")
            index = {}
            
        if index:
            st.metric("Total Indexed Trajectories", len(index))
            st.markdown("Below are successful agent runs stored in the memory index for Few-Shot prompting:")
            
            for task_id, entry in index.items():
                with st.expander(f"Task: `{task_id}`"):
                    st.markdown("**Original Prompt:**")
                    st.write(entry.get("prompt"))
                    st.markdown("**Few-shot Trajectory Trace:**")
                    st.code(entry.get("few_shot_trace"), language="markdown")
        else:
            st.info("Memory index is currently empty.")

# TAB 3: System Prompts
with tab3:
    st.subheader("Current Prompts & Configuration")
    
    if not REGISTRY_PATH.exists():
        st.error(f"Prompt registry not found at {REGISTRY_PATH}")
    else:
        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                registry = json.load(f)
        except Exception as e:
            st.error(f"Error reading prompt registry: {e}")
            registry = {}
            
        if registry:
            # Load registered tools to demonstrate expanded view
            tools_list = []
            if MANIFEST_PATH.exists():
                try:
                    tools_data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
                    for name, info in tools_data.items():
                        tools_list.append(f"- `{name}`: {info['description']}")
                except Exception:
                    pass
            
            custom_tools_text = "\n".join(tools_list) if tools_list else "None registered"
            custom_tools_section_val = f"### Custom tools available:\n{custom_tools_text}"
            
            raw_system_prompt = registry.get("RLM_SYSTEM_PROMPT", "")
            expanded_system_prompt = raw_system_prompt.replace("{custom_tools_section}", custom_tools_section_val)
            
            st.markdown("### Expanded System Prompt (With Injected Hebbian Tools)")
            st.code(expanded_system_prompt, language="markdown")
            
            st.markdown("### Raw Prompt Template")
            st.code(raw_system_prompt, language="markdown")
            
            st.markdown("### Orchestrator Addendum")
            st.code(registry.get("ORCHESTRATOR_ADDENDUM", ""), language="markdown")

# TAB 4: Compiled Tools
with tab4:
    st.subheader("Hebbian Compiled Tools Registry")
    
    if not MANIFEST_PATH.exists():
        st.info("No compiled tools manifest found. Build tools using 'compile_hebbian_tool' first.")
    else:
        try:
            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            st.error(f"Error reading tools manifest: {e}")
            manifest = {}
            
        if manifest:
            st.metric("Total Compiled Tools", len(manifest))
            
            for tool_name, info in manifest.items():
                with st.expander(f"🛠️ Tool: `{tool_name}` — {info.get('description')}"):
                    st.markdown(f"**Path:** `{info.get('path')}`")
                    st.markdown(f"**Source Log:** `{info.get('source_log')}`")
                    st.markdown(f"**Compiled At:** `{info.get('timestamp')}`")
                    
                    # Read and show compiled script code
                    script_path = WORKSPACE_DIR / info.get("path", "")
                    if script_path.exists():
                        st.markdown("**Python Source Code:**")
                        st.code(script_path.read_text(encoding="utf-8"), language="python")
                    else:
                        st.warning("Tool source code file missing.")
        else:
            st.info("Compiled tools manifest is currently empty.")
