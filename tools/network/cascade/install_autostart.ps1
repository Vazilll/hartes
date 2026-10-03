# Vazus Cascade - AutoStart Installer
# Autostart winws.exe via Scheduled Task (SYSTEM, Highest)
# Run from any PowerShell - auto-elevates to Admin

$TaskName  = "VazusCascadeZapret"
$WINWS     = "C:\Users\Vaz\zapret\zapret-v72.13\binaries\windows-x86_64\winws.exe"
$FAKE      = "C:\Users\Vaz\zapret\zapret-v72.13\binaries\windows-x86_64"
$LogPath   = "C:\vazus\cascade\zapret_task.log"

# ---- Auto-elevate if not admin ----
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdmin) {
    Write-Host "Not admin - re-launching as Administrator..." -ForegroundColor Yellow
    $args2 = '-ExecutionPolicy Bypass -File "' + $MyInvocation.MyCommand.Path + '"'
    Start-Process powershell.exe -ArgumentList $args2 -Verb RunAs
    exit
}

Write-Host "Installing Vazus Cascade Autostart (running as Admin)..." -ForegroundColor Cyan

# ---- Remove old task ----
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "Old task removed (if any)"

# ---- Build argument string ----
$ArgStr = (
    '--wf-tcp=80,443 --wf-udp=443,50000-65535 ' +
    '--filter-tcp=80 --dpi-desync=fake,disorder2 --dpi-desync-ttl=4 ' +
    '--dpi-desync-fake-http="' + $FAKE + '\http_iana_org.bin" --new ' +
    '--filter-tcp=443 --dpi-desync=fake,disorder2 --dpi-desync-ttl=4 ' +
    '--dpi-desync-repeats=6 ' +
    '--dpi-desync-fake-tls="' + $FAKE + '\tls_clienthello_www_google_com.bin" --new ' +
    '--filter-udp=443 --dpi-desync=fake --dpi-desync-repeats=6 ' +
    '--dpi-desync-fake-quic="' + $FAKE + '\quic_initial_www_google_com.bin"'
)

# ---- Create Task components ----
$Action    = New-ScheduledTaskAction -Execute $WINWS -Argument $ArgStr
$Trigger   = New-ScheduledTaskTrigger -AtStartup
$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest -LogonType ServiceAccount
$Settings  = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

# ---- Register ----
$Task = Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Settings $Settings `
    -Description "Vazus DPI bypass - winws.exe autostart" `
    -ErrorAction Stop

if ($Task) {
    Write-Host "[OK] Task '$TaskName' registered" -ForegroundColor Green

    # Start immediately
    Write-Host "Starting task now..."
    Start-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 4

    $proc = Get-Process -Name "winws" -ErrorAction SilentlyContinue
    if ($proc) {
        $pid2 = $proc.Id
        Write-Host "[OK] winws.exe is RUNNING (PID: $pid2)" -ForegroundColor Green
    } else {
        Write-Host "[WARN] winws.exe not in process list yet." -ForegroundColor Yellow
        Write-Host "       It will auto-start on next reboot."
        Write-Host "       Or run manually as Admin: $WINWS $ArgStr"
    }
}

Write-Host ""
Write-Host "Scheduled task status:" -ForegroundColor Cyan
Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue |
    Select-Object TaskName, State, @{N='LastRun';E={$_.LastRunTime}}
