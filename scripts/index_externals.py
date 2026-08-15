import os
import json
from pathlib import Path
import time

EXTERNALS_DIR = Path("C:/vazus/pyenv/external_repos")
OUT_JSONL = Path("C:/vazus/pyenv/leann-indexes/external_repos.leann.passages.jsonl")

def chunk_text(text, max_chars=1500):
    chunks = []
    lines = text.split("\n")
    current_chunk = []
    current_len = 0
    for line in lines:
        if current_len + len(line) > max_chars and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_len = len(line)
        else:
            current_chunk.append(line)
            current_len += len(line) + 1
    if current_chunk:
        chunks.append("\n".join(current_chunk))
    return chunks

def build_index():
    print("Finding python files...", flush=True)
    passages = []
    total_files = 0
    for root, _, files in os.walk(EXTERNALS_DIR):
        for f in files:
            if f.endswith(".py"):
                path = Path(root) / f
                try:
                    with open(path, "r", encoding="utf-8") as f_in:
                        content = f_in.read()
                    
                    if not content.strip():
                        continue
                    
                    # Create chunks
                    repo_name = path.parts[len(EXTERNALS_DIR.parts)]
                    chunks = chunk_text(content)
                    for i, chunk in enumerate(chunks):
                        header = f"Repo: {repo_name} | File: {path.name} | Part: {i+1}\n"
                        passages.append(header + chunk)
                    total_files += 1
                except Exception:
                    pass

    print(f"Read {total_files} files into {len(passages)} passages.", flush=True)
    
    with open(OUT_JSONL, "w", encoding="utf-8") as f_out:
        for p in passages:
            f_out.write(json.dumps({"text": p}, ensure_ascii=False) + "\n")
            
    print(f"Saved passages to {OUT_JSONL}", flush=True)

if __name__ == "__main__":
    t0 = time.time()
    build_index()
    print(f"Done in {time.time()-t0:.2f}s")
