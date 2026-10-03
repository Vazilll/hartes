#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive
LOG=/tmp/vazus_deploy.log
exec > >(tee -a "$LOG") 2>&1

log() { echo "[$(date '+%H:%M:%S')] $*"; }
ok()  { echo "  + $*"; }
err() { echo "  x $*"; exit 1; }

log "=== VAZUS VPS DEPLOY ==="

# ---- 1. SYSTEM ----
log "[1/10] System update..."
apt-get update -qq
apt-get install -y -qq curl wget jq ufw fail2ban nginx openssl 2>/dev/null
ok "packages installed"

# ---- 2. UNBAN CLIENT IP ----
log "[2/10] Whitelisting client IP..."
CLIENT_IP=$(echo $SSH_CLIENT | awk '{print $1}')
log "Client IP: $CLIENT_IP"
mkdir -p /etc/fail2ban
printf '[DEFAULT]\nbantime  = 600\nfindtime = 300\nmaxretry = 10\nignoreip = 127.0.0.1/8 ::1 195.189.181.140\n\n[sshd]\nenabled  = true\nmaxretry = 5\nbantime  = 3600\n' > /etc/fail2ban/jail.local
systemctl restart fail2ban 2>/dev/null || true
fail2ban-client set sshd unbanip 195.189.181.140 2>/dev/null || true
ok "IP whitelisted"

# ---- 3. SSH on port 2222 ----
log "[3/10] Adding SSH port 2222..."
grep -q "Port 2222" /etc/ssh/sshd_config 2>/dev/null || echo "Port 2222" >> /etc/ssh/sshd_config
systemctl restart sshd 2>/dev/null || systemctl restart ssh 2>/dev/null || true
ok "SSH now on :22 and :2222"

# ---- 4. XRAY ----
log "[4/10] Installing xray..."
curl -sL https://github.com/XTLS/Xray-install/raw/main/install-release.sh -o /tmp/xray_install.sh
bash /tmp/xray_install.sh install 2>&1 | tail -3
XRAY_BIN=/usr/local/bin/xray
[ -f "$XRAY_BIN" ] || err "xray not installed"
ok "xray installed: $($XRAY_BIN version | head -1)"

# ---- 5. REALITY KEYS ----
log "[5/10] Generating Reality keys..."
KEYS=$($XRAY_BIN x25519 2>/dev/null)
PRIVATE_KEY=$(echo "$KEYS" | grep "Private" | awk '{print $3}')
PUBLIC_KEY=$(echo "$KEYS"  | grep "Public"  | awk '{print $3}')
VLESS_UUID=$($XRAY_BIN uuid 2>/dev/null || cat /proc/sys/kernel/random/uuid)
SHORT_ID=$(openssl rand -hex 4)
log "UUID:       $VLESS_UUID"
log "PublicKey:  $PUBLIC_KEY"
log "ShortID:    $SHORT_ID"

# ---- 6. XRAY CONFIG (using printf, no heredoc) ----
log "[6/10] Writing xray config..."
mkdir -p /usr/local/etc/xray /var/log/xray

python3 -c "
import json, sys
cfg = {
    'log': {'loglevel':'warning','access':'/var/log/xray/access.log','error':'/var/log/xray/error.log'},
    'inbounds': [{
        'tag': 'vless-reality',
        'listen': '0.0.0.0',
        'port': 443,
        'protocol': 'vless',
        'settings': {
            'clients': [{'id': sys.argv[1], 'flow': 'xtls-rprx-vision'}],
            'decryption': 'none'
        },
        'streamSettings': {
            'network': 'tcp',
            'security': 'reality',
            'realitySettings': {
                'show': False,
                'dest': 'www.microsoft.com:443',
                'xver': 0,
                'serverNames': ['www.microsoft.com','www.google.com','www.apple.com'],
                'privateKey': sys.argv[2],
                'shortIds': [sys.argv[3], '']
            }
        },
        'sniffing': {'enabled':True,'destOverride':['http','tls','quic']}
    }],
    'outbounds': [
        {'tag':'direct','protocol':'freedom'},
        {'tag':'block','protocol':'blackhole'}
    ],
    'routing': {
        'domainStrategy': 'IPIfNonMatch',
        'rules': [
            {'type':'field','ip':['geoip:private'],'outboundTag':'block'},
            {'type':'field','domain':['geosite:category-ads-all'],'outboundTag':'block'}
        ]
    }
}
print(json.dumps(cfg, indent=2))
" "$VLESS_UUID" "$PRIVATE_KEY" "$SHORT_ID" > /usr/local/etc/xray/config.json

systemctl enable xray && systemctl restart xray
sleep 2
systemctl is-active xray | grep -q active && ok "xray running" || err "xray failed"

# ---- 7. HYSTERIA2 ----
log "[7/10] Installing Hysteria2..."
ARCH=$(uname -m); [ "$ARCH" = "aarch64" ] && HA=arm64 || HA=amd64
HY2_VER=$(curl -s https://api.github.com/repos/apernet/hysteria/releases/latest | grep '"tag_name"' | cut -d'"' -f4)
curl -sL "https://github.com/apernet/hysteria/releases/download/${HY2_VER}/hysteria-linux-${HA}" -o /usr/local/bin/hysteria
chmod +x /usr/local/bin/hysteria
HY2_PASS=$(openssl rand -base64 18 | tr -d '=/+' | head -c 24)
log "Hysteria2 password: $HY2_PASS"

mkdir -p /etc/hysteria
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 \
  -days 3650 -nodes \
  -keyout /etc/hysteria/private.key \
  -out /etc/hysteria/cert.pem \
  -subj "/CN=www.microsoft.com" 2>/dev/null

python3 -c "
import json, sys
cfg = {
    'listen': ':8443',
    'tls': {'cert': '/etc/hysteria/cert.pem', 'key': '/etc/hysteria/private.key'},
    'auth': {'type': 'password', 'password': sys.argv[1]},
    'masquerade': {'type': 'proxy', 'proxy': {'url': 'https://www.microsoft.com/', 'rewriteHost': True}}
}
import yaml
" "$HY2_PASS" 2>/dev/null || true

printf 'listen: :8443\ntls:\n  cert: /etc/hysteria/cert.pem\n  key: /etc/hysteria/private.key\nauth:\n  type: password\n  password: "%s"\nmasquerade:\n  type: proxy\n  proxy:\n    url: https://www.microsoft.com/\n    rewriteHost: true\n' "$HY2_PASS" > /etc/hysteria/config.yaml

printf '[Unit]\nDescription=Hysteria2 Server\nAfter=network.target\n[Service]\nExecStart=/usr/local/bin/hysteria server --config /etc/hysteria/config.yaml\nRestart=always\nRestartSec=5\nLimitNOFILE=1048576\n[Install]\nWantedBy=multi-user.target\n' > /etc/systemd/system/hysteria-server.service

systemctl daemon-reload
systemctl enable hysteria-server && systemctl restart hysteria-server
sleep 2
systemctl is-active hysteria-server | grep -q active && ok "hysteria2 running" || err "hysteria2 failed"

# ---- 8. CLOUDFLARED (SSH backup) ----
log "[8/10] Installing cloudflared tunnel..."
CFARCH=$(uname -m); [ "$CFARCH" = "aarch64" ] && CFARCH=arm64 || CFARCH=amd64
wget -q "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${CFARCH}" \
  -O /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared

printf '[Unit]\nDescription=Cloudflare Quick Tunnel SSH\nAfter=network-online.target\n[Service]\nExecStart=/usr/local/bin/cloudflared tunnel --url ssh://localhost:22 --no-autoupdate\nRestart=always\nRestartSec=30\n[Install]\nWantedBy=multi-user.target\n' > /etc/systemd/system/cloudflared-ssh.service

systemctl daemon-reload
systemctl enable cloudflared-ssh && systemctl start cloudflared-ssh
ok "cloudflared started"

# ---- 9. UFW FIREWALL ----
log "[9/10] Configuring firewall..."
ufw --force reset 2>/dev/null
ufw default deny incoming 2>/dev/null
ufw default allow outgoing 2>/dev/null
ufw allow 22/tcp 2>/dev/null
ufw allow 2222/tcp 2>/dev/null
ufw allow 443/tcp 2>/dev/null
ufw allow 8443/udp 2>/dev/null
ufw allow 80/tcp 2>/dev/null
ufw --force enable 2>/dev/null
ok "firewall configured"

# ---- 10. SUMMARY ----
log "[10/10] Getting tunnel URL..."
sleep 10
CF_URL=$(journalctl -u cloudflared-ssh --no-pager -n 30 2>/dev/null | grep -o "https://[^ ]*trycloudflare.com" | tail -1)
MY_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')

echo ""
echo "=========================================================="
echo "  VAZUS VPS DEPLOY COMPLETE"
echo "=========================================================="
echo "Server IP:        $MY_IP"
echo "VLESS UUID:       $VLESS_UUID"
echo "Reality PubKey:   $PUBLIC_KEY"
echo "Reality ShortID:  $SHORT_ID"
echo "Hysteria2 Pass:   $HY2_PASS"
echo "CF SSH Tunnel:    $CF_URL"
echo ""
echo "--- VLESS+Reality link ---"
echo "vless://${VLESS_UUID}@${MY_IP}:443?encryption=none&flow=xtls-rprx-vision&type=tcp&security=reality&sni=www.microsoft.com&fp=chrome&pbk=${PUBLIC_KEY}&sid=${SHORT_ID}#Vazus-VPS"
echo ""
echo "--- Hysteria2 link ---"
echo "hysteria2://${HY2_PASS}@${MY_IP}:8443/?insecure=1&sni=www.microsoft.com#Vazus-HY2"
echo "=========================================================="

printf 'VPS_IP=%s\nVLESS_UUID=%s\nREALITY_PUBKEY=%s\nREALITY_SHORTID=%s\nHY2_PASSWORD=%s\nCF_SSH_TUNNEL=%s\n' \
  "$MY_IP" "$VLESS_UUID" "$PUBLIC_KEY" "$SHORT_ID" "$HY2_PASS" "$CF_URL" > /root/vazus_config.txt
echo "Config saved to /root/vazus_config.txt"
