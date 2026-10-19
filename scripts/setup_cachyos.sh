#!/usr/bin/env bash
# ==============================================================================
# Vazus OS — Turnkey CachyOS / Arch Linux Deployment Script
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAZUS_DIR="${VAZUS_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"

echo "=========================================================="
echo "  Vazus OS — CachyOS Native Installation                  "
echo "  Location: ${VAZUS_DIR}                                  "
echo "=========================================================="

# 1. Install optimized CachyOS / Arch native packages
echo "[1/6] Installing system packages via pacman..."
sudo pacman -S --needed --noconfirm \
    base-devel \
    gcc \
    clang \
    cmake \
    openmp \
    bubblewrap \
    cloudflared \
    wl-clipboard \
    xclip \
    libnotify \
    ripgrep \
    z3 \
    nodejs \
    npm \
    uv

# 2. Configure VAZUS_ROOT environment
echo "[2/6] Configuring VAZUS_ROOT at ${VAZUS_DIR}..."
export VAZUS_ROOT="${VAZUS_DIR}"

if ! grep -q "VAZUS_ROOT" "${HOME}/.bashrc"; then
    echo "export VAZUS_ROOT=\"${VAZUS_DIR}\"" >> "${HOME}/.bashrc"
    echo "export PYTHONPATH=\"\${VAZUS_ROOT}:\${PYTHONPATH:-}\"" >> "${HOME}/.bashrc"
fi

# 3. Setup Python Virtual Environment via uv (Hermetic Python 3.12)
echo "[3/6] Initializing Python 3.12 Virtual Environment via uv..."
if [ ! -d "${VAZUS_DIR}/.venv" ]; then
    uv venv "${VAZUS_DIR}/.venv" --python 3.12
fi
source "${VAZUS_DIR}/.venv/bin/activate"

# 4. Install Python Dependencies
echo "[4/6] Installing Python dependencies..."
uv pip install -r "${VAZUS_DIR}/requirements.txt" pytest pytest-asyncio ruff

# 5. Compile Native SIMD Vector Kernel on CachyOS
echo "[5/6] Compiling libavx512_cosine.so with CachyOS GCC..."
if [ -f "${VAZUS_DIR}/vazus_core/avx512_cosine.c" ]; then
    gcc -O3 -march=native -fopenmp -fPIC -shared \
        -o "${VAZUS_DIR}/vazus_core/libavx512_cosine.so" \
        "${VAZUS_DIR}/vazus_core/avx512_cosine.c" -lm
    echo "✓ libavx512_cosine.so compiled successfully."
fi

# 6. Verify Installation
echo "[6/6] Verifying installation..."
python -c "
import sys
from pathlib import Path
sys.path.insert(0, '${VAZUS_DIR}')
from vazus_core.paths import VAZUS_ROOT, DEFAULT_DB_PATH
print(f'✓ VAZUS_ROOT resolved: {VAZUS_ROOT}')
print(f'✓ DEFAULT_DB_PATH: {DEFAULT_DB_PATH}')
"

echo "=========================================================="
echo "  Vazus OS successfully deployed on CachyOS!              "
echo "=========================================================="
