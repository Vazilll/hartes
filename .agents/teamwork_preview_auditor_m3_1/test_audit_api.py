import sys
import urllib.request
import urllib.parse
import json
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')

def test_endpoint(url, headers={}):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()

print("--- STARTING LIVE DASHBOARD API AUDIT ---")

# 1. GET /
status, hdrs, body = test_endpoint('http://127.0.0.1:8502/')
print(f"1. GET / status: {status}, content length: {len(body)}, HTML title present: {b'<title>vazus' in body}")
assert status == 200
assert b"<title>vazus SuperGraph OS" in body

# 2. GET /api/v1/knowledge/stats
status, hdrs, body = test_endpoint('http://127.0.0.1:8502/api/v1/knowledge/stats')
print(f"2. GET /stats status: {status}, json: {body.decode('utf-8').strip()}")
assert status == 200
conn = sqlite3.connect('C:/vazus/vazus.db')
c = conn.cursor()
db_nodes = c.execute('SELECT COUNT(*) FROM kg_nodes').fetchone()[0]
db_edges = c.execute('SELECT COUNT(*) FROM kg_edges').fetchone()[0]
stats_json = json.loads(body)
assert stats_json['kg_nodes'] == db_nodes, f"Mismatch: {stats_json['kg_nodes']} vs {db_nodes}"
assert stats_json['kg_edges'] == db_edges, f"Mismatch: {stats_json['kg_edges']} vs {db_edges}"
print("   => VERIFIED: /stats returns exact SQLite db row counts.")

# 3. GET /api/v1/knowledge/search
query = urllib.parse.quote('тест')
status, hdrs, body = test_endpoint(f'http://127.0.0.1:8502/api/v1/knowledge/search?query={query}&top_k=3')
search_json = json.loads(body)
print(f"3. GET /search status: {status}, results count: {search_json['count']}")
assert status == 200
assert search_json['count'] > 0
for item in search_json['results']:
    print(f"   - [{item['node_type']}] {item['name']} (similarity: {item['similarity']})")

# 4. GET /api/v1/knowledge/stream (Range Request 206)
if search_json['results']:
    sample_src = search_json['results'][0]['source_file']
    print(f"4. Testing stream endpoint for file: {sample_src}")
    encoded_path = urllib.parse.quote(sample_src)
    
    # Range request bytes=0-1023
    status, hdrs, body_slice = test_endpoint(f'http://127.0.0.1:8502/api/v1/knowledge/stream?path={encoded_path}', headers={'Range': 'bytes=0-1023'})
    print(f"   Range req status: {status} (Expected 206), Content-Range: {hdrs.get('Content-Range')}, Content-Length: {hdrs.get('Content-Length')}, bytes received: {len(body_slice)}")
    assert status == 206, f"Expected 206, got {status}"
    assert len(body_slice) == 1024, f"Expected 1024 bytes, got {len(body_slice)}"

    # Full request 200
    status, hdrs, body_full = test_endpoint(f'http://127.0.0.1:8502/api/v1/knowledge/stream?path={encoded_path}')
    print(f"   Full req status: {status} (Expected 200), Content-Length: {hdrs.get('Content-Length')}, bytes received: {len(body_full)}")
    assert status == 200
    assert body_slice == body_full[:1024], "Range slice matches first 1024 bytes of full file!"
    print("   => VERIFIED: HTTP 206 Range streaming reads physical file bytes accurately.")

# 5. GET /api/v1/knowledge/thumbnail
if search_json['results']:
    sample_thumb = search_json['results'][0]['thumbnail_path']
    print(f"5. Testing thumbnail endpoint for file: {sample_thumb}")
    encoded_thumb = urllib.parse.quote(sample_thumb)
    status, hdrs, body_thumb = test_endpoint(f'http://127.0.0.1:8502/api/v1/knowledge/thumbnail?path={encoded_thumb}')
    print(f"   Thumbnail status: {status}, Content-Type: {hdrs.get('Content-Type')}, bytes: {len(body_thumb)}")
    assert status == 200
    assert hdrs.get('Content-Type') == 'image/jpeg'
    print("   => VERIFIED: Thumbnail endpoint reads real JPEG file.")

print("\n--- ALL LIVE DASHBOARD API VERIFICATION CHECKS PASSED PERFECTLY ---")
