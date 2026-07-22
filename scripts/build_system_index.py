#!/usr/bin/env python3
"""Build dnts-full-system leann index from all project code."""
import sys, json
from pathlib import Path

sys.path.insert(0, 'C:/vazus/pyenv')

SKIP_DIRS = {".venv", "__pycache__", ".git", "node_modules", "study",
             ".agents", ".claude", "_archive", "third_party"}

ROOTS = [
    ("vazus_core", Path("C:/vazus/pyenv/vazus_core"), [".py", ".md", ".json", ".yaml"]),
    ("scripts",   Path("C:/vazus/pyenv/scripts"),   [".py", ".md", ".json", ".yaml"]),
    ("gomcp",     Path("C:/vazus/pyenv/gomcp/tools"),[".go", ".md"]),
    ("dnts-hub",  Path("D:/dnts"),                 [".py", ".md"]),
]

import ast

def chunk_python(text: str, file_identifier: str) -> list[str]:
    chunks = []
    try:
        module = ast.parse(text)
    except SyntaxError:
        return chunk_generic(text, file_identifier)

    lines = text.splitlines()
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = node.lineno - 1
            if hasattr(node, 'decorator_list') and node.decorator_list:
                start = node.decorator_list[0].lineno - 1
            end = getattr(node, 'end_lineno', len(lines))
            chunk = "\n".join(lines[start:end])
            if len(chunk.strip()) > 10:
                chunks.append(f"# {file_identifier} [{node.name}]\n{chunk}")
    
    if not chunks and text.strip():
        return chunk_generic(text, file_identifier)
        
    return chunks

def chunk_generic(text: str, file_identifier: str, max_lines=50, overlap=10) -> list[str]:
    chunks = []
    lines = text.splitlines()
    if not lines: return chunks
    for i in range(0, len(lines), max_lines - overlap):
        chunk = "\n".join(lines[i:i + max_lines])
        if len(chunk.strip()) > 10:
            chunks.append(f"# {file_identifier}\n{chunk}")
    return chunks

passages = []
for prefix, root, exts in ROOTS:
    if not root.exists():
        sys.stderr.write(f"SKIP {root}\n")
        continue
    c = 0
    for fpath in root.rglob("*"):
        try:
            if not fpath.is_file():
                continue
        except OSError:
            continue
        if any(p in SKIP_DIRS for p in fpath.parts):
            continue
        if fpath.suffix not in exts or fpath.stat().st_size > 100_000:
            continue
        
        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
            
        file_identifier = f"{prefix}/{fpath.name}"
        if fpath.suffix == ".py":
            file_chunks = chunk_python(text, file_identifier)
        else:
            file_chunks = chunk_generic(text, file_identifier)
            
        passages.extend(file_chunks)
        c += 1
    sys.stderr.write(f"  {prefix}: {c} files\n")

sys.stderr.write(f"Total chunks: {len(passages)}\n")

# Write ALL passages to JSONL at once
out_path = Path("C:/vazus/pyenv/leann-indexes/dnts-full-system.leann.passages.jsonl")
out_path.parent.mkdir(parents=True, exist_ok=True)

with open(out_path, "w", encoding="utf-8") as f:
    for text in passages:
        f.write(json.dumps({"text": text}, ensure_ascii=False) + "\n")

sys.stderr.write(f"Written: {out_path}\n")
sys.stderr.write(f"Size: {out_path.stat().st_size // 1024} KB\n")
sys.stderr.write(f"DONE: {len(passages)} passages\n")
