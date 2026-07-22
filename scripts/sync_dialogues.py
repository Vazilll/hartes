import os
import json
import re
import sys
from datetime import datetime

# Reconfigure stdout/stderr to UTF-8 to prevent encoding errors on Windows console
try:
    if sys.stdout:
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr:
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

BRAIN_DIR = r"C:\Users\Vaz\.gemini\antigravity-cli\brain"
OUTPUT_DIR = r"G:\Мой диск\ai\dialogues cli"

def clean_filename(name):
    # Remove invalid characters for Windows filenames
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    # Replace newlines and tabs with spaces
    name = re.sub(r'\s+', " ", name)
    name = name.strip()
    # Limit length
    if len(name) > 60:
        name = name[:57] + "..."
    return name

def extract_user_request(content):
    if not content:
        return ""
    match = re.search(r'<USER_REQUEST>(.*?)</USER_REQUEST>', content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return content.strip()

def format_timestamp(ts_str):
    if not ts_str:
        return ""
    try:
        dt = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return ts_str

def process_transcript(conv_id):
    conv_path = os.path.join(BRAIN_DIR, conv_id)
    logs_dir = os.path.join(conv_path, ".system_generated", "logs")
    transcript_path = os.path.join(logs_dir, "transcript.jsonl")
    
    if not os.path.exists(transcript_path):
        return
        
    messages = []
    first_user_request = ""
    first_timestamp = None
    
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    step = json.loads(line)
                except Exception:
                    continue
                
                step_type = step.get("type")
                created_at = step.get("created_at")
                
                if step_type == "USER_INPUT":
                    content = extract_user_request(step.get("content", ""))
                    if content:
                        if not first_user_request:
                            first_user_request = content
                        if not first_timestamp and created_at:
                            first_timestamp = created_at
                        messages.append({
                            "role": "user",
                            "time": format_timestamp(created_at),
                            "content": content
                        })
                elif step_type == "PLANNER_RESPONSE" and "content" in step:
                    content = step.get("content", "").strip()
                    if content:
                        messages.append({
                            "role": "assistant",
                            "time": format_timestamp(created_at),
                            "content": content
                        })
    except Exception as e:
        print(f"Error reading {transcript_path}: {e}")
        return

    if not messages:
        return
        
    date_str = "unknown_date"
    if first_timestamp:
        try:
            date_str = first_timestamp.split("T")[0]
        except Exception:
            pass
    else:
        try:
            mtime = os.path.getmtime(transcript_path)
            date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
        except Exception:
            pass
            
    preview = clean_filename(first_user_request) if first_user_request else "empty"
    if not preview:
        preview = "untitled"
    short_id = conv_id[:8]
    filename = f"{date_str} - {preview} - {short_id}.md"
    output_path = os.path.join(OUTPUT_DIR, filename)
    
    md_lines = []
    title = first_user_request[:100].replace("\n", " ") if first_user_request else "Диалог"
    md_lines.append(f"# {title}")
    md_lines.append(f"*ID сессии: {conv_id}*")
    md_lines.append(f"*Дата начала: {format_timestamp(first_timestamp) if first_timestamp else 'Неизвестно'}*")
    md_lines.append("\n---\n")
    
    for msg in messages:
        if msg["role"] == "user":
            md_lines.append(f"### 👤 Пользователь ({msg['time']})")
            md_lines.append(msg["content"])
        else:
            md_lines.append(f"### 🤖 Ассистент (Antigravity) ({msg['time']})")
            md_lines.append(msg["content"])
        md_lines.append("\n---\n")
        
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as out_f:
            out_f.write("\n".join(md_lines))
        print(f"Synced: {filename}")
    except Exception as e:
        print(f"Error writing to {output_path}: {e}")

def main():
    if not os.path.exists(BRAIN_DIR):
        print(f"Brain directory {BRAIN_DIR} not found.")
        return
        
    print("Starting dialogue synchronization...")
    conv_ids = [d for d in os.listdir(BRAIN_DIR) if os.path.isdir(os.path.join(BRAIN_DIR, d))]
    for cid in conv_ids:
        process_transcript(cid)
    print("Synchronization finished successfully.")

if __name__ == "__main__":
    main()
