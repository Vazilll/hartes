# Vazus VPN Route Fix
# Запускать от Администратора - добавляет маршрут к VPS через реальный шлюз
# чтобы AmneziaVPN не создавал routing loop

$VPS_IP   = "157.228.174.15"
$GATEWAY  = "10.29.116.77"
$IFACE    = "Wi-Fi 2"

Write-Host "=== Vazus VPN Route Fix ===" -ForegroundColor Cyan
Write-Host "VPS:     $VPS_IP"
Write-Host "Gateway: $GATEWAY"
Write-Host "Iface:   $IFACE"
Write-Host ""

# Удаляем старый маршрут к VPS если есть
$existing = Get-NetRoute -DestinationPrefix "$VPS_IP/32" -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removing old route..." -ForegroundColor Yellow
    Remove-NetRoute -DestinationPrefix "$VPS_IP/32" -Confirm:$false -ErrorAction SilentlyContinue
}

# Добавляем маршрут: трафик к VPS идёт через реальный МТС-шлюз, минуя VPN
Write-Host "Adding bypass route for VPS..." -ForegroundColor Green
$iface_idx = (Get-NetAdapter -Name $IFACE).ifIndex
New-NetRoute -DestinationPrefix "$VPS_IP/32" `
             -InterfaceIndex $iface_idx `
             -NextHop $GATEWAY `
             -RouteMetric 1 `
             -PolicyStore ActiveStore `
             -ErrorAction SilentlyContinue

# Проверяем
Write-Host ""
Write-Host "=== Result ===" -ForegroundColor Cyan
Get-NetRoute -DestinationPrefix "$VPS_IP/32" | Format-Table DestinationPrefix, NextHop, InterfaceAlias, RouteMetric

Write-Host "=== Default route ===" -ForegroundColor Cyan
Get-NetRoute -DestinationPrefix "0.0.0.0/0" | Format-Table DestinationPrefix, NextHop, InterfaceAlias, RouteMetric

Write-Host ""
Write-Host "ГОТОВО. Теперь:" -ForegroundColor Green
Write-Host "1. Подключись к AmneziaVPN"
Write-Host "2. Интернет должен работать"
Write-Host ""
Write-Host "Если VPN переподключится - запусти скрипт снова" -ForegroundColor Yellow
Write-Host "(маршрут ActiveStore не переживает переподключение VPN)"
