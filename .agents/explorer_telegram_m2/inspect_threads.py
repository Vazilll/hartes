import glob
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

tg_msg_dir = r"C:\vazus\knowledge\telegram_messages"
jsonl_files = glob.glob(os.path.join(tg_msg_dir, "*.jsonl"))

print("=== INSPECTING REPLIES IN JSONL & MD ===")

for f in jsonl_files:
    fname = os.path.basename(f)
    md_path = f.replace('.jsonl', '.md')
    print(f"\n=================== {fname} ===================")
    
    with open(f, 'r', encoding='utf-8') as jf:
        messages = [json.loads(line) for line in jf if line.strip()]
        
    print(f"Total messages in {fname}: {len(messages)}")
    
    # Check text patterns for reply indications
    quotes_count = 0
    id_ref_count = 0
    re_count = 0
    reply_to_field_count = 0
    
    samples = []
    
    for msg in messages:
        txt = msg.get('text', '')
        if 'reply_to_msg_id' in msg:
            reply_to_field_count += 1
            
        if txt.startswith('>'):
            quotes_count += 1
            if len(samples) < 5:
                samples.append(('Blockquote >', msg['id'], txt[:150]))
        if re.search(r'\[(ID|msg):\s*\d+\]', txt, re.IGNORECASE) or re.search(r'\(ID:\s*\d+\)', txt):
            id_ref_count += 1
            if len(samples) < 5:
                samples.append(('ID ref', msg['id'], txt[:150]))
        if txt.lower().startswith('re:') or 'ответ на' in txt.lower() or 'в ответ' in txt.lower():
            re_count += 1
            if len(samples) < 5:
                samples.append(('Re/Ответ', msg['id'], txt[:150]))

    print(f"  reply_to_msg_id JSON field count: {reply_to_field_count}")
    print(f"  Blockquotes ('>'): {quotes_count}")
    print(f"  ID references: {id_ref_count}")
    print(f"  Re/Ответ phrases: {re_count}")
    print("  Samples found:")
    for cat, mid, snippet in samples:
        print(f"    - [{cat}] Msg {mid}: {snippet.replace(chr(10), ' ')}")

    # Check Markdown file for reply indications
    if os.path.exists(md_path):
        with open(md_path, 'r', encoding='utf-8') as mf:
            md_text = mf.read()
        md_quotes = len(re.findall(r'^\s*>', md_text, re.MULTILINE))
        md_replies = len(re.findall(r'reply|ответ', md_text, re.IGNORECASE))
        print(f"  MD file blockquotes count: {md_quotes}")
        print(f"  MD file reply keywords count: {md_replies}")

