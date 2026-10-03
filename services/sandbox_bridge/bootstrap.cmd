@echo off
set "DIR=%~dp0"
echo [%date% %time%] Bootstrap starting in %DIR% > "%DIR%ipc\bootstrap.log"

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "& { try { $d = '%DIR%'; $r = Join-Path $d 'ipc\guest_ready.json'; [System.IO.File]::WriteAllText($r, '{\"status\":\"ready\",\"pid\":' + $PID + '}'); & '%DIR%guest_agent.ps1' } catch { [System.IO.File]::WriteAllText((Join-Path '%DIR%' 'ipc\ps_err.log'), $_.ToString()) } }" >> "%DIR%ipc\bootstrap.log" 2>&1