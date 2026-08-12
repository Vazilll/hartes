import glob
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

tg_msg_dir = r"C:\vazus\knowledge\telegram_messages"
jsonl_files = glob.glob(os.path.join(tg_msg_dir, "*.jsonl"))

for f in jsonl_files:
    fname = os.path.basename(f)
    with open(f, 'r', encoding='utf-8') as jf:
        msgs = [json.loads(l) for l in jf if l.strip()]
        
    ids = [m['id'] for m in msgs]
    dates = [m['date'] for m in msgs]
    senders = set(m['sender'] for m in msgs)
    
    print(f"=== {fname} ===")
    print(f"  Count: {len(msgs)}")
    print(f"  ID range: min={min(ids)}, max={max(ids)}")
    print(f"  ID ordering: {'Decreasing' if ids[0] > ids[-1] else 'Increasing'}")
    print(f"  Date range: {min(dates)} to {max(dates)}")
    print(f"  Unique senders ({len(senders)}): {list(senders)[:10]}")
    print()
