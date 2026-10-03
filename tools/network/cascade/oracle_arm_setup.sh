#!/bin/bash
# ================================================================
# ORACLE ARM BOARD / SD CARD SETUP SCRIPT
# Для плат: Orange Pi 5, Raspberry Pi 4/5, Rock Pi, NanoPi
# Также подходит для Oracle Cloud ARM64 (Ampere A1)
# Запускать после записи Debian ARM64 на SD и первого старта
# ================================================================
set -e
LOG="/var/log/vazus_oracle_setup.log"
log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== VAZUS ORACLE ARM SETUP ==="
log "Hostname: $(hostname), Arch: $(uname -m)"

# ===== SYSTEM =====
apt-get update -qq
apt-get install -y -qq \
    curl wget git unzip jq htop iftop nmap \
    python3 python3-pip python3-venv \
    nginx docker.io docker-compose-plugin \
    fail2ban ufw wireguard-tools \
    hostapd dnsmasq iptables nftables \
    avahi-daemon avahi-utils \
    ffmpeg v4l-utils \
    build-essential

# ===== DOCKER =====
systemctl enable docker
systemctl start docker
usermod -aG docker $SUDO_USER 2>/dev/null || true

# ===== UFW FIREWALL =====
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp   # SSH
ufw allow 2222/tcp # SSH alt
ufw allow 443/tcp  # xray
ufw allow 80/tcp   # nginx
ufw allow 8080/tcp # dashboard
ufw allow 8000/tcp # worker API
ufw allow 7777/tcp # cascade monitor
ufw allow 51820/udp # WireGuard
ufw --force enable

# ===== CLOUDFLARED =====
ARCH=$(uname -m)
[ "$ARCH" = "aarch64" ] && CF_ARCH="arm64" || CF_ARCH="amd64"
wget -q "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${CF_ARCH}" \
    -O /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared

# Cloudflare Quick Tunnel для SSH доступа
cat > /etc/systemd/system/cloudflared-ssh.service << 'EOF'
[Unit]
Description=Cloudflare SSH Tunnel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/cloudflared tunnel --url ssh://localhost:22 --no-autoupdate
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF
systemctl enable cloudflared-ssh
systemctl start cloudflared-ssh

# ===== XRAY (VLESS+Reality) =====
log "Installing xray..."
bash <(curl -sL https://github.com/XTLS/Xray-install/raw/main/install-release.sh) @ install 2>&1 | tail -3

XRAY_KEYS=$(xray x25519 2>/dev/null || /usr/local/bin/xray x25519)
PRIVATE_KEY=$(echo "$XRAY_KEYS" | grep "Private" | awk '{print $3}')
PUBLIC_KEY=$(echo "$XRAY_KEYS" | grep "Public" | awk '{print $3}')
UUID=$(cat /proc/sys/kernel/random/uuid)
SHORT_ID=$(openssl rand -hex 4)

cat > /usr/local/etc/xray/config.json << EOF
{
  "log": {"loglevel": "warning"},
  "inbounds": [{
    "port": 443, "protocol": "vless",
    "settings": {"clients": [{"id": "$UUID", "flow": "xtls-rprx-vision"}], "decryption": "none"},
    "streamSettings": {
      "network": "tcp", "security": "reality",
      "realitySettings": {
        "dest": "www.google.com:443",
        "serverNames": ["www.google.com"],
        "privateKey": "$PRIVATE_KEY",
        "shortIds": ["$SHORT_ID"]
      }
    }
  }],
  "outbounds": [{"protocol": "freedom"}]
}
EOF
systemctl enable xray
systemctl restart xray

# ===== PYTHON VAZUS WORKER =====
log "Setting up Python worker..."
mkdir -p /opt/vazus-worker
python3 -m venv /opt/vazus-worker/venv
/opt/vazus-worker/venv/bin/pip install -q fastapi uvicorn paramiko

cat > /opt/vazus-worker/worker.py << 'EOF'
import asyncio, json, subprocess, os, time, psutil
from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse

app = FastAPI()
ROLE = os.environ.get("VAZUS_ROLE", "oracle-arm")

@app.get("/")
async def root():
    return {
        "status": "ok", "role": ROLE,
        "uptime": time.time(),
        "cpu": psutil.cpu_percent(),
        "mem": psutil.virtual_memory()._asdict(),
        "disk": psutil.disk_usage("/")._asdict(),
    }

@app.post("/exec")
async def exec_cmd(body: dict):
    cmd = body.get("cmd", "")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    return {"stdout": result.stdout, "stderr": result.stderr, "rc": result.returncode}

@app.websocket("/ws")
async def orchestrate(ws: WebSocket):
    await ws.accept()
    await ws.send_json({"type": "hello", "role": ROLE})
    while True:
        data = await ws.receive_json()
        if data.get("type") == "exec":
            r = subprocess.run(data["cmd"], shell=True, capture_output=True, text=True, timeout=60)
            await ws.send_json({"type": "result", "stdout": r.stdout, "stderr": r.stderr})
EOF

/opt/vazus-worker/venv/bin/pip install -q psutil

cat > /etc/systemd/system/vazus-worker.service << EOF
[Unit]
Description=Vazus Oracle ARM Worker
After=network.target

[Service]
WorkingDirectory=/opt/vazus-worker
ExecStart=/opt/vazus-worker/venv/bin/uvicorn worker:app --host 0.0.0.0 --port 8000
Environment=VAZUS_ROLE=oracle-arm
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
systemctl enable vazus-worker
systemctl start vazus-worker

# ===== WIFI AP (если есть wlan0) =====
if ip link show wlan0 &>/dev/null; then
    log "Setting up WiFi AP on wlan0..."
    cat > /etc/hostapd/hostapd.conf << 'EOF'
interface=wlan0
driver=nl80211
ssid=VazusCascade
hw_mode=g
channel=6
auth_algs=1
wpa=2
wpa_passphrase=vazus_cascade_2026
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
EOF
    
    cat > /etc/dnsmasq.d/ap.conf << 'EOF'
interface=wlan0
dhcp-range=192.168.100.10,192.168.100.50,12h
EOF
    
    # NAT через основной интерфейс
    ETH0=$(ip route | grep default | awk '{print $5}' | head -1)
    iptables -t nat -A POSTROUTING -o "$ETH0" -j MASQUERADE
    iptables -A FORWARD -i wlan0 -o "$ETH0" -j ACCEPT
    iptables -A FORWARD -i "$ETH0" -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT
    
    systemctl enable hostapd dnsmasq
    systemctl start hostapd dnsmasq
    log "WiFi AP: VazusCascade on wlan0"
fi

# ===== CASCADE MONITOR =====
mkdir -p /opt/vazus-cascade
cat > /opt/vazus-cascade/cascade_monitor.py << 'EOF'
#!/usr/bin/env python3
"""Cascade monitor — минимальная версия для ARM"""
import socket, json, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

VPS_SERVERS = [
    {"id": "vps1", "host": "91.184.241.206", "port": 2222, "label": "VPS1"},
    {"id": "vps2", "host": "147.45.73.195",  "port": 22,   "label": "VPS2"},
    {"id": "vps3", "host": "157.228.174.15", "port": 22,   "label": "VPS3"},
]
STATUS = {"servers": {}, "active": [], "mode": "init"}

def check(srv):
    try:
        s = socket.create_connection((srv["host"], srv["port"]), timeout=8)
        s.settimeout(3)
        try: banner = s.recv(64).decode(errors="ignore")
        except: banner = ""
        s.close()
        return "SSH" in banner
    except: return False

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(STATUS, ensure_ascii=False).encode())

def monitor():
    while True:
        alive = [s for s in VPS_SERVERS if check(s)]
        STATUS["servers"] = {s["id"]: check(s) for s in VPS_SERVERS}
        STATUS["active"] = [s["id"] for s in alive]
        STATUS["mode"] = "cascade" if len(alive)>1 else ("single" if alive else "direct")
        STATUS["ts"] = time.time()
        Path("/tmp/cascade_status.json").write_text(json.dumps(STATUS))
        time.sleep(60)

threading.Thread(target=monitor, daemon=True).start()
HTTPServer(("0.0.0.0", 7777), H).serve_forever()
EOF

python3 /opt/vazus-cascade/cascade_monitor.py &

# ===== NGINX DASHBOARD =====
cat > /etc/nginx/sites-available/vazus << 'EOF'
server {
    listen 8080;
    location / { root /var/www/vazus-dash; index index.html; }
    location /api/ { proxy_pass http://127.0.0.1:8000/; }
    location /cascade/ { proxy_pass http://127.0.0.1:7777/; }
}
EOF
ln -sf /etc/nginx/sites-available/vazus /etc/nginx/sites-enabled/
nginx -t && systemctl restart nginx

# ===== SUMMARY =====
MY_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
CF_URL=$(journalctl -u cloudflared-ssh --no-pager -n 20 2>/dev/null | grep -o "https://.*trycloudflare.com" | head -1)
log ""
log "============================================"
log "   VAZUS ORACLE ARM SETUP COMPLETE"
log "============================================"
log "IP: $MY_IP"
log "Xray UUID: $UUID"
log "Xray Public Key: $PUBLIC_KEY"
log "CF Tunnel (SSH): $CF_URL"
log "Dashboard: http://$MY_IP:8080"
log "Worker API: http://$MY_IP:8000"
log "Cascade status: http://$MY_IP:7777"
log "============================================"
