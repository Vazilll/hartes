#!/bin/bash
# ==============================================================================
# Vazus Autonomous Absolute AI Flywheel -- Setup Target 1
# Target: 1 GB Linux Cloud VPS (157.228.174.15) -- Minimal Proxy / Scheduler
# Architecture: Tier 0 Always-On Cloud Control Plane
# Strict Memory Budget: <= 200 MB RAM (systemd MemoryMax=200M, MemoryHigh=160M)
# ==============================================================================

set -e

LOG_FILE="/var/log/vazus/vps_setup.log"
mkdir -p /var/log/vazus
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "=== Starting Vazus Flywheel Tier 0 VPS Setup (Target 1) ==="
log "Host: $(hostname) | Kernel: $(uname -r) | Arch: $(uname -m)"

# 1. System packages & dependencies (stripped down for minimal RAM)
log "[1/7] Updating apt repositories and installing minimal dependencies..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
    curl wget git jq \
    python3 python3-pip python3-venv \
    fail2ban ufw

# 2. Workspace directories
log "[2/7] Creating /opt/vazus-flywheel directory structure..."
mkdir -p /opt/vazus-flywheel/data
mkdir -p /opt/vazus-flywheel/artifacts/vault/colab_queue/inbox
mkdir -p /opt/vazus-flywheel/artifacts/vault/colab_queue/active
mkdir -p /opt/vazus-flywheel/artifacts/vault/colab_queue/outbox
mkdir -p /etc/vazus

# 3. Dedicated Python 3 virtualenv with minimal memory footprint
log "[3/7] Setting up isolated Python 3 virtualenv..."
if [ ! -d "/opt/vazus-flywheel/venv" ]; then
    python3 -m venv /opt/vazus-flywheel/venv
fi
/opt/vazus-flywheel/venv/bin/pip install --upgrade pip -q
/opt/vazus-flywheel/venv/bin/pip install -q httpx psutil

# 4. Secure environment configuration (Strict 0600 permissions, zero plaintext secrets)
log "[4/7] Generating /etc/vazus/flywheel.env with 0600 permissions..."
ENV_FILE="/etc/vazus/flywheel.env"
if [ ! -f "$ENV_FILE" ]; then
    cat << 'EOF' > "$ENV_FILE"
# /etc/vazus/flywheel.env -- Strict 0600 permissions
VAZUS_VPS_IP=157.228.174.15
VAZUS_ROLE=tier0_vps
MEMORY_LIMIT_MB=200.0
MEMORY_WARNING_MB=150.0
NODE_TTL_SEC=90.0
TICK_INTERVAL_SEC=30.0
GITHUB_REPOSITORY=Vazilll/hartes
# Secrets injected securely via vault at runtime (NEVER commit plaintext secrets)
GITHUB_TOKEN=
JULES_API_KEY=
EOF
fi

chown root:root "$ENV_FILE"
chmod 0600 "$ENV_FILE"
log "Secured $ENV_FILE permissions: $(stat -c '%a %U:%G' "$ENV_FILE" 2>/dev/null || echo '0600 root:root')"

# 5. UFW Firewall Configuration
log "[5/7] Enforcing firewall boundary rules..."
if command -v ufw >/dev/null 2>&1; then
    ufw default deny incoming || true
    ufw default allow outgoing || true
    ufw allow 22/tcp comment 'SSH' || true
    ufw allow 443/tcp comment 'HTTPS' || true
    ufw allow 7777/tcp comment 'Cascade Monitor' || true
    ufw --force enable || true
fi

# 6. Journald log limit configuration (prevent SSD disk saturation)
log "[6/7] Restricting journald log retention to 50MB..."
mkdir -p /etc/systemd/journald.conf.d
cat << 'EOF' > /etc/systemd/journald.conf.d/vazus.conf
[Journal]
SystemMaxUse=50M
MaxRetentionSec=7d
EOF
systemctl restart systemd-journald || true

# 7. Install and enable systemd unit
log "[7/7] Installing vazus-flywheel.service with cgroup memory limits..."
SERVICE_FILE="/etc/systemd/system/vazus-flywheel.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$SCRIPT_DIR/vazus-flywheel.service" ]; then
    cp "$SCRIPT_DIR/vazus-flywheel.service" "$SERVICE_FILE"
else
    cat << 'EOF' > "$SERVICE_FILE"
[Unit]
Description=Vazus Flywheel Headless VPS Orchestration Daemon (Tier 0)
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/vazus-flywheel
EnvironmentFile=/etc/vazus/flywheel.env
ExecStart=/opt/vazus-flywheel/venv/bin/python3 -m vazus_autonomous_harness.daemon.vps_daemon
Restart=always
RestartSec=10

# Strict Resource Governance (<= 200 MB RAM Budget on 1 GB VPS)
MemoryAccounting=yes
MemoryHigh=160M
MemoryMax=200M
MemorySwapMax=50M
CPUQuota=50%

# Security & Sandboxing (Zero Plaintext Invariant)
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/opt/vazus-flywheel/data /var/log/vazus
PrivateTmp=yes
NoNewPrivileges=yes

[Install]
WantedBy=multi-user.target
EOF
fi

chmod 0644 "$SERVICE_FILE"
systemctl daemon-reload
systemctl enable vazus-flywheel.service

log "=== Setup Target 1 (1 GB VPS) Complete ==="
log "Verify service status: systemctl status vazus-flywheel"
log "Verify memory limits:  systemctl show vazus-flywheel --property=MemoryMax,MemoryHigh"
