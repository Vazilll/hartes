# ==============================================================================
# Vazus Real-Time Event-Driven Zero-Interference Guest Agent
# ==============================================================================

$desktop = [Environment]::GetFolderPath("Desktop")
$BridgeDir = Join-Path $desktop "sandbox_bridge"
if (-not (Test-Path $BridgeDir)) {
    if ($PSScriptRoot -and (Test-Path $PSScriptRoot)) { $BridgeDir = $PSScriptRoot }
    elseif (Test-Path "C:\SandboxBridge") { $BridgeDir = "C:\SandboxBridge" }
}

$IpcDir = Join-Path $BridgeDir "ipc"
$ReqDir = Join-Path $IpcDir "requests"
$ResDir = Join-Path $IpcDir "responses"
$ShotDir = Join-Path $IpcDir "screenshots"
$readyFile = Join-Path $IpcDir "guest_ready.json"
$logFile = Join-Path $IpcDir "guest_agent.log"

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

foreach ($d in @($IpcDir, $ReqDir, $ResDir, $ShotDir)) {
    if (-not [System.IO.Directory]::Exists($d)) {
        [System.IO.Directory]::CreateDirectory($d) | Out-Null
    }
}

function Log-Msg {
    param([string]$Text)
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
    $line = "[$stamp] $Text`r`n"
    [System.IO.File]::AppendAllText($logFile, $line, $utf8NoBom)
}

Log-Msg "Guest Agent starting PID=$PID in $BridgeDir"

# Write initial ready file
$readyJson = @{
    status = "ready"
    timestamp = (Get-Date).ToString("o")
    pid = $PID
    user = $env:USERNAME
    bridge_dir = $BridgeDir
} | ConvertTo-Json
[System.IO.File]::WriteAllText($readyFile, $readyJson, $utf8NoBom)

Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue
Add-Type -AssemblyName System.Drawing -ErrorAction SilentlyContinue

$Signature = @"
using System;
using System.Runtime.InteropServices;

public class Win32Input {
    [DllImport("user32.dll")]
    public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);

    [DllImport("user32.dll")]
    public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);

    [DllImport("user32.dll")]
    public static extern bool SetCursorPos(int X, int Y);

    public const uint MOUSEEVENTF_MOVE = 0x0001;
    public const uint MOUSEEVENTF_LEFTDOWN = 0x0002;
    public const uint MOUSEEVENTF_LEFTUP = 0x0004;
    public const uint MOUSEEVENTF_RIGHTDOWN = 0x0008;
    public const uint MOUSEEVENTF_RIGHTUP = 0x0010;
    public const uint MOUSEEVENTF_MIDDLEDOWN = 0x0020;
    public const uint MOUSEEVENTF_MIDDLEUP = 0x0040;
    public const uint MOUSEEVENTF_ABSOLUTE = 0x8000;

    public const uint KEYEVENTF_EXTENDEDKEY = 0x0001;
    public const uint KEYEVENTF_KEYUP = 0x0002;
    
    public const byte VK_LWIN = 0x5B;
    public const byte VK_RETURN = 0x0D;
    public const byte VK_ESCAPE = 0x1B;
    public const byte VK_TAB = 0x09;
    public const byte VK_CONTROL = 0x11;
    public const byte VK_SHIFT = 0x10;
    public const byte VK_MENU = 0x12;
}
"@

try {
    Add-Type -TypeDefinition $Signature -ErrorAction SilentlyContinue
} catch {}

function Capture-Screen {
    param([string]$OutPath)
    $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
    $graphics = [System.Drawing.Graphics]::FromImage($bmp)
    $graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
    $bmp.Save($OutPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $graphics.Dispose()
    $bmp.Dispose()
}

function Process-Request {
    param([string]$reqPath)
    
    if (-not [System.IO.File]::Exists($reqPath)) { return }
    
    $content = ""
    for ($r = 0; $r -lt 10; $r++) {
        try {
            $content = [System.IO.File]::ReadAllText($reqPath, [System.Text.Encoding]::UTF8)
            if ($content -and $content.Trim()) { break }
        } catch {
            Start-Sleep -Milliseconds 15
        }
    }
    
    if (-not $content -or -not $content.Trim()) { return }
    
    $req = $null
    try {
        $req = $content | ConvertFrom-Json
    } catch {
        return
    }
    
    $reqId = $req.id
    $action = $req.action
    
    Log-Msg "Processing Request ID=$reqId, Action=$action"
    $response = @{
        id = $reqId
        action = $action
        success = $true
        timestamp = (Get-Date).ToString("o")
    }
    
    switch ($action) {
        "ping" {
            $response["pong"] = $true
            $response["bridge_dir"] = $BridgeDir
            $response["screen"] = @{
                width = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width
                height = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height
            }
        }
        
        "mouse_click" {
            $x = [int]$req.x
            $y = [int]$req.y
            $btn = if ($req.button) { $req.button } else { "left" }
            $double = [bool]$req.double
            
            [Win32Input]::SetCursorPos($x, $y)
            Start-Sleep -Milliseconds 30
            
            if ($btn -eq "right") {
                [Win32Input]::mouse_event([Win32Input]::MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, [UIntPtr]::Zero)
                Start-Sleep -Milliseconds 30
                [Win32Input]::mouse_event([Win32Input]::MOUSEEVENTF_RIGHTUP, 0, 0, 0, [UIntPtr]::Zero)
            } elseif ($btn -eq "middle") {
                [Win32Input]::mouse_event([Win32Input]::MOUSEEVENTF_MIDDLEDOWN, 0, 0, 0, [UIntPtr]::Zero)
                Start-Sleep -Milliseconds 30
                [Win32Input]::mouse_event([Win32Input]::MOUSEEVENTF_MIDDLEUP, 0, 0, 0, [UIntPtr]::Zero)
            } else {
                [Win32Input]::mouse_event([Win32Input]::MOUSEEVENTF_LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
                Start-Sleep -Milliseconds 30
                [Win32Input]::mouse_event([Win32Input]::MOUSEEVENTF_LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
                
                if ($double) {
                    Start-Sleep -Milliseconds 60
                    [Win32Input]::mouse_event([Win32Input]::MOUSEEVENTF_LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
                    Start-Sleep -Milliseconds 30
                    [Win32Input]::mouse_event([Win32Input]::MOUSEEVENTF_LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
                }
            }
            $response["clicked"] = @{ x = $x; y = $y; button = $btn }
        }
        
        "mouse_move" {
            $x = [int]$req.x
            $y = [int]$req.y
            [Win32Input]::SetCursorPos($x, $y)
            $response["position"] = @{ x = $x; y = $y }
        }
        
        "mouse_drag" {
            $x1 = [int]$req.start_x
            $y1 = [int]$req.start_y
            $x2 = [int]$req.end_x
            $y2 = [int]$req.end_y
            
            [Win32Input]::SetCursorPos($x1, $y1)
            Start-Sleep -Milliseconds 40
            [Win32Input]::mouse_event([Win32Input]::MOUSEEVENTF_LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
            
            $steps = 10
            for ($i = 1; $i -le $steps; $i++) {
                $cx = [int]($x1 + ($x2 - $x1) * ($i / $steps))
                $cy = [int]($y1 + ($y2 - $y1) * ($i / $steps))
                [Win32Input]::SetCursorPos($cx, $cy)
                Start-Sleep -Milliseconds 15
            }
            
            [Win32Input]::mouse_event([Win32Input]::MOUSEEVENTF_LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
            $response["dragged"] = @{ from = @{ x = $x1; y = $y1 }; to = @{ x = $x2; y = $y2 } }
        }
        
        "key_type" {
            $text = [string]$req.text
            [System.Windows.Forms.SendKeys]::SendWait($text)
            if ($req.press_enter) {
                Start-Sleep -Milliseconds 50
                [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
            }
            $response["typed"] = $text
        }
        
        "hotkey" {
            $keys = [string]$req.keys
            $kLower = $keys.ToLower().Trim()
            
            if ($kLower -eq "win+r") {
                [Win32Input]::keybd_event([Win32Input]::VK_LWIN, 0, 0, [UIntPtr]::Zero)
                [Win32Input]::keybd_event(0x52, 0, 0, [UIntPtr]::Zero)
                Start-Sleep -Milliseconds 40
                [Win32Input]::keybd_event(0x52, 0, [Win32Input]::KEYEVENTF_KEYUP, [UIntPtr]::Zero)
                [Win32Input]::keybd_event([Win32Input]::VK_LWIN, 0, [Win32Input]::KEYEVENTF_KEYUP, [UIntPtr]::Zero)
            } elseif ($kLower -eq "enter" -or $kLower -eq "return") {
                [Win32Input]::keybd_event([Win32Input]::VK_RETURN, 0, 0, [UIntPtr]::Zero)
                Start-Sleep -Milliseconds 30
                [Win32Input]::keybd_event([Win32Input]::VK_RETURN, 0, [Win32Input]::KEYEVENTF_KEYUP, [UIntPtr]::Zero)
            } elseif ($kLower -eq "esc" -or $kLower -eq "escape") {
                [Win32Input]::keybd_event([Win32Input]::VK_ESCAPE, 0, 0, [UIntPtr]::Zero)
                Start-Sleep -Milliseconds 30
                [Win32Input]::keybd_event([Win32Input]::VK_ESCAPE, 0, [Win32Input]::KEYEVENTF_KEYUP, [UIntPtr]::Zero)
            } elseif ($kLower -eq "tab") {
                [Win32Input]::keybd_event([Win32Input]::VK_TAB, 0, 0, [UIntPtr]::Zero)
                Start-Sleep -Milliseconds 30
                [Win32Input]::keybd_event([Win32Input]::VK_TAB, 0, [Win32Input]::KEYEVENTF_KEYUP, [UIntPtr]::Zero)
            } elseif ($kLower.StartsWith("ctrl+")) {
                $char = $kLower.Substring(5).ToUpper()
                [Win32Input]::keybd_event([Win32Input]::VK_CONTROL, 0, 0, [UIntPtr]::Zero)
                [System.Windows.Forms.SendKeys]::SendWait("^($char)")
                [Win32Input]::keybd_event([Win32Input]::VK_CONTROL, 0, [Win32Input]::KEYEVENTF_KEYUP, [UIntPtr]::Zero)
            } elseif ($kLower.StartsWith("alt+")) {
                $char = $kLower.Substring(4).ToUpper()
                [Win32Input]::keybd_event([Win32Input]::VK_MENU, 0, 0, [UIntPtr]::Zero)
                [System.Windows.Forms.SendKeys]::SendWait("%($char)")
                [Win32Input]::keybd_event([Win32Input]::VK_MENU, 0, [Win32Input]::KEYEVENTF_KEYUP, [UIntPtr]::Zero)
            } else {
                [System.Windows.Forms.SendKeys]::SendWait($keys)
            }
            $response["hotkey_sent"] = $keys
        }
        
        "screenshot" {
            $shotName = "shot_${reqId}_$((Get-Date).Ticks).png"
            $shotPath = Join-Path $ShotDir $shotName
            Capture-Screen -OutPath $shotPath
            $response["screenshot_filename"] = $shotName
            $response["screenshot_path"] = "$ShotDir\$shotName"
        }
        
        "exec" {
            $cmd = [string]$req.command
            $timeoutSec = if ($req.timeout) { [int]$req.timeout } else { 60 }
            
            $bytes = [System.Text.Encoding]::Unicode.GetBytes($cmd)
            $encoded = [Convert]::ToBase64String($bytes)
            
            $pinfo = New-Object System.Diagnostics.ProcessStartInfo
            $pinfo.FileName = "powershell.exe"
            $pinfo.Arguments = "-NoProfile -ExecutionPolicy Bypass -EncodedCommand $encoded"
            $pinfo.RedirectStandardOutput = $true
            $pinfo.RedirectStandardError = $true
            $pinfo.UseShellExecute = $false
            $pinfo.CreateNoWindow = $true
            
            $proc = New-Object System.Diagnostics.Process
            $proc.StartInfo = $pinfo
            $proc.Start() | Out-Null
            
            $completed = $proc.WaitForExit($timeoutSec * 1000)
            if ($completed) {
                $stdout = $proc.StandardOutput.ReadToEnd()
                $stderr = $proc.StandardError.ReadToEnd()
                $response["exit_code"] = $proc.ExitCode
                $response["stdout"] = $stdout
                $response["stderr"] = $stderr
            } else {
                $proc.Kill()
                $response["success"] = $false
                $response["error"] = "Command timed out after $timeoutSec seconds"
            }
        }
        
        "launch" {
            $exe = [string]$req.path
            $args = [string]$req.args
            $proc = Start-Process -FilePath $exe -ArgumentList $args -PassThru
            $response["launched_pid"] = $proc.Id
            $response["process_name"] = $proc.ProcessName
        }
        
        default {
            $response["success"] = $false
            $response["error"] = "Unknown action: $action"
        }
    }
    
    $resPath = Join-Path $ResDir "res_${reqId}.json"
    $resJson = $response | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText($resPath, $resJson, $utf8NoBom)
    
    try { [System.IO.File]::Delete($reqPath) } catch {}
    Log-Msg "Completed Request ID=$reqId"
}

Log-Msg "Guest Agent entering real-time event loop in $BridgeDir..."

# Set up FileSystemWatcher for instant 0ms event notifications
$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = $ReqDir
$watcher.Filter = "*.json"
$watcher.IncludeSubdirectories = $false
$watcher.NotifyFilter = [System.IO.NotifyFilters]::FileName -bor [System.IO.NotifyFilters]::LastWrite -bor [System.IO.NotifyFilters]::Size
$watcher.EnableRaisingEvents = $true

Register-ObjectEvent $watcher "Created" -SourceIdentifier "ReqCreated" | Out-Null
Register-ObjectEvent $watcher "Changed" -SourceIdentifier "ReqChanged" | Out-Null

while ($true) {
    try {
        # Check event queue
        $events = Get-Event -SourceIdentifier "Req*" -ErrorAction SilentlyContinue
        if ($events) {
            foreach ($ev in $events) {
                $fPath = $ev.SourceEventArgs.FullPath
                if ($fPath) { Process-Request $fPath }
            }
            Remove-Event -SourceIdentifier "Req*" -ErrorAction SilentlyContinue
        }
        
        # Direct sweep
        if ([System.IO.Directory]::Exists($ReqDir)) {
            $files = [System.IO.Directory]::GetFiles($ReqDir, "*.json")
            foreach ($f in $files) { Process-Request $f }
        }
    } catch {
        Log-Msg "Error in event loop: $_"
    }
    
    Start-Sleep -Milliseconds 15
}
