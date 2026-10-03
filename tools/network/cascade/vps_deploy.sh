#!/bin/bash
# ================================================================
# VAZUS VPS DEPLOY SCRIPT
# Debian/Ubuntu ARM64 + x86_64 compatible
# Usage: bash vps_deploy.sh [entry|relay|exit]
# ================================================================
set -e

ROLE="${1:-entry}"
VPS_RELAY_IP="${VPS_RELAY_IP:-91.184.241.206}"
LOG="/var/log/vazus_deploy.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== Vazus VPS Deploy === ROLE=$ROLE ==="

# ===== 1. SYSTEM UPDATE =====
log "Updating system..."
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
    curl wget git unzip jq htop iftop netcat-openbsd \
    iptables nftables python3 python3-pip python3-venv \
    fail2ban nginx certbot \
    build-essential libnetfilter-queue-dev \
    docker.io docker-compose-plugin || apt-get install -y docker-compose

# Enable docker
systemctl enable docker
systemctl start docker

# ===== 2. CHANGE SSH PORT (safety) =====
log "Configuring SSH..."
# Keep original port, add extra port
if ! grep -q "Port 2222" /etc/ssh/sshd_config; then
    echo "Port 22" >> /etc/ssh/sshd_config
    echo "Port 2222" >> /etc/ssh/sshd_config
    systemctl restart sshd
fi

# ===== 3. XRAY VLESS+REALITY =====
log "Installing xray..."
bash <(curl -sL https://github.com/XTLS/Xray-install/raw/main/install-release.sh) @ install 2>&1 | tail -5

# Generate Reality keys
XRAY_KEYS=$(xray x25519 2>/dev/null || /usr/local/bin/xray x25519)
PRIVATE_KEY=$(echo "$XRAY_KEYS" | grep "Private" | awk '{print $3}')
PUBLIC_KEY=$(echo "$XRAY_KEYS" | grep "Public" | awk '{print $3}')
UUID=$(cat /proc/sys/kernel/random/uuid)
SHORT_ID=$(openssl rand -hex 4)

log "Xray UUID: $UUID"
log "Public key: $PUBLIC_KEY"

cat > /usr/local/etc/xray/config.json << EOF
{
  "log": {"loglevel": "warning", "access": "/var/log/xray/access.log", "error": "/var/log/xray/error.log"},
  "inbounds": [
    {
      "tag": "vless-reality",
      "port": 443,
      "protocol": "vless",
      "settings": {
        "clients": [{"id": "$UUID", "flow": "xtls-rprx-vision"}],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
          "show": false,
          "dest": "www.google.com:443",
          "xver": 0,
          "serverNames": ["www.google.com", "www.bing.com"],
          "privateKey": "$PRIVATE_KEY",
          "shortIds": ["$SHORT_ID"]
        }
      },
      "sniffing": {"enabled": true, "destOverride": ["http", "tls", "quic"]}
    }
  ],
  "outbounds": [
$(if [ "$ROLE" = "entry" ] && [ -n "$VPS_RELAY_IP" ]; then
echo '    {"tag": "relay", "protocol": "vless", "settings": {"vnext": [{"address": "'$VPS_RELAY_IP'", "port": 443, "users": [{"id": "RELAY_UUID", "flow": "xtls-rprx-vision", "encryption": "none"}]}]}, "streamSettings": {"network": "tcp", "security": "reality", "realitySettings": {"serverName": "www.google.com", "fingerprint": "chrome"}}},'
fi)
    {"tag": "direct", "protocol": "freedom"},
    {"tag": "block", "protocol": "blackhole"}
  ]
}
EOF

mkdir -p /var/log/xray
systemctl enable xray
systemctl restart xray
log "Xray started, UUID=$UUID, PUBLIC_KEY=$PUBLIC_KEY"

# ===== 4. CLOUDFLARED TUNNEL (SSH через Cloudflare) =====
log "Installing cloudflared..."
ARCH=$(uname -m)
if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    CF_ARCH="arm64"
else
    CF_ARCH="amd64"
fi

wget -q "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${CF_ARCH}" \
    -O /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared

# Quick tunnel for SSH (no auth required)
cat > /etc/systemd/system/cloudflared-tunnel.service << 'EOF'
[Unit]
Description=Cloudflare Quick Tunnel for SSH
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/cloudflared tunnel --url ssh://localhost:22 --no-autoupdate
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl enable cloudflared-tunnel
systemctl start cloudflared-tunnel
sleep 5
CF_URL=$(journalctl -u cloudflared-tunnel --no-pager -n 20 2>/dev/null | grep -o "https://.*trycloudflare.com" | head -1)
log "Cloudflare tunnel URL: $CF_URL"

# ===== 5. FAIL2BAN =====
log "Configuring fail2ban..."
cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
maxretry = 5
bantime = 3600
findtime = 600

[sshd]
enabled = true
maxretry = 3
bantime = 86400
EOF
systemctl enable fail2ban
systemctl restart fail2ban

# ===== 6. NFTABLES FORWARDING =====
log "Configuring nftables..."
cat > /etc/nftables.conf << 'EOF'
#!/usr/sbin/nft -f
flush ruleset

table inet filter {
    chain input {
        type filter hook input priority 0; policy accept;
    }
    chain forward {
        type filter hook forward priority 0; policy accept;
    }
    chain output {
        type filter hook output priority 0; policy accept;
    }
}

table ip nat {
    chain postrouting {
        type nat hook postrouting priority 100;
        masquerade;
    }
}
EOF
echo 'net.ipv4.ip_forward=1' > /etc/sysctl.d/99-forward.conf
sysctl -p /etc/sysctl.d/99-forward.conf
nft -f /etc/nftables.conf
systemctl enable nftables

# ===== 7. PYTHON FASTAPI WORKER (AGY Orchestrator) =====
log "Setting up Python AGY worker..."
mkdir -p /opt/vazus-worker
python3 -m venv /opt/vazus-worker/venv
/opt/vazus-worker/venv/bin/pip install -q fastapi uvicorn paramiko websockets

cat > /opt/vazus-worker/worker.py << 'PYEOF'
#!/usr/bin/env python3
"""Vazus Cascade AGY Worker — минимальный оркестратор"""
import asyncio, json, subprocess, os, time
from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse

app = FastAPI(title="Vazus AGY Worker")
ROLE = os.environ.get("VAZUS_ROLE", "entry")
VERSION = "1.0.0"

@app.get("/")
async def root():
    return {"status": "ok", "role": ROLE, "version": VERSION, "time": time.time()}

@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})

@app.post("/exec")
async def exec_cmd(body: dict):
    cmd = body.get("cmd", "")
    if not cmd:
        return {"error": "no cmd"}
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return {"stdout": result.stdout, "stderr": result.stderr, "rc": result.returncode}
    except Exception as e:
        return {"error": str(e)}

@app.websocket("/ws")
async def ws_orchestrate(ws: WebSocket):
    await ws.accept()
    await ws.send_json({"type": "hello", "role": ROLE, "version": VERSION})
    while True:
        try:
            data = await ws.receive_json()
            if data.get("type") == "exec":
                result = subprocess.run(data["cmd"], shell=True, capture_output=True, text=True, timeout=60)
                await ws.send_json({"type": "result", "stdout": result.stdout, "stderr": result.stderr, "rc": result.returncode})
            elif data.get("type") == "ping":
                await ws.send_json({"type": "pong"})
        except Exception as e:
            await ws.send_json({"type": "error", "msg": str(e)})
PYEOF

cat > /etc/systemd/system/vazus-worker.service << 'EOF'
[Unit]
Description=Vazus AGY Worker
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/vazus-worker
ExecStart=/opt/vazus-worker/venv/bin/uvicorn worker:app --host 0.0.0.0 --port 8000
Environment=VAZUS_ROLE=entry
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl enable vazus-worker
systemctl start vazus-worker

# ===== 8. NGINX WEB DASHBOARD =====
log "Setting up nginx dashboard..."
mkdir -p /var/www/vazus-dash

cat > /var/www/vazus-dash/index.html << 'HTMLEOF'
<!DOCTYPE html>
<html lang="ru">
<head><meta charset="UTF-8"><title>Vazus Cascade Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body { background: #0a0a0f; color: #e0e0e0; font-family: 'Courier New', mono; margin: 0; padding: 20px; }
h1 { color: #00ff88; font-size: 1.5em; }
.card { background: #111; border: 1px solid #333; border-radius: 8px; padding: 15px; margin: 10px 0; }
.alive { color: #00ff88; } .dead { color: #ff4444; }
pre { font-size: 0.85em; overflow-x: auto; }
button { background: #00ff88; color: #000; border: none; padding: 8px 16px; cursor: pointer; border-radius: 4px; margin: 5px; }
</style></head>
<body>
<h1>⚡ Vazus Cascade Dashboard</h1>
<div class="card">
  <h3>VPS Status</h3>
  <div id="status">Loading...</div>
</div>
<div class="card">
  <h3>Worker API</h3>
  <button onclick="testWorker()">Test Worker</button>
  <button onclick="location.reload()">Refresh</button>
  <pre id="worker-out"></pre>
</div>
<script>
async function fetchStatus() {
  try {
    const r = await fetch('/api/');
    const d = await r.json();
    document.getElementById('status').innerHTML = 
      '<span class="alive">✅ Worker Online</span><pre>' + JSON.stringify(d, null, 2) + '</pre>';
  } catch(e) {
    document.getElementById('status').innerHTML = '<span class="dead">❌ Worker offline: ' + e + '</span>';
  }
}
async function testWorker() {
  const r = await fetch('/api/exec', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({cmd: 'uptime && free -h'})});
  const d = await r.json();
  document.getElementById('worker-out').textContent = d.stdout || d.error;
}
fetchStatus();
setInterval(fetchStatus, 10000);
</script>
</body></html>
HTMLEOF

cat > /etc/nginx/sites-available/vazus << 'EOF'
server {
    listen 8080;
    server_name _;
    
    location / {
        root /var/www/vazus-dash;
        index index.html;
    }
    
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

ln -sf /etc/nginx/sites-available/vazus /etc/nginx/sites-enabled/
nginx -t && systemctl restart nginx

# ===== 9. WATCHTOWER (auto-update Docker containers) =====
if command -v docker &>/dev/null; then
    log "Setting up Watchtower..."
    docker run -d \
        --name watchtower \
        --restart unless-stopped \
        -v /var/run/docker.sock:/var/run/docker.sock \
        containrrr/watchtower --interval 86400 2>/dev/null || log "Watchtower already running"
fi

# ===== SUMMARY =====
log ""
log "============================================"
log "   VAZUS VPS DEPLOY COMPLETE"
log "============================================"
log "ROLE: $ROLE"
log "XRAY UUID: $UUID"
log "XRAY Public Key: $PUBLIC_KEY"
log "XRAY Short ID: $SHORT_ID"
log "Cloudflare Tunnel: $CF_URL"
log "Web Dashboard: http://$(curl -s ifconfig.me):8080"
log "AGY Worker: http://$(curl -s ifconfig.me):8000"
log "============================================"
log ""
log "Add to SSH config on Windows:"
log "Host vps-new"
log "    HostName $CF_URL"
log "    User root"  
log "    ProxyCommand C:\\Users\\Vaz\\cloudflared.exe access ssh --hostname %h"
log "============================================"
