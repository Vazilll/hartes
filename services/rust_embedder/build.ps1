# vazus_embedder — PyO3 Rust Build Script
# Requires: Rust toolchain (rustup), Python 3.10+ venv

$ErrorActionPreference = "Stop"
$VenvPython = "C:\vazus\.venv\Scripts\python.exe"
$VenvPip    = "C:\vazus\.venv\Scripts\pip.exe"
$CrateDir   = $PSScriptRoot

Write-Host "=== [1/4] Checking Rust toolchain ===" -ForegroundColor Cyan
if (-not (Get-Command rustup -ErrorAction SilentlyContinue)) {
    Write-Error "rustup not found. Install from https://rustup.rs"
    exit 1
}
rustup show active-toolchain
rustup target add x86_64-pc-windows-msvc 2>$null

Write-Host "=== [2/4] Installing maturin into venv ===" -ForegroundColor Cyan
& $VenvPip install "maturin>=1.5" --quiet

Write-Host "=== [3/4] Building vazus_embedder.pyd (release) ===" -ForegroundColor Cyan
Set-Location $CrateDir
& $VenvPython -m maturin develop --release

Write-Host "=== [4/4] Smoke test ===" -ForegroundColor Cyan
& $VenvPython -c @"
import vazus_embedder as ve
vecs = ve.embed_texts(['test sentence', 'another sentence'])
print(f'embed_texts: {len(vecs)} vectors, dim={len(vecs[0])}')
sim = ve.cosine_similarity(vecs[0], vecs[1])
print(f'cosine_similarity: {sim:.4f}')
top = ve.batch_top_k(vecs[0], vecs, 2)
print(f'batch_top_k: {top}')
blob = ve.pack_f32(vecs[0])
back = ve.unpack_f32(blob)
print(f'pack/unpack roundtrip: {len(back)} floats, match={vecs[0][:3] == back[:3]}')
print('ALL OK')
"@

Write-Host ""
Write-Host "=== BUILD COMPLETE ===" -ForegroundColor Green
Write-Host "To upgrade embed_texts() to real Candle inference:" -ForegroundColor Yellow
Write-Host "  1. Download model: huggingface-cli download BAAI/bge-small-en-v1.5 --local-dir C:\vazus\models\bge-small" -ForegroundColor Yellow
Write-Host "  2. Edit src/lib.rs — replace pseudo-embedding section with candle-transformers BertModel" -ForegroundColor Yellow
Write-Host "  3. Re-run this script" -ForegroundColor Yellow
