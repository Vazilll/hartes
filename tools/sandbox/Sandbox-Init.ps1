Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "  VAZUS SUPERGRAPH OS - ISOLATED SANDBOX BOOTSTRAP" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan

Write-Host "[1/4] Checking mapped architectural volumes..." -ForegroundColor Yellow
if (Test-Path "C:\Vazus") {
    Write-Host "  [OK] C:\Vazus workspace mounted." -ForegroundColor Green
}
if (Test-Path "C:\GeminiConfig") {
    Write-Host "  [OK] Gemini Config & Skills mounted." -ForegroundColor Green
    $targetGemini = "C:\Users\WDAGUtilityAccount\.gemini"
    New-Item -ItemType Directory -Path $targetGemini -Force | Out-Null
    Copy-Item -Path "C:\GeminiConfig\*" -Destination $targetGemini -Recurse -Force
    Write-Host "  [OK] Antigravity skills & config copied to user profile." -ForegroundColor Green
}

Write-Host "[2/4] Testing Vazus OS Core modules in Sandbox..." -ForegroundColor Yellow
if (Test-Path "C:\Vazus\.venv\Scripts\python.exe") {
    & "C:\Vazus\.venv\Scripts\python.exe" -c "
import vazus_core
from vazus_core.runtime import A2ARouter, A2UIRenderer, TaskTransferManager
from vazus_core.memory import AgentMemoryBank
from vazus_core.security import ModelArmor
print('  [SUCCESS] All Vazus OS Core modules + Enterprise Stack verified inside Sandbox!')
"
}

Write-Host "[3/4] Running 5-Tier Quality Gate verification inside Sandbox..." -ForegroundColor Yellow
if (Test-Path "C:\Vazus\.venv\Scripts\pytest.exe") {
    & "C:\Vazus\.venv\Scripts\pytest.exe" "C:\Vazus\tests\test_enterprise_stack.py" -v
}

Write-Host "[4/4] System ready! You can now start Antigravity in complete isolation." -ForegroundColor Cyan
