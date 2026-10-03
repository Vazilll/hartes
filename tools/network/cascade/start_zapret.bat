@echo off
:: ============================================================
:: VAZUS CASCADE — Zapret winws.exe Full DPI Bypass Launcher
:: v72.13 | YouTube, Discord, QUIC, WireGuard
:: Запускать от АДМИНИСТРАТОРА
:: ============================================================
setlocal
set "ZAPRET=C:\Users\Vaz\zapret\zapret-v72.13\binaries\windows-x86_64"
set "CASCADE=C:\vazus\cascade"
set "LOG=%CASCADE%\zapret.log"
set "WINWS=%ZAPRET%\winws.exe"

echo [%date% %time%] === Vazus Cascade Zapret Starting === >> "%LOG%"

:: Права администратора
net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo Run as Administrator!
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b 1
)

:: Убить старые
taskkill /F /IM winws.exe /T >nul 2>&1
timeout /t 1 /nobreak >nul
echo [%date% %time%] Old instances killed >> "%LOG%"

:: ===== Проверяем наличие бинаря =====
if not exist "%WINWS%" (
    echo [ERROR] winws.exe not found at %WINWS%
    echo [ERROR] winws.exe not found >> "%LOG%"
    pause
    exit /b 1
)

:: ===== ЗАПУСК WINWS =====
:: Стратегия 1: HTTP (port 80) - fake + disorder
:: Стратегия 2: TLS/HTTPS (port 443) - fake + disorder2 
:: Стратегия 3: QUIC/UDP 443 - fake repeats  
:: Стратегия 4: WireGuard UDP range

start "" /MIN "%WINWS%" ^
  --wf-tcp=80,443 ^
  --wf-udp=443,50000-65535 ^
  --filter-tcp=80 ^
    --dpi-desync=fake,disorder2 ^
    --dpi-desync-ttl=4 ^
    --dpi-desync-fake-http="%ZAPRET%\http_iana_org.bin" ^
  --new ^
  --filter-tcp=443 ^
    --dpi-desync=fake,disorder2 ^
    --dpi-desync-ttl=4 ^
    --dpi-desync-repeats=6 ^
    --dpi-desync-fake-tls="%ZAPRET%\tls_clienthello_www_google_com.bin" ^
  --new ^
  --filter-udp=443 ^
    --dpi-desync=fake ^
    --dpi-desync-repeats=6 ^
    --dpi-desync-fake-quic="%ZAPRET%\quic_initial_www_google_com.bin" ^
  --new ^
  --filter-udp=50000-65535 ^
    --dpi-desync=fake ^
    --dpi-desync-fake-wireguard="%ZAPRET%\wireguard_initiation.bin"

echo [%date% %time%] winws.exe started OK >> "%LOG%"
echo [OK] Zapret DPI bypass running. Log: %LOG%
