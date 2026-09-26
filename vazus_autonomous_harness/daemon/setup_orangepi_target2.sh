#!/bin/bash
# ==============================================================================
# Vazus Autonomous Absolute AI Flywheel -- Setup Target 2
# Target: Orange Pi 4 Pro (6 GB RAM, 6-core ARM64) -- Home Edge Server Node
# Architecture: Tier 1.5 Home Edge Anchor (Continuous 24/7 SMT Z3 + Git Sync)
# Memory Allocation: 6 GB RAM available (Worker capped at 2.5 GB via cgroups)
# ==============================================================================

set -e

LOG_FILE="/var/log/vazus/orangepi_setup.log"
mkdir -p /var/log/vazus
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "=== Starting Vazus Flywheel Tier 1.5 Orange Pi Setup (Target 2) ==="
ARCH=$(uname -m)
log "Host: $(hostname) | Kernel: $(uname -r) | Arch: $ARCH"

# 1. Architecture sanity check
if [ "$ARCH" != "aarch64" ] && [ "$ARCH" != "arm64" ]; then
    log "[WARNING] Detected non-ARM64 architecture ($ARCH). Target 2 is optimized for ARM64/aarch64."
fi

# 2. System dependencies & native Z3 solver libraries
log "[1/7] Updating apt repositories and installing ARM64 development toolchain..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
    curl wget git jq build-essential \
    python3 python3-pip python3-venv \
    libz3-dev python3-z3 \
    fail2ban ufw htop

# 3. Workspace directories
log "[2/7] Initializing /opt/vazus-edge workspace..."
mkdir -p /opt/vazus-edge/data
mkdir -p /opt/vazus-edge/repo
mkdir -p /opt/vazus-edge/artifacts/vault/colab_queue/inbox
mkdir -p /opt/vazus-edge/artifacts/vault/colab_queue/active
mkdir -p /opt/vazus-edge/artifacts/vault/colab_queue/outbox
mkdir -p /etc/vazus

# 4. Isolated Python 3 virtualenv with native Z3 solver bindings
log "[3/7] Setting up isolated Python virtualenv with native SMT Z3..."
if [ ! -d "/opt/vazus-edge/venv" ]; then
    python3 -m venv --system-site-packages /opt/vazus-edge/venv
fi
/opt/vazus-edge/venv/bin/pip install --upgrade pip -q
/opt/vazus-edge/venv/bin/pip install -q httpx psutil z3-solver pytest

# 5. Native ARM64 Z3 solver verification
log "[4/7] Verifying native ARM64 SMT Z3 formal proof engine..."
/opt/vazus-edge/venv/bin/python3 -c "
import z3
s = z3.Solver()
p = z3.Bool('p')
s.add(p == True)
assert str(s.check()) == 'sat'
print('SMT Z3 ARM64 Formal Gate Verified: sat')
" | tee -a "$LOG_FILE"

# 6. Secure environment configuration (Strict 0600 permissions, zero plaintext secrets)
log "[5/7] Generating /etc/vazus/edge.env with 0600 permissions..."
EDGE_ENV="/etc/vazus/edge.env"
if [ ! -f "$EDGE_ENV" ]; then
    cat << 'EOF' > "$EDGE_ENV"
# /etc/vazus/edge.env -- Strict 0600 permissions
VAZUS_ROLE=tier1_5_edge
NODE_ID=orangepi4pro_edge_01
TIER=Tier1_5_Edge
CAPABILITIES=SMT_Z3,ARM64_SOLVER,GIT_SYNC,QUANT_LLM
MEMORY_LIMIT_MB=2500.0
MEMORY_WARNING_MB=2200.0
VPS_COORDINATOR_URL=http://157.228.174.15:7777
# Runtime secrets injected securely via vault (NEVER commit plaintext secrets)
GITHUB_TOKEN=
JULES_API_KEY=
EOF
fi

chown root:root "$EDGE_ENV"
chmod 0600 "$EDGE_ENV"
log "Secured $EDGE_ENV permissions: $(stat -c '%a %U:%G' "$EDGE_ENV" 2>/dev/null || echo '0600 root:root')"

# 7. Systemd service installation (6 GB RAM allocation - 2.5 GB worker cgroup cap)
log "[6/7] Installing vazus-edge-worker.service..."
EDGE_SERVICE="/etc/systemd/system/vazus-edge-worker.service"
cat << 'EOF' > "$EDGE_SERVICE"
[Unit]
Description=Vazus Edge Worker & Formal SMT Verification Engine (Tier 1.5)
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/vazus-edge
EnvironmentFile=/etc/vazus/edge.env
ExecStart=/opt/vazus-edge/venv/bin/python3 -m vazus_autonomous_harness.daemon.vps_daemon
Restart=always
RestartSec=10

# Resource Allocation (6 GB RAM Headroom - Capped at 2.5 GB)
MemoryAccounting=yes
MemoryHigh=2200M
MemoryMax=2500M
MemorySwapMax=500M
CPUQuota=300%

# Security & Sandboxing (Zero Plaintext Invariant)
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/opt/vazus-edge/data /opt/vazus-edge/repo /var/log/vazus
PrivateTmp=yes
NoNewPrivileges=yes

[Install]
WantedBy=multi-user.target
EOF

chmod 0644 "$EDGE_SERVICE"
systemctl daemon-reload
systemctl enable vazus-edge-worker.service

# 8. Git automation and fast-forward sync helper
log "[7/7] Setting up background git fast-forward automation helper..."
cat << 'EOF' > /opt/vazus-edge/git_sync_safe.sh
#!/bin/bash
set -e
REPO_DIR="/opt/vazus-edge/repo"
if [ -d "$REPO_DIR/.git" ]; then
    cd "$REPO_DIR"
    git fetch origin --prune
    # Fast-forward only to prevent split-brain state divergence
    git merge --ff-only origin/vazus-dev || git merge --ff-only origin/main || {
        echo "[GIT-SYNC] Fast-forward diverged. Keeping local working tree clean."
        exit 1
    }
fi
EOF
chmod +x /opt/vazus-edge/git_sync_safe.sh

log "=== Setup Target 2 (Orange Pi 4 Pro ARM64) Complete ==="
log "Verify native Z3: /opt/vazus-edge/venv/bin/python3 -c 'import z3; print(z3.Solver().check())'"
log "Verify service:   systemctl status vazus-edge-worker"
