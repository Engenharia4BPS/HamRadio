param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector",
    [string]$RadioKeyingPort = "COM8",
    [int]$RadioKeyingBaud = 9600,
    [ValidateSet("RIGCTLD","DTR","RTS","NONE")]
    [string]$PttLine = "RIGCTLD",
    [ValidateSet("DTR","RTS","NONE")]
    [string]$CwLine = "RTS",
    [string]$RigHost = "127.0.0.1",
    [int]$RigPort = 4532,
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $InstallRoot "runtime\python.exe"
$VectorIni = Join-Path $InstallRoot "config\vector.ini"
$HubLog = Join-Path $InstallRoot "logs\vector-hub.log"
$RebootMarker = Join-Path $InstallRoot "config\reboot-pending.flag"
$MigrateService = Join-Path $InstallerRoot "migrate-service.ps1"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this script from an elevated PowerShell prompt."
    }
}

function Find-Com0comSetup {
    foreach ($candidate in @(
        "C:\Ham\com0com\setupc.exe",
        "$env:ProgramFiles\com0com\setupc.exe",
        "${env:ProgramFiles(x86)}\com0com\setupc.exe"
    )) {
        if ($candidate -and (Test-Path $candidate -PathType Leaf)) { return (Resolve-Path $candidate).Path }
    }
    return $null
}

function Invoke-Com0comList([string]$SetupExe) {
    if (-not $SetupExe) { return "" }
    $cwd = Split-Path -Parent $SetupExe
    Push-Location $cwd
    try {
        $lines = @(& $SetupExe list 2>&1)
        return (($lines | ForEach-Object { [string]$_ }) -join "`n")
    }
    finally { Pop-Location }
}

function Get-IniValue([string]$Path,[string]$Section,[string]$Key) {
    $inside = $false
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trim = $line.Trim()
        if ($trim -match '^\[(.+)\]$') {
            $inside = ($Matches[1] -ieq $Section)
            continue
        }
        if ($inside -and $trim -match ('^' + [regex]::Escape($Key) + '\s*=\s*(.*)$')) {
            return $Matches[1].Trim()
        }
    }
    return $null
}

function Set-IniValue([string]$Path,[string]$Section,[string]$Key,[string]$Value) {
    $lines = New-Object System.Collections.Generic.List[string]
    foreach ($line in Get-Content -LiteralPath $Path) { [void]$lines.Add([string]$line) }

    $sectionStart = -1
    $nextSection = $lines.Count
    for ($i=0; $i -lt $lines.Count; $i++) {
        if ($lines[$i].Trim() -match '^\[(.+)\]$') {
            if ($sectionStart -ge 0) { $nextSection = $i; break }
            if ($Matches[1] -ieq $Section) { $sectionStart = $i }
        }
    }

    if ($sectionStart -lt 0) {
        if ($lines.Count -gt 0 -and $lines[$lines.Count-1].Trim() -ne "") { [void]$lines.Add("") }
        [void]$lines.Add("[$Section]")
        [void]$lines.Add("$Key = $Value")
    } else {
        $found = $false
        for ($i=$sectionStart+1; $i -lt $nextSection; $i++) {
            if ($lines[$i].Trim() -match ('^' + [regex]::Escape($Key) + '\s*=')) {
                $lines[$i] = "$Key = $Value"
                $found = $true
                break
            }
        }
        if (-not $found) { $lines.Insert($nextSection,"$Key = $Value") }
    }

    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllLines($Path,$lines,$utf8)
}

function Get-RequiredVectorPorts([string]$Path) {
    $ports = New-Object System.Collections.Generic.List[string]
    $cat = Get-IniValue $Path "cat" "ports"
    if ($cat) {
        foreach ($p in $cat.Split(',')) {
            $v = $p.Trim().ToUpperInvariant()
            if ($v -match '^COM\d+$' -and -not $ports.Contains($v)) { [void]$ports.Add($v) }
        }
    }
    $inside = $false
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trim = $line.Trim()
        if ($trim -match '^\[(.+)\]$') { $inside = ($Matches[1] -ieq 'keying'); continue }
        if ($inside -and $trim -match '^client\d+\s*=\s*(.+)$') {
            $parts = @($Matches[1].Split(',') | ForEach-Object { $_.Trim() })
            $p = $null
            if ($parts.Count -ge 4) { $p = $parts[1] }
            elseif ($parts.Count -ge 3) { $p = $parts[0] }
            if ($p) {
                $v = $p.ToUpperInvariant()
                if ($v -match '^COM\d+$' -and -not $ports.Contains($v)) { [void]$ports.Add($v) }
            }
        }
    }
    return @($ports)
}

function Test-Rigctld([string]$HostName,[int]$PortNumber,[string]$Command = "f") {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect($HostName,$PortNumber,$null,$null)
        if (-not $iar.AsyncWaitHandle.WaitOne(2000,$false)) { throw "connection timeout" }
        $client.EndConnect($iar)
        $stream = $client.GetStream()
        $stream.ReadTimeout = 2000
        $stream.WriteTimeout = 2000
        $writer = New-Object System.IO.StreamWriter($stream,[System.Text.Encoding]::ASCII,1024,$true)
        $writer.NewLine = "`n"
        $writer.AutoFlush = $true
        $reader = New-Object System.IO.StreamReader($stream,[System.Text.Encoding]::ASCII,$false,1024,$true)
        $writer.WriteLine($Command)
        $line = $reader.ReadLine()
        if ($null -eq $line) { throw "rigctld closed connection" }
        return $line.Trim()
    }
    finally { $client.Close() }
}

function Runtime-OK {
    if (-not (Test-Path $PythonExe -PathType Leaf)) { return $false }
    & $PythonExe -c "import tkinter, serial, win32serviceutil, servicemanager" *> $null
    return ($LASTEXITCODE -eq 0)
}

function Port-Exists([string]$PortName) {
    try { return ([System.IO.Ports.SerialPort]::GetPortNames() -contains $PortName.ToUpperInvariant()) }
    catch { return $false }
}

function Show-Check([string]$Label,[bool]$Ok,[string]$Detail = "") {
    $status = if ($Ok) { "OK" } else { "FAIL" }
    $color = if ($Ok) { "Green" } else { "Red" }
    $suffix = if ($Detail) { " - $Detail" } else { "" }
    Write-Host (("{0,-22}: {1}{2}" -f $Label,$status,$suffix)) -ForegroundColor $color
}

Assert-Administrator

if (-not (Test-Path $VectorIni -PathType Leaf)) { throw "vector.ini is missing: $VectorIni" }
if (-not (Test-Path $MigrateService -PathType Leaf)) { throw "migrate-service.ps1 is missing: $MigrateService" }

$com0com = Find-Com0comSetup
$runtimeOk = Runtime-OK
$com0comOk = [bool]$com0com
$requiredPorts = Get-RequiredVectorPorts $VectorIni
$listText = if ($com0com) { Invoke-Com0comList $com0com } else { "" }
$missingPorts = @()
foreach ($p in $requiredPorts) {
    if ($listText -notmatch ('(?i)\b' + [regex]::Escape($p) + '\b')) { $missingPorts += $p }
}
$virtualPortsOk = ($requiredPorts.Count -gt 0 -and $missingPorts.Count -eq 0)
$radioPortOk = Port-Exists $RadioKeyingPort

$rigResponse = $null
$rigOk = $false
try {
    $rigResponse = Test-Rigctld $RigHost $RigPort "f"
    $rigOk = ($rigResponse -match '^\d+(\.\d+)?$')
} catch { $rigResponse = $_.Exception.Message }

$currentRadioPort = Get-IniValue $VectorIni "radio_keying" "port"
$currentRadioBaud = Get-IniValue $VectorIni "radio_keying" "baud"
$currentPtt = Get-IniValue $VectorIni "radio_keying" "ptt_line"
$currentCw = Get-IniValue $VectorIni "radio_keying" "cw_line"
$currentRigHost = Get-IniValue $VectorIni "rig" "host"
$currentRigPort = Get-IniValue $VectorIni "rig" "port"

Write-Host ""
Write-Host "GADX Vector - Phase D6 commissioning/post-install" -ForegroundColor Cyan
Write-Host "Install root : $InstallRoot"
Write-Host ""
Show-Check "Private runtime" $runtimeOk $PythonExe
Show-Check "com0com" $com0comOk $(if ($com0com) { $com0com } else { "setupc.exe not found" })
Show-Check "Vector COM pairs" $virtualPortsOk $(if ($virtualPortsOk) { ($requiredPorts -join ', ') } else { "missing: " + ($missingPorts -join ', ') })
Show-Check "CW physical port" $radioPortOk "$RadioKeyingPort @ $RadioKeyingBaud"
Show-Check "rigctld" $rigOk "$RigHost`:$RigPort response=$rigResponse"
Write-Host ""
Write-Host "Station configuration requested:"
Write-Host "  radio_keying : $RadioKeyingPort @ $RadioKeyingBaud, PTT=$PttLine, CW=$CwLine"
Write-Host "  rigctld      : $RigHost`:$RigPort"
Write-Host ""
Write-Host "Current vector.ini:"
Write-Host "  radio_keying : $currentRadioPort @ $currentRadioBaud, PTT=$currentPtt, CW=$currentCw"
Write-Host "  rigctld      : $currentRigHost`:$currentRigPort"
Write-Host ""

$preflightOk = $runtimeOk -and $com0comOk -and $virtualPortsOk -and $radioPortOk -and $rigOk

if (-not $Apply) {
    Write-Host "PREVIEW ONLY - no changes were made." -ForegroundColor Yellow
    if (-not $preflightOk) {
        Write-Host "D6 preflight is NOT ready for -Apply. Fix the FAIL items first." -ForegroundColor Red
        exit 2
    }
    Write-Host "D6 preflight passed." -ForegroundColor Green
    Write-Host "Re-run with -Apply to update station-specific radio settings, install/start GADXVectorHub and perform the final post-check."
    exit 0
}

if (-not $preflightOk) { throw "D6 preflight failed. No service transaction was started." }

Write-Host "Applying station-specific [radio_keying] and [rig] values..."
Set-IniValue $VectorIni "radio_keying" "port" $RadioKeyingPort
Set-IniValue $VectorIni "radio_keying" "baud" ([string]$RadioKeyingBaud)
Set-IniValue $VectorIni "radio_keying" "ptt_line" $PttLine
Set-IniValue $VectorIni "radio_keying" "cw_line" $CwLine
Set-IniValue $VectorIni "rig" "host" $RigHost
Set-IniValue $VectorIni "rig" "port" ([string]$RigPort)

Write-Host "Installing/starting GADXVectorHub transactionally..."
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $MigrateService -InstallRoot $InstallRoot -Apply
if ($LASTEXITCODE -ne 0) { throw "Service transaction failed with exit code $LASTEXITCODE." }

Start-Sleep -Seconds 2
$svc = Get-Service -Name "GADXVectorHub" -ErrorAction SilentlyContinue
$serviceOk = ($svc -and [string]$svc.Status -eq "Running")

$pttResponse = $null
$pttSafe = $false
try {
    $pttResponse = Test-Rigctld $RigHost $RigPort "t"
    $pttSafe = ($pttResponse -eq "0")
} catch { $pttResponse = $_.Exception.Message }

$logReady = $false
$logPhysical = $false
if (Test-Path $HubLog -PathType Leaf) {
    $tail = @(Get-Content -LiteralPath $HubLog -Tail 120 -ErrorAction SilentlyContinue)
    $joined = $tail -join "`n"
    $logReady = ($joined -match 'Vector Hub ready')
    $expected = [regex]::Escape("Physical keying: $RadioKeyingPort @ $RadioKeyingBaud PTT=$PttLine CW=$CwLine")
    $logPhysical = ($joined -match $expected)
}

Write-Host ""
Write-Host "Final post-install check:" -ForegroundColor Cyan
Show-Check "GADXVectorHub" $serviceOk $(if ($svc) { [string]$svc.Status } else { "not installed" })
Show-Check "Hub ready log" $logReady $HubLog
Show-Check "Physical keying log" $logPhysical "$RadioKeyingPort PTT=$PttLine CW=$CwLine"
Show-Check "PTT safe state" $pttSafe "rigctld t -> $pttResponse"

$finalOk = $serviceOk -and $logReady -and $logPhysical -and $pttSafe
if ($finalOk) {
    if (Test-Path $RebootMarker -PathType Leaf) { Remove-Item -LiteralPath $RebootMarker -Force }
    Write-Host ""
    Write-Host "INSTALLATION STATUS : READY" -ForegroundColor Green
    Write-Host "Reboot pending       : False"
    exit 0
}

Write-Host ""
Write-Host "INSTALLATION STATUS : ATTENTION REQUIRED" -ForegroundColor Red
Write-Host "The service was not declared READY because one or more final checks failed."
exit 3
