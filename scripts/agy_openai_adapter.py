import asyncio
import json
import uuid
import time
from fastapi import FastAPI, Request
import uvicorn
import shutil

app = FastAPI(title="Antigravity OpenAI-Compatible Adapter")

# Resolve agy path
import os
AGY_PATH = shutil.which("agy")
if not AGY_PATH:
    for p in [
        r"C:\Users\Vaz\AppData\Local\agy\bin\agy.exe",
        r"C:\vazus\pyenv\.venv\Scripts\agy.exe",
        r"C:\vazus\pyenv\.venv\Scripts\agy",
    ]:
        if os.path.isfile(p):
            AGY_PATH = p
            break

if not AGY_PATH:
    raise RuntimeError("agy binary not found!")

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    data = await request.json()
    with open('C:/vazus/scratch/last_request.json', 'w') as f:
        json.dump(data, f, indent=2)
        
    messages = data.get("messages", [])
    model = data.get("model", "gemini-3.5-flash")
    
    tools = data.get("tools", [])
    tool_choice = data.get("tool_choice")
    response_format = data.get("response_format")
    
    prompt = ""
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        prompt += f"{role.upper()}:\n{content}\n\n"
        
    requested_tool_name = None
    extracted_schema = None
    is_json_schema = response_format and response_format.get("type") == "json_schema"
    
    if tools:
        if isinstance(tool_choice, dict) and "function" in tool_choice:
            requested_tool_name = tool_choice["function"]["name"]
        else:
            requested_tool_name = tools[0]["function"]["name"]
            
        tool_schema = next((t for t in tools if t["function"]["name"] == requested_tool_name), tools[0])
        extracted_schema = tool_schema.get("function", {}).get("parameters", {})
        prompt += f"\n\n[SYSTEM]: You MUST respond by calling the function '{requested_tool_name}'. "
        prompt += f"Output ONLY a raw, valid JSON object representing the arguments to the function, and nothing else (no markdown, no backticks). "
        prompt += f"Schema: {json.dumps(tool_schema)}\n"
    elif is_json_schema:
        extracted_schema = response_format.get("json_schema", {}).get("schema", {})
        prompt += "\n\n[SYSTEM]: You MUST output ONLY a valid JSON object matching the following schema. No markdown, no backticks.\n"
        prompt += f"Schema: {json.dumps(extracted_schema)}\n"
    elif response_format and response_format.get("type") == "json_object":
        prompt += "\n\n[SYSTEM]: You MUST output ONLY a valid JSON object. No markdown, no backticks.\n"

    print(f"[Adapter] Incoming request. Extracted prompt length: {len(prompt)}")
    # Run the agy CLI tool
    cmd = [
        AGY_PATH,
        "-p", "-",
        "--model", "gemini-3.6-flash",
        "--effort", "high",
        "--print-timeout", "300s",
        "--dangerously-skip-permissions",
        "--output-format", "text"
    ]
    
    env = os.environ.copy()
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(input=prompt.encode('utf-8')), timeout=300.0)
        response_text = stdout.decode('utf-8', errors='replace').strip()
        
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        response_id = f"chatcmpl-{uuid.uuid4().hex}"
        created_time = int(time.time())
        
        message_obj = {"role": "assistant"}
        
        # Helper to wrap text into JSON based on schema
        def wrap_json_fallback(text, schema):
            text = text.strip('"').strip("'")
            props = schema.get("properties", {}) if schema else {}
            if props:
                first_prop = list(props.keys())[0]
                return json.dumps({first_prop: text})
            return json.dumps({"output": text})

        if tools:
            try:
                parsed = json.loads(response_text)
                if not isinstance(parsed, dict):
                    raise ValueError("Not a JSON object")
                arguments_json = response_text
            except Exception:
                arguments_json = wrap_json_fallback(response_text, extracted_schema)
                    
            message_obj["content"] = None
            message_obj["tool_calls"] = [
                {
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "type": "function",
                    "function": {
                        "name": requested_tool_name,
                        "arguments": arguments_json
                    }
                }
            ]
        else:
            is_json_format = response_format and response_format.get("type") in ["json_object", "json_schema"]
            if is_json_format:
                try:
                    parsed = json.loads(response_text)
                    if not isinstance(parsed, dict):
                        raise ValueError("Not a JSON object")
                    message_obj["content"] = response_text
                except Exception:
                    message_obj["content"] = wrap_json_fallback(response_text, extracted_schema)
            else:
                message_obj["content"] = response_text

        return {
            "id": response_id,
            "object": "chat.completion",
            "created": created_time,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": message_obj,
                    "finish_reason": "tool_calls" if tools else "stop"
                }
            ],
            "usage": {
                "prompt_tokens": len(prompt) // 4,
                "completion_tokens": len(response_text) // 4,
                "total_tokens": (len(prompt) + len(response_text)) // 4
            }
        }
    except asyncio.TimeoutError:
        proc.kill()
        return {"error": {"message": "Antigravity CLI timed out", "type": "timeout_error"}}

if __name__ == "__main__":
    port = int(os.environ.get("AGY_ADAPTER_PORT", 5001))
    print(f"Starting Antigravity OpenAI-Compatible Adapter on port {port}...")
    print(f"Using agy path: {AGY_PATH}")
    uvicorn.run(app, host="127.0.0.1", port=port)
