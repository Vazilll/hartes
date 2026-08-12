import urllib.request
import urllib.parse
import threading
import time
import sys
from pathlib import Path

sys.path.insert(0, r"C:\vazus")
from scripts.dashboard import DashboardRequestHandler, ThreadedHTTPServer

def run_tests():
    server = ThreadedHTTPServer(('127.0.0.1', 8599), DashboardRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.5)

    base_url = 'http://127.0.0.1:8599'
    results = {}

    def fetch(url, headers=None, drain=True):
        req = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(req) as resp:
                data = resp.read() if drain else resp.read(1024)
                return resp.status, resp.reason, resp.headers, len(data)
        except urllib.error.HTTPError as e:
            return e.code, e.reason, e.headers, 0

    print("=== TEST 1: Mandatory Traversal Checks ===")
    
    # 1a. GET /api/v1/knowledge/stream?path=C:/Windows/win.ini
    st, msg, hdrs, _ = fetch(f"{base_url}/api/v1/knowledge/stream?path=C:/Windows/win.ini")
    print(f"Stream Absolute Traversal (C:/Windows/win.ini): {st} {msg}")
    results['stream_absolute_traversal'] = (st == 403)

    # 1b. GET /api/v1/knowledge/stream?path=../../Windows/win.ini
    st, msg, hdrs, _ = fetch(f"{base_url}/api/v1/knowledge/stream?path=../../Windows/win.ini")
    print(f"Stream Relative Traversal (../../Windows/win.ini): {st} {msg}")
    results['stream_relative_traversal'] = (st == 403)

    # 1c. GET /api/v1/knowledge/thumbnail?path=C:/Windows/win.ini
    st, msg, hdrs, _ = fetch(f"{base_url}/api/v1/knowledge/thumbnail?path=C:/Windows/win.ini")
    print(f"Thumbnail Absolute Traversal (C:/Windows/win.ini): {st} {msg}")
    results['thumb_absolute_traversal'] = (st == 403)

    # 1d. GET /api/v1/knowledge/thumbnail?path=../../Windows/win.ini
    st, msg, hdrs, _ = fetch(f"{base_url}/api/v1/knowledge/thumbnail?path=../../Windows/win.ini")
    print(f"Thumbnail Relative Traversal (../../Windows/win.ini): {st} {msg}")
    results['thumb_relative_traversal'] = (st == 403)

    print("\n=== TEST 2: Adversarial Traversal Vectors ===")
    
    # Encoded traversal
    encoded_path = urllib.parse.quote("C:\\Windows\\win.ini")
    st, msg, hdrs, _ = fetch(f"{base_url}/api/v1/knowledge/stream?path={encoded_path}")
    print(f"Stream Encoded Backslash (C%3A%5CWindows%5Cwin.ini): {st} {msg}")
    results['stream_encoded_backslash'] = (st == 403)

    # Double dot encoded traversal
    double_encoded = "%2e%2e%2f%2e%2e%2fWindows%2fwin.ini"
    st, msg, hdrs, _ = fetch(f"{base_url}/api/v1/knowledge/stream?path={double_encoded}")
    print(f"Stream Double Encoded Dots (%2e%2e%2f...): {st} {msg}")
    results['stream_double_encoded'] = (st == 403)

    # Root drive traversal attempt
    st, msg, hdrs, _ = fetch(f"{base_url}/api/v1/knowledge/stream?path=C:/")
    print(f"Stream Root Dir Traversal (C:/): {st} {msg}")
    results['stream_root_dir'] = (st == 403)

    # Alternate drive letter attempt
    st, msg, hdrs, _ = fetch(f"{base_url}/api/v1/knowledge/stream?path=D:/Program%20Files")
    print(f"Stream Alternate Drive (D:/Program Files): {st} {msg}")
    results['stream_alt_drive'] = (st == 403)

    print("\n=== TEST 3: Mandatory Legitimate Streaming Requests ===")
    video_path = r"C:\vazus\knowledge\telegram_courses\Курс _Покоритель Наташек 6_0_\2025-07-22 00-42-20_msg19.mp4"
    quoted_video = urllib.parse.quote(video_path)

    # Full GET (HTTP 200) - read first 100KB without dropping connection abruptly
    st, msg, hdrs, length = fetch(f"{base_url}/api/v1/knowledge/stream?path={quoted_video}", drain=False)
    print(f"Legitimate stream full: Status {st}, Type {hdrs.get('Content-Type')}, Length {hdrs.get('Content-Length')}")
    results['stream_legit_200'] = (st == 200 and hdrs.get('Content-Type') == 'video/mp4')

    # Range GET (HTTP 206)
    st, msg, hdrs, length = fetch(f"{base_url}/api/v1/knowledge/stream?path={quoted_video}", headers={'Range': 'bytes=0-1023'})
    print(f"Legitimate stream range: Status {st}, Range {hdrs.get('Content-Range')}, Length {hdrs.get('Content-Length')}")
    results['stream_legit_206'] = (st == 206 and hdrs.get('Content-Range') == 'bytes 0-1023/367768188' and length == 1024)

    print("\n=== TEST 4: Mandatory Legitimate Thumbnail Requests ===")
    thumb_path = r"C:\vazus\knowledge\telegram_courses\Курс _Покоритель Наташек 6_0_\media_198.jpg"
    quoted_thumb = urllib.parse.quote(thumb_path)

    st, msg, hdrs, length = fetch(f"{base_url}/api/v1/knowledge/thumbnail?path={quoted_thumb}")
    print(f"Legitimate thumbnail: Status {st}, Type {hdrs.get('Content-Type')}, Length {hdrs.get('Content-Length')}")
    results['thumb_legit_200'] = (st == 200 and hdrs.get('Content-Type') == 'image/jpeg' and length == 33900)

    print("\n=== TEST 5: Edge Cases & Boundary Conditions ===")

    # Missing path parameter
    st, msg, hdrs, _ = fetch(f"{base_url}/api/v1/knowledge/stream")
    print(f"Missing path param: Status {st} {msg}")
    results['missing_path'] = (st == 400)

    # Non-existent file inside allowed boundary
    st, msg, hdrs, _ = fetch(f"{base_url}/api/v1/knowledge/stream?path=C:/vazus/nonexistent_file.mp4")
    print(f"Non-existent file in boundary: Status {st} {msg}")
    results['nonexistent_file'] = (st == 404)

    # Invalid range request
    st, msg, hdrs, _ = fetch(f"{base_url}/api/v1/knowledge/stream?path={quoted_video}", headers={'Range': 'bytes=9999999999-9999999999'})
    print(f"Invalid range request: Status {st} {msg}, Range Header: {hdrs.get('Content-Range')}")
    results['invalid_range'] = (st == 416)

    server.shutdown()

    print("\n=== TEST SUMMARY ===")
    all_passed = True
    for test_name, passed in results.items():
        symbol = "✅ PASS" if passed else "❌ FAIL"
        if not passed:
            all_passed = False
        print(f"  {symbol} - {test_name}")

    if all_passed:
        print("\nALL VERIFICATION TESTS PASSED SUCCESSFULLY!")
    else:
        print("\nSOME TESTS FAILED!")

if __name__ == "__main__":
    run_tests()
