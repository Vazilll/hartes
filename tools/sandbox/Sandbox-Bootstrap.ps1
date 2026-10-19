# Vazus SuperGraph OS - Offline Sandbox Initializer
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'

Clear-Host
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "     VAZUS SUPERGRAPH OS & GOOGLE ANTIGRAVITY SANDBOX" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Mount Validation
Write-Host "[STEP 1/5] Validating Mapped Host Directories..." -ForegroundColor Yellow
$vazusRoot = "C:\Vazus"
$geminiConfig = "C:\GeminiConfig"

if (Test-Path $vazusRoot) {
    Write-Host "  [OK] Vazus Workspace mounted at $vazusRoot" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] $vazusRoot not found! Check .wsb MappedFolders." -ForegroundColor Red
    Exit 1
}

if (Test-Path $geminiConfig) {
    Write-Host "  [OK] Gemini / Antigravity config mounted at $geminiConfig" -ForegroundColor Green
    $targetProfile = "C:\Users\WDAGUtilityAccount\.gemini"
    New-Item -ItemType Directory -Path $targetProfile -Force | Out-Null
    Copy-Item -Path "$geminiConfig\*" -Destination $targetProfile -Recurse -Force
    Write-Host "  [OK] Antigravity skills, plugins, and rules deployed to user profile." -ForegroundColor Green
} else {
    Write-Host "  [WARNING] $geminiConfig not mapped." -ForegroundColor Yellow
}

# 2. Environment PATH configuration
Write-Host "`n[STEP 2/5] Configuring Execution PATH and Python Virtualenv..." -ForegroundColor Yellow
$venvPython = "C:\Vazus\.venv\Scripts\python.exe"
$venvPytest = "C:\Vazus\.venv\Scripts\pytest.exe"

if (Test-Path $venvPython) {
    $env:PATH = "C:\Vazus\.venv\Scripts;C:\Vazus\.venv;$env:PATH"
    Write-Host "  [OK] Python Virtualenv activated: $(& $venvPython --version)" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] Python executable not found at $venvPython" -ForegroundColor Red
    Exit 1
}

# 3. Import & Topology Verification
Write-Host "`n[STEP 3/5] Verifying Vazus Core & Enterprise Stack..." -ForegroundColor Yellow
$importResult = & $venvPython -c "
import sys
try:
    import vazus_core
    from vazus_core.runtime import A2ARouter, A2AMessage, A2UIRenderer, TaskTransferManager
    from vazus_core.memory import AgentMemoryBank, MemoryTier
    from vazus_core.security import ModelArmor
    print('  [SUCCESS] All core modules loaded cleanly: A2A, A2UI, MemoryBank, TaskTransfer, ModelArmor')
except Exception as e:
    print('  [FAIL] Import error:', e)
    sys.exit(1)
"
Write-Host $importResult -ForegroundColor Green

# 4. Run Pytest Suite
Write-Host "`n[STEP 4/5] Executing 5-Tier Quality Gate Tests..." -ForegroundColor Yellow
& $venvPytest "C:\Vazus\tests\test_enterprise_stack.py" -v --no-header

# 5. Desktop Shortcuts & Status
Write-Host "`n[STEP 5/5] Creating Sandbox Control Shortcuts..." -ForegroundColor Yellow
$desktopPath = [Environment]::GetFolderPath("Desktop")
$wsh = New-Item -Path "$desktopPath\Run-Tests.cmd" -ItemType File -Force -Value @"
@echo off
C:\Vazus\.venv\Scripts\pytest.exe C:\Vazus\tests\test_enterprise_stack.py -v
pause
"@
Write-Host "  [OK] Created 'Run-Tests.cmd' on Desktop" -ForegroundColor Green

Write-Host ""
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "  ISOLATED ENVIRONMENT READY: ZERO EXTERNAL NETWORK DEPENDENCY" -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host ""
