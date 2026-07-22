#!/usr/bin/env python3
# C:\vazus\pyenv\scripts\agy_monitor_cli.py
import asyncio
import json
import sys
import os

# Force UTF-8 on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# ANSI colors
GREEN = "\033[92m"
PURPLE = "\033[95m"
CYAN = "\033[96m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"

async def monitor():
    url = "ws://localhost:8765"
    print(f"{BOLD}{CYAN}[System]{RESET} Connecting to Antigravity WebSocket Monitor at {url}...")
    
    while True:
        try:
            import websockets
            async with websockets.connect(url) as ws:
                print(f"{BOLD}{GREEN}[Connected]{RESET} Live monitoring started. Waiting for agents...")
                async for message in ws:
                    msg = json.loads(message)
                    m_type = msg.get("type")
                    data = msg.get("data", {})
                    
                    if m_type == "agent_started":
                        print(
                            f"\n{BOLD}{PURPLE}[Started]{RESET} Agent {data['id']} (Attempt {data['attempt']})\n"
                            f"  {BOLD}Prompt:{RESET} {data['prompt']}"
                        )
                    elif m_type == "agent_token":
                        # Print token streamed in real-time
                        sys.stdout.write(data["token"])
                        sys.stdout.flush()
                    elif m_type == "agent_finished":
                        print(
                            f"\n{BOLD}{GREEN}[Finished]{RESET} Agent {data['id']} execution complete.\n"
                            f"{'-' * 60}"
                        )
        except (ImportError, ModuleNotFoundError):
            print(f"{BOLD}{RED}[Error]{RESET} 'websockets' library is missing in this environment.")
            break
        except Exception as e:
            print(f"{BOLD}{RED}[Disconnected]{RESET} Connection lost ({str(e)}). Reconnecting in 3s...")
            await asyncio.sleep(3)

if __name__ == "__main__":
    try:
        asyncio.run(monitor())
    except KeyboardInterrupt:
        print(f"\n{BOLD}{CYAN}[System]{RESET} Monitor stopped.")
