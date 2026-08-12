import glob
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

tg_dir = r"C:\vazus\knowledge\telegram_messages"
jsonl_files = glob.glob(os.path.join(tg_dir, "*.jsonl"))

for f in jsonl_files:
    fname = os.path.basename(f)
    md_name = fname.replace('.jsonl', '.md')
    md_path = os.path.join(tg_dir, md_name)
    
    with open(f, 'r', encoding='utf-8') as jf:
        json_lines = [json.loads(line) for line in jf if line.strip()]
        
    print(f"=== {fname} ===")
    print(f"Total JSONL records: {len(json_lines)}")
    if json_lines:
        print("Sample 0:", json_lines[0])
        print("Sample 1:", json_lines[1])
        print("Sample -1:", json_lines[-1])
        
    if os.path.exists(md_path):
        with open(md_path, 'r', encoding='utf-8') as mf:
            md_content = mf.read()
        print(f"MD file size: {len(md_content)} bytes")
    else:
        print("MD file DOES NOT EXIST!")
    print("\n" + "="*50)
