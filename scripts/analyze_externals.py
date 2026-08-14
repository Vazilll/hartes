import os
import sys
import json
import requests
from vazus_core.engine.utils import load_adapter_key

def analyze():
    print("Gathering external snippets via fast keyword search...")
    jsonl_path = "C:/vazus/pyenv/leann-indexes/external_repos.leann.passages.jsonl"
    
    keywords = ["memory", "episodic", "checkpoint", "routing", "predictive", "recursive", "reflection", "self-edit", "router"]
    snippets = []
    
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                text = json.loads(line).get("text", "")
                text_lower = text.lower()
                matches = sum(1 for kw in keywords if kw in text_lower)
                if matches >= 2:
                    snippets.append((matches, text))
    except Exception as e:
        print(f"Error reading {jsonl_path}: {e}")
        return

    # Sort by number of keyword matches and take top 15
    snippets.sort(key=lambda x: x[0], reverse=True)
    top_snippets = [s[1] for s in snippets[:15]]
    
    context = "\n\n---\n".join(top_snippets)
    print(f"Extracted {len(top_snippets)} relevant snippets.")
    
    print("Synthesizing analysis via Gemini Pro...")
    prompt = """You are the Lead AI Architect.
We are building NEXUS (a unified multi-agent system with RLM reasoning, LeANN hybrid search, and predictive routing).
I have downloaded 7 open-source repositories from Google Research and MIT (ReasoningBank, Concordia, pyrlm-runtime, SEAL, etc.).

Below are top snippets extracted from their source code based on key architectural queries (memory, routing, recursion, self-editing).
Please analyze these snippets and compare them to our NEXUS architecture.
Identify 3-5 specific algorithms, code structures, or concepts from these snippets that we should transplant into our NEXUS core right now.
Provide actionable bullet points with file/repo references where possible.
"""
    
    payload = {
        "model": "gemini-3.1-pro",
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": context}
        ],
        "temperature": 0.3
    }
    
    headers = {"Authorization": f"Bearer {load_adapter_key()}"}
    resp = requests.post("http://127.0.0.1:5001/v1/chat/completions", json=payload, headers=headers)
    resp.raise_for_status()
    
    answer = resp.json()["choices"][0]["message"]["content"]
    
    out_path = "C:/Users/Vaz/.gemini/antigravity-ide/brain/3e506a9a-18fb-47f3-8c54-5e5eff419e58/external_architecture_comparison.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(answer)
        
    print(f"Analysis saved to {out_path}")

if __name__ == "__main__":
    analyze()
