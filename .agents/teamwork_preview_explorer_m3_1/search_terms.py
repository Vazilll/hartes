import os
import re

terms = ['ThesisNode', 'ProtocolNode', 'CAUSES', 'REQUIRES', 'CONTRADICTS', 'Zettelkasten', 'Obsidian', 'wiki', 'kg_nodes', 'kg_edges']

root_dir = r'C:\vazus'

matches = {}

for root, dirs, files in os.walk(root_dir):
    if '.venv' in root or '.git' in root or '__pycache__' in root:
        continue
    for f in files:
        if f.endswith('.py') or f.endswith('.md') or f.endswith('.sql'):
            fpath = os.path.join(root, f)
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as fp:
                    content = fp.read()
                    for term in terms:
                        if term in content:
                            if term not in matches:
                                matches[term] = []
                            matches[term].append(fpath)
            except Exception as e:
                pass

print("=== Search Term Matches in Codebase ===")
for term, files in matches.items():
    print(f"\n--- Term: {term} ({len(files)} files) ---")
    for f in files[:10]:
        print(" ", f)
