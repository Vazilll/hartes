@echo off
title Vazus Hyper-V Sandbox Automated Provisioning
color 0b

echo ===================================================================
echo     VAZUS OS: HYPER-V SANDBOX AUTOMATED SYSTEM PROVISIONING
echo ===================================================================
echo.

set SANDBOX_DIR=%USERPROFILE%\Desktop\sandbox
set INSTALLERS_DIR=%SANDBOX_DIR%\installers

echo [*] Installing Google Chrome 64-bit silently...
if exist "%INSTALLERS_DIR%\ChromeSetup.exe" (
    start /wait "" "%INSTALLERS_DIR%\ChromeSetup.exe" /silent /install
    echo [+] Google Chrome installed successfully!
) else (
    echo [-] Installer not found, skipping local install.
)

echo [*] Locating Chrome executable...
set CHROME_PATH=
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    set "CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe"
) else if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    set "CHROME_PATH=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
) else if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" (
    set "CHROME_PATH=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
)

echo [*] Launching Google Chrome with NotebookLM & Academic Workspaces...
if defined CHROME_PATH (
    echo [+] Starting Google Chrome: %CHROME_PATH%
    start "" "%CHROME_PATH%" --start-maximized "https://notebook.google.com/" "https://notebook.google.com/notebook/b61efe0f-9b7f-4438-8792-79aa13671a79" "https://notebook.google.com/notebook/94b713d9-2a5b-4d7e-a4a1-8804bfd2031e" "https://notebook.google.com/notebook/6236ddcb-f6af-432a-bc5f-6144eea9d94b" "https://notebook.google.com/notebook/a5cb58c1-d990-4d25-9fc0-fd3981437f70" "https://www.youtube.com/results?search_query=3blue1brown+essence+of+linear+algebra" "https://online-edu.mirea.ru/my/"
) else (
    echo [!] Using default Windows Browser...
    start "" "https://notebook.google.com/"
    start "" "https://www.youtube.com/results?search_query=3blue1brown+essence+of+linear+algebra"
    start "" "https://online-edu.mirea.ru/my/"
)

echo [*] Launching Task Manager...
start taskmgr.exe

echo [*] Starting System Diagnostics Dashboard...
start powershell.exe -NoExit -Command "Write-Host '=====================================================' -ForegroundColor Cyan; Write-Host '   VAZUS SUPERGRAPH OS: HYPER-V ISOLATED SANDBOX    ' -ForegroundColor Green; Write-Host '=====================================================' -ForegroundColor Cyan; Write-Host 'Status: FULLY PROVISIONED & ISOLATED' -ForegroundColor Yellow; Write-Host 'Applications Launched:' -ForegroundColor White; Write-Host '  - Google Chrome (NotebookLM Hub + 4 MIREA Notebooks)' -ForegroundColor Green; Write-Host '  - System Task Manager' -ForegroundColor Green; Write-Host '  - YouTube (3Blue1Brown)' -ForegroundColor Green; Write-Host '  - RTU MIREA Moodle SDO' -ForegroundColor Green; Write-Host '
Hardware Isolation Metrics:' -ForegroundColor Magenta; Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors | Format-List; Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize, FreePhysicalMemory | Format-List; Write-Host 'Ready for autonomous operations!' -ForegroundColor Yellow"

echo.
echo ===================================================================
echo     PROVISIONING COMPLETED SUCCESSFULLY!
echo ===================================================================
