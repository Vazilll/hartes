#!/usr/bin/env python3
"""
Vazus Cascade Monitor — отказоустойчивый мониторинг VPS каскада
Автоматически переключается между серверами, статус-сервер на :7777
"""
import json
import socket
import sys
import time
import threading
import logging
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# ===== КОНФИГ =====
VPS_SERVERS = [
    {"id": "vps1", "host": "91.184.241.206", "port": 2222, "user": "root", "label": "VPS1 Aeza"},
    {"id": "vps2", "host": "147.45.73.195",  "port": 22,   "user": "root", "label": "VPS2 Old"},
    {"id": "vps3", "host": "157.228.174.15", "port": 22,   "user": "root", "label": "VPS3 157"},
    {"id": "cf",   "host": "fat-wing-nevertheless-bags.trycloudflare.com",
                            "port": 22,    "user": "root", "label": "CF Tunnel"},
]
SSH_KEY = r"C:\Users\Vaz\.ssh\id_rsa"
STATUS_FILE = Path(r"C:\vazus\cascade\vps_status.json")
ACTIVE_ROUTE = Path(r"C:\vazus\cascade\active_route.json")
CHECK_INTERVAL = 60  # seconds
STATUS_PORT = 7777
LOG_FILE = Path(r"C:\vazus\cascade\monitor.log")

# ===== LOGGING =====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("cascade")

# ===== STATE =====
state = {
    "servers": {},
    "active": [],
    "mode": "initializing",
    "last_check": None,
    "total_checks": 0,
}

def check_tcp(host, port, timeout=8):
    """Fast TCP connect check"""
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except:
        return False

def check_ssh_banner(host, port, timeout=8):
    """Check if SSH banner is present"""
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.settimeout(5)
        banner = s.recv(128).decode("utf-8", errors="ignore")
        s.close()
        return "SSH" in banner, banner.strip()
    except:
        return False, ""

def check_server(srv):
    """Full check for one server"""
    host, port = srv["host"], srv["port"]
    result = {
        "id": srv["id"],
        "label": srv["label"],
        "host": host,
        "port": port,
        "alive": False,
        "ssh_banner": "",
        "latency_ms": None,
        "last_seen": None,
        "error": None,
    }
    
    t0 = time.time()
    tcp_ok = check_tcp(host, port, timeout=8)
    latency = round((time.time() - t0) * 1000, 1)
    
    if tcp_ok:
        result["latency_ms"] = latency
        has_ssh, banner = check_ssh_banner(host, port)
        result["ssh_banner"] = banner
        if has_ssh:
            result["alive"] = True
            result["last_seen"] = datetime.now().isoformat()
        else:
            result["alive"] = False
            result["error"] = f"Port open but no SSH banner (banner: {banner[:50]})"
    else:
        result["error"] = "TCP timeout/refused"
    
    return result

def update_active_route(alive_servers):
    """Update routing based on alive servers"""
    if not alive_servers:
        mode = "direct_zapret"
        log.warning("ALL VPS DOWN — using direct connection + Zapret only")
    elif len(alive_servers) == 1:
        mode = f"single_{alive_servers[0]['id']}"
        log.info(f"Single VPS active: {alive_servers[0]['label']}")
    else:
        mode = f"cascade_{'_'.join(s['id'] for s in alive_servers)}"
        log.info(f"Cascade active: {' -> '.join(s['label'] for s in alive_servers)}")
    
    route = {
        "mode": mode,
        "active_servers": [{"id": s["id"], "host": s["host"], "port": s["port"], "label": s["label"]} 
                           for s in alive_servers],
        "updated": datetime.now().isoformat(),
        "fallback": "direct + zapret winws.exe",
    }
    
    ACTIVE_ROUTE.write_text(json.dumps(route, ensure_ascii=False, indent=2))
    return mode

def run_check_cycle():
    """Single check cycle for all servers"""
    state["total_checks"] += 1
    state["last_check"] = datetime.now().isoformat()
    
    results = {}
    alive = []
    
    for srv in VPS_SERVERS:
        log.info(f"Checking {srv['label']} ({srv['host']}:{srv['port']})...")
        result = check_server(srv)
        results[srv["id"]] = result
        if result["alive"]:
            alive.append(srv)
            log.info(f"  ✅ ALIVE ({result['latency_ms']}ms) — {result['ssh_banner'][:60]}")
        else:
            log.warning(f"  ❌ DEAD — {result['error']}")
    
    state["servers"] = results
    state["active"] = [s["id"] for s in alive]
    state["mode"] = update_active_route(alive)
    
    STATUS_FILE.write_text(json.dumps({
        "servers": results,
        "active": state["active"],
        "mode": state["mode"],
        "last_check": state["last_check"],
        "total_checks": state["total_checks"],
    }, ensure_ascii=False, indent=2))
    
    return alive

class StatusHandler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        pass  # Suppress access logs
    
    def do_GET(self):
        if self.path in ("/", "/status"):
            data = json.dumps({
                "servers": state["servers"],
                "active": state["active"],
                "mode": state["mode"],
                "last_check": state["last_check"],
                "total_checks": state["total_checks"],
            }, ensure_ascii=False, indent=2)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(data.encode())
        elif self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

def run_status_server():
    server = HTTPServer(("0.0.0.0", STATUS_PORT), StatusHandler)
    log.info(f"Status server on http://localhost:{STATUS_PORT}/status")
    server.serve_forever()

def main():
    log.info("=== Vazus Cascade Monitor Starting ===")
    log.info(f"Monitoring {len(VPS_SERVERS)} servers, interval={CHECK_INTERVAL}s")
    
    # Start HTTP status server in background
    t = threading.Thread(target=run_status_server, daemon=True)
    t.start()
    
    # Main loop
    while True:
        try:
            alive = run_check_cycle()
            log.info(f"Check done: {len(alive)}/{len(VPS_SERVERS)} alive, mode={state['mode']}")
        except Exception as e:
            log.error(f"Check cycle error: {e}", exc_info=True)
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
