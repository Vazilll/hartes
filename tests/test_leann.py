import sys
import os
sys.path.insert(0, r"C:\vazus")
sys.path.insert(0, r"C:\vazus\scripts")
import urllib.request
import json

req = urllib.request.Request('http://127.0.0.1:5010/search', data=b'{"query":"unified_search.go", "top_k":2}', headers={'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req).read()
data = json.loads(resp)
for i, r in enumerate(data.get('results', [])):
    print(f'Match {i+1} [Score: {r["score"]:.3f}]: {r["text"][:100]}...')
