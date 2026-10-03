@echo off
:: Vazus VPN Route Fix - запускать от Администратора
:: Добавляет постоянный маршрут к VPS через МТС-шлюз
:: Маршрут переживает перезагрузку (-p = persistent)

set VPS=157.228.174.15
set GW=10.29.116.77

echo ===============================
echo  Vazus VPN Route Fix
echo  VPS: %VPS%
echo  Gateway (МТС): %GW%
echo ===============================
echo.

:: Удаляем старый маршрут если есть
route delete %VPS% >nul 2>&1

:: Добавляем постоянный маршрут (-p = persistent, выживет после ребута)
route -p add %VPS% mask 255.255.255.255 %GW% metric 1
if %ERRORLEVEL% == 0 (
    echo [OK] Маршрут добавлен!
) else (
    echo [ERROR] Ошибка - запусти от Администратора!
    pause
    exit /b 1
)

echo.
echo === Проверка маршрута ===
route print %VPS%

echo.
echo ===============================
echo  Готово! Теперь:
echo  1. Подключись к AmneziaVPN
echo  2. Интернет должен работать
echo ===============================
pause
