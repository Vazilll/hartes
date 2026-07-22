# System health check
$cpu = Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, LoadPercentage
Write-Host "=== CPU ==="
Write-Host "Name: $($cpu.Name)"
Write-Host "Cores: $($cpu.NumberOfCores) physical, $($cpu.NumberOfLogicalProcessors) logical"
Write-Host "Load: $($cpu.LoadPercentage)%"

$os = Get-CimInstance Win32_OperatingSystem
$totalRAM = [math]::Round($os.TotalVisibleMemorySize/1MB, 1)
$freeRAM = [math]::Round($os.FreePhysicalMemory/1MB, 1)
$usedRAM = $totalRAM - $freeRAM
Write-Host "`n=== RAM ==="
Write-Host "Total: ${totalRAM} GB"
Write-Host "Used: ${usedRAM} GB"
Write-Host "Free: ${freeRAM} GB"

Write-Host "`n=== DISK ==="
Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object {
    $total = [math]::Round($_.Size/1GB, 1)
    $free = [math]::Round($_.FreeSpace/1GB, 1)
    $used = $total - $free
    $pct = [math]::Round($used/$total*100, 1)
    Write-Host "$($_.DeviceID): ${used} GB / ${total} GB used (${pct}%), ${free} GB free"
}
