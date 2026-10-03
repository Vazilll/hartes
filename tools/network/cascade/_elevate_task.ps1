$TaskName = 'VazusCascadeZapret'
$WINWS = 'C:\Users\Vaz\zapret\zapret-v72.13\binaries\windows-x86_64\winws.exe'.Replace('\','\\')
$ArgStr = '--wf-tcp=80,443 --wf-udp=443,50000-65535 --filter-tcp=80 --dpi-desync=fake,disorder2 --dpi-desync-ttl=4 --dpi-desync-fake-http="C:\Users\Vaz\zapret\zapret-v72.13\binaries\windows-x86_64\http_iana_org.bin" --new --filter-tcp=443 --dpi-desync=fake,disorder2 --dpi-desync-ttl=4 --dpi-desync-repeats=6 --dpi-desync-fake-tls="C:\Users\Vaz\zapret\zapret-v72.13\binaries\windows-x86_64\tls_clienthello_www_google_com.bin" --new --filter-udp=443 --dpi-desync=fake --dpi-desync-repeats=6 --dpi-desync-fake-quic="C:\Users\Vaz\zapret\zapret-v72.13\binaries\windows-x86_64\quic_initial_www_google_com.bin"'
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
$Action = New-ScheduledTaskAction -Execute 'C:\Users\Vaz\zapret\zapret-v72.13\binaries\windows-x86_64\winws.exe' -Argument $ArgStr
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -RunLevel Highest -LogonType ServiceAccount
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Description 'Vazus winws DPI bypass'
Start-ScheduledTask -TaskName $TaskName
Start-Sleep 3
$proc = Get-Process -Name 'winws' -ErrorAction SilentlyContinue
if ($proc) { Write-Host 'RUNNING PID=' + $proc.Id } else { Write-Host 'NOT RUNNING' }
