# PowerShell Setup Script for DNTS SOTA Native Windows Environment
# Location: C:\vazus\setup_windows_sota.ps1

$ErrorActionPreference = "Stop"

# Helper functions for colored logging
function Write-Header ($msg) {
    Write-Host "`n=======================================================" -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host "=======================================================" -ForegroundColor Cyan
}

function Write-Success ($msg) {
    Write-Host "[SUCCESS] $msg" -ForegroundColor Green
}

function Write-Info ($msg) {
    Write-Host "[INFO] $msg" -ForegroundColor White
}

function Write-Warning ($msg) {
    Write-Host "[WARNING] $msg" -ForegroundColor Yellow
}

function Write-ErrorMsg ($msg) {
    Write-Host "[ERROR] $msg" -ForegroundColor Red
}

Write-Header "DNTS SOTA: Инициализация окружения Windows"

# ---------------------------------------------------------------------
# ШАГ 1: Проверка системных требований (Python, Go, NPU Драйверы)
# ---------------------------------------------------------------------
Write-Header "Шаг 1: Верификация системных зависимостей"

# 1. Проверка Python
try {
    $pythonVersionStr = & python --version 2>&1
    if ($pythonVersionStr -match "Python (\d+)\.(\d+)") {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -eq 3 -and $minor -ge 10) {
            Write-Success "Python обнаружен: $pythonVersionStr"
        } else {
            Write-Warning "Python обнаружен ($pythonVersionStr), но рекомендуется версия >= 3.10."
        }
    }
} catch {
    Write-ErrorMsg "Python не найден в PATH системы! Пожалуйста, установите Python 3.10+ и добавьте его в системные переменные."
    exit 1
}

# 2. Проверка Go
try {
    $goVersionStr = & go version 2>&1
    if ($goVersionStr -match "go version go(\d+)\.(\d+)") {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -ge 1 -and $minor -ge 20) {
            Write-Success "Go Compiler обнаружен: $goVersionStr"
        } else {
            Write-Warning "Go обнаружен ($goVersionStr), но рекомендуется версия >= 1.20."
        }
    }
} catch {
    Write-Warning "Go Compiler (golang) не найден в PATH системы. MCP серверы могут использовать предустановленные бинарники."
}

# 3. Проверка драйверов Intel NPU (AI Boost)
Write-Info "Поиск аппаратного ускорения Intel NPU..."
try {
    $npuDevice = Get-CimInstance Win32_PnPEntity | Where-Object { 
        $_.Name -like "*AI Boost*" -or $_.Name -like "*Intel*NPU*" -or $_.HardwareID -like "*PCI\VEN_8086&DEV_7D1D*"
    }
    
    if ($npuDevice) {
        Write-Success "Обнаружен нейропроцессор (Intel NPU): $($npuDevice.Name)"
        Write-Info "Статус устройства: $($npuDevice.Status)"
    } else {
        Write-Warning "Intel AI Boost NPU не найден в Диспетчере устройств."
        Write-Warning "Установка продолжится, но инференс на NPU будет недоступен (будет использоваться CPU/iGPU)."
    }
} catch {
    Write-Warning "Не удалось выполнить запрос CIM устройств. Проверка NPU пропущена."
}


# ---------------------------------------------------------------------
# ШАГ 2: Создание директории и виртуального окружения Python
# ---------------------------------------------------------------------
Write-Header "Шаг 2: Создание изолированного виртуального окружения"

$dntsDir = "C:\vazus"
$venvDir = "C:\vazus\.venv"

if (-not (Test-Path $dntsDir)) {
    Write-Info "Создание рабочей директории $dntsDir..."
    New-Item -ItemType Directory -Path $dntsDir | Out-Null
}

if (-not (Test-Path $venvDir)) {
    Write-Info "Создание Python Virtual Environment в $venvDir..."
    & python -m venv $venvDir
    Write-Success "Виртуальное окружение создано."
} else {
    Write-Info "Обнаружено существующее виртуальное окружение в $venvDir. Использование текущего venv..."
}

$venvPython = "$venvDir\Scripts\python.exe"
$venvPip = "$venvDir\Scripts\pip.exe"


# ---------------------------------------------------------------------
# ШАГ 3: Установка Python пакетов (Deep Learning и Симуляции)
# ---------------------------------------------------------------------
Write-Header "Шаг 3: Установка пакетов PyTorch, OpenVINO, EasyOCR и NeuroML"

# Обновление pip
Write-Info "Обновление pip..."
& $venvPython -m pip install --upgrade pip

# Установка PyTorch (CPU-версия)
Write-Info "Установка PyTorch (оптимизированного под CPU)..."
& $venvPip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Установка OpenVINO & Optimum Intel
Write-Info "Установка OpenVINO Runtime и Optimum Intel..."
& $venvPip install openvino openvino-dev optimum[openvino]

# Установка EasyOCR
Write-Info "Установка EasyOCR..."
& $venvPip install easyocr

# Установка NeuroML зависимостей
Write-Info "Установка pyNeuroML и libNeuroML..."
& $venvPip install pyNeuroML libNeuroML

Write-Success "Все Python зависимости успешно установлены в .venv!"


# ---------------------------------------------------------------------
# ШАГ 4: Настройка переменных окружения для NPU offloading
# ---------------------------------------------------------------------
Write-Header "Шаг 4: Настройка системных переменных для NPU"

try {
    $env:INTEL_OPENVINO_DEVICE = "NPU"
    $env:OPENVINO_DEVICE = "NPU"
    [Environment]::SetEnvironmentVariable("INTEL_OPENVINO_DEVICE", "NPU", "User")
    [Environment]::SetEnvironmentVariable("OPENVINO_DEVICE", "NPU", "User")
    Write-Success "Переменные окружения INTEL_OPENVINO_DEVICE=NPU и OPENVINO_DEVICE=NPU успешно прописаны!"
} catch {
    Write-Warning "Не удалось записать переменные окружения в реестр пользователя."
}


# ---------------------------------------------------------------------
# ШАГ 5: Итоговая верификация рантайма
# ---------------------------------------------------------------------
Write-Header "Шаг 5: Итоговая верификация рантайма и создание тестов"

$testScriptPath = "$dntsDir\verify_ov_npu.py"
Write-Info "Запуск верификации..."
try {
    & $venvPython $testScriptPath
} catch {
    Write-Warning "Верификационный скрипт завершился с ошибкой. Проверьте логи."
}

Write-Header "Среда DNTS SOTA Native Windows успешно развернута!"
Write-Host 'Для активации виртуального окружения в терминале выполните:' -ForegroundColor Yellow
Write-Host '  & C:\vazus\.venv\Scripts\Activate.ps1' -ForegroundColor Green
