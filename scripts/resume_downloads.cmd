@echo off
setlocal enabledelayedexpansion
set PYTHONIOENCODING=utf-8
set PYTHON_EXE=C:\vazus\pyenv\.venv\Scripts\python.exe

echo ====== RESILIENT MODEL DOWNLOADER ======
echo Target folder: C:\vazus\models
echo.

:ZAYA_LOOP
echo [1/2] Attempting to download ZAYA1-8B...
%PYTHON_EXE% -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='Abiray/ZAYA1-8B-GGUF', filename='ZAYA1-8B-Q4_K_M.gguf', local_dir='C:/vazus/models', resume_download=True)"
if %ERRORLEVEL% NEQ 0 (
    echo ZAYA download failed or interrupted. Retrying in 10 seconds...
    timeout /t 10 /nobreak >nul
    goto ZAYA_LOOP
)
echo [OK] ZAYA1-8B Downloaded!
echo.

:RWKV_LOOP
echo [2/2] Attempting to download RWKV-7 G1g...
%PYTHON_EXE% -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='shoumenchougou/RWKV7-G1g-2.9B-GGUF', filename='rwkv7-g1g-2.9b-Q4_K_M.gguf', local_dir='C:/vazus/models', resume_download=True)"
if %ERRORLEVEL% NEQ 0 (
    echo RWKV download failed or interrupted. Retrying in 10 seconds...
    timeout /t 10 /nobreak >nul
    goto RWKV_LOOP
)
echo [OK] RWKV-7 G1g Downloaded!
echo.
echo ALL DOWNLOADS COMPLETE!
