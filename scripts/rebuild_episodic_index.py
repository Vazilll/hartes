import json
import os
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Load leann_search_direct to use normalize_memory_chunk
sys.path.insert(0, "C:/vazus/pyenv/scripts")
import leann_search_direct

INDEX_DIR = Path("C:/vazus/pyenv/leann-indexes")

def process_file(jsonl_path: Path):
    out_path = jsonl_path.with_name(jsonl_path.stem + ".episodic.jsonl")
    if out_path.exists():
        print(f"Skipping {jsonl_path.name}, episodic already exists.")
        return
        
    print(f"Normalizing {jsonl_path.name}...")
    lines = jsonl_path.read_text(encoding="utf-8").strip().split('\n')
    
    passages = []
    for line in lines:
        if not line.strip(): continue
        try:
            passages.append(json.loads(line).get("text", ""))
        except:
            pass
            
    print(f"  Found {len(passages)} passages. Normalizing concurrently...")
    
    episodic_passages = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(leann_search_direct.normalize_memory_chunk, passages)
        for i, norm_text in enumerate(results):
            episodic_passages.append({"text": norm_text})
            if (i+1) % 50 == 0:
                print(f"  Normalized {i+1}/{len(passages)}...")
                
    with open(out_path, "w", encoding="utf-8") as f:
        for p in episodic_passages:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
            
    print(f"  Saved episodic index to {out_path.name}")
    
    # We should also generate embeddings, but we'll let leann_search_direct do it lazily on next load 
    # if we switch LEANN_PASSAGES.

if __name__ == "__main__":
    for f in INDEX_DIR.glob("*.passages.jsonl"):
        process_file(f)
