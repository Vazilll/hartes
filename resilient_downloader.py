import os
import sys
import time
import requests

MODELS = [
    {
        "url": "https://hf-mirror.com/Abiray/ZAYA1-8B-GGUF/resolve/main/ZAYA1-8B-Q4_K_M.gguf",
        "path": "C:/vazus/models/ZAYA1-8B-Q4_K_M.gguf"
    },
    {
        "url": "https://hf-mirror.com/shoumenchougou/RWKV7-G1g-2.9B-GGUF/resolve/main/rwkv7-g1g-2.9b-Q4_K_M.gguf",
        "path": "C:/vazus/models/rwkv7-g1g-2.9b-Q4_K_M.gguf"
    }
]

def download_file(url, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = path + ".download"
    
    # Get total size from HEAD request
    try:
        r = requests.head(url, allow_redirects=True, timeout=15)
        total_size = int(r.headers.get('content-length', 0))
    except Exception as e:
        print(f"Error checking file headers: {e}", flush=True)
        total_size = 0

    print(f"Downloading {os.path.basename(path)}...", flush=True)
    print(f"Total size: {total_size / (1024*1024):.2f} MB", flush=True)

    while True:
        try:
            # Check existing temp file size
            current_size = 0
            if os.path.exists(temp_path):
                current_size = os.path.getsize(temp_path)
            
            if total_size and current_size >= total_size:
                print(f"Temp file size {current_size} is equal/greater than total size {total_size}. Finalizing.", flush=True)
                os.replace(temp_path, path)
                return True

            headers = {}
            if current_size > 0:
                headers['Range'] = f'bytes={current_size}-'
                print(f"Resuming download from byte offset {current_size}...", flush=True)
                mode = 'ab'
            else:
                mode = 'wb'

            r = requests.get(url, headers=headers, stream=True, timeout=15)
            
            if r.status_code not in (200, 206):
                print(f"Bad status code {r.status_code}. Retrying...", flush=True)
                time.sleep(5)
                continue

            last_log_time = time.time()
            bytes_downloaded = current_size

            with open(temp_path, mode) as f:
                for chunk in r.iter_content(chunk_size=1024*1024):  # 1MB chunks
                    if chunk:
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        
                        # Log every 5 seconds
                        if time.time() - last_log_time > 5:
                            pct = (bytes_downloaded / total_size * 100) if total_size else 0
                            print(f"Progress: {bytes_downloaded / (1024*1024):.1f} / {total_size / (1024*1024):.1f} MB ({pct:.1f}%)", flush=True)
                            last_log_time = time.time()
            
            # Download completed successfully
            print(f"Finished downloading {os.path.basename(path)}.", flush=True)
            os.replace(temp_path, path)
            return True

        except (requests.RequestException, IOError) as e:
            print(f"\nConnection error or timeout: {e}. Retrying in 5 seconds...", flush=True)
            time.sleep(5)

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    print("====== RESILIENT PYTHON DOWNLOADER (MIRRORED) ======", flush=True)
    for model in MODELS:
        path = model["path"]
        if os.path.exists(path):
            print(f"File {os.path.basename(path)} already exists. Skipping.", flush=True)
            continue
        download_file(model["url"], path)
    print("====== ALL DOWNLOADS COMPLETED ======", flush=True)
