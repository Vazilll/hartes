# Antigravity launcher with Hiddify proxy
# Port 12334 - HTTP proxy from Hiddify
# Запускай этот скрипт вместо ярлыка Antigravity

$PROXY = "http://127.0.0.1:12334"

$env:HTTP_PROXY = $PROXY
$env:HTTPS_PROXY = $PROXY
$env:http_proxy = $PROXY
$env:https_proxy = $PROXY
$env:NO_PROXY = "localhost,127.0.0.1,::1"
$env:no_proxy = "localhost,127.0.0.1,::1"

Write-Host "🚀 Launching Antigravity with Hiddify proxy ($PROXY)..."

$AGY_PATH = "$env:LOCALAPPDATA\Programs\antigravity\Antigravity.exe"
Start-Process -FilePath $AGY_PATH
