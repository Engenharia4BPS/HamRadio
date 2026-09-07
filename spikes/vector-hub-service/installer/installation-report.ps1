param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector",
    [switch]$AsJson
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SetupScript = Join-Path $InstallerRoot "setup-vector.ps1"
$ReleasePath = Join-Path $InstallerRoot "release.json"
$DependencyLockPath = Join-Path $InstallerRoot "dependency-lock.json"
$VerifyCom0com = Join-Path $InstallerRoot "verify-com0com-lock.ps1"
$VectorIni = Join-Path $InstallRoot "config\vector.ini"
$PythonExe = Join-Path $InstallRoot "runtime\python.exe"
$HubLog = Join-Path $InstallRoot "logs\vector-hub.log"
$RebootMarker = Join-Path $InstallRoot "config\reboot-pending.flag"
$BackupRoot = Join-Path $InstallRoot "backups"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this script from an elevated PowerShell prompt."
    }
}

function Get-IniValue([string]$Path,[string]$Section,[string]$Key) {
    if (-not (Test-Path $Path -PathType Leaf)) { return $null }
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

function Get-CatPorts([string]$Path) {
    $value = Get-IniValue $Path "cat" "ports"
    if (-not $value) { return @() }
    return @($value.Split(',') | ForEach-Object { $_.Trim().ToUpperInvariant() } | Where-Object { $_ -match '^COM\d+$' })
}

function Get-KeyingEntries([string]$Path) {
    if (-not (Test-Path $Path -PathType Leaf)) { return @() }
    $entries = @()
    $inside = $false
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trim = $line.Trim()
        if ($trim -match '^\[(.+)\]$') {
            $inside = ($Matches[1] -ieq 'keying')
            continue
        }
        if (-not $inside -or $trim -notmatch '^(client\d+)\s*=\s*(.+)$') { continue }
        $key = [string]$Matches[1]
        $parts = @($Matches[2].Split(',') | ForEach-Object { $_.Trim() })
        if ($parts.Count -ge 4) {
            $entries += [pscustomobject]@{
                key = $key
                name = [string]$parts[0]
                port = ([string]$parts[1]).ToUpperInvariant()
                ptt_input = ([string]$parts[2]).ToUpperInvariant()
                cw_input = ([string]$parts[3]).ToUpperInvariant()
            }
        }
        elseif ($parts.Count -ge 3) {
            $entries += [pscustomobject]@{
                key = $key
                name = $key
                port = ([string]$parts[0]).ToUpperInvariant()
                ptt_input = ([string]$parts[1]).ToUpperInvariant()
                cw_input = ([string]$parts[2]).ToUpperInvariant()
            }
        }
    }
    return @($entries)
}

function Test-Rigctld([string]$HostName,[int]$PortNumber,[string]$Command) {
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
    finally {
        $client.Close()
    }
}

function Test-LockedRuntime($Lock) {
    if (-not (Test-Path $PythonExe -PathType Leaf)) { return $false }
    $pythonVersion = [string]$Lock.python.version
    $pyserialVersion = $null
    $pywin32Version = $null
    foreach ($pkg in @($Lock.python_packages)) {
        if ([string]$pkg.name -eq 'pyserial') { $pyserialVersion = [string]$pkg.version }
        if ([string]$pkg.name -eq 'pywin32') { $pywin32Version = [string]$pkg.version }
    }
    if (-not $pythonVersion -or -not $pyserialVersion -or -not $pywin32Version) { return $false }
    $oldNoUserSite = $env:PYTHONNOUSERSITE
    try {
        $env:PYTHONNOUSERSITE = "1"
        $code = "import platform,tkinter,serial,win32serviceutil,servicemanager; from importlib.metadata import version; raise SystemExit(0 if platform.python_version() == '$pythonVersion' and version('pyserial') == '$pyserialVersion' and version('pywin32') == '$pywin32Version' else 1)"
        & $PythonExe -c $code *> $null
        return ($LASTEXITCODE -eq 0)
    }
    finally {
        $env:PYTHONNOUSERSITE = $oldNoUserSite
    }
}

function Get-LatestBackup([string]$Root) {
    if (-not (Test-Path $Root -PathType Container)) { return $null }
    $item = Get-ChildItem -LiteralPath $Root -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($item) { return $item.FullName }
    return $null
}

Assert-Administrator

foreach ($path in @($SetupScript,$ReleasePath,$DependencyLockPath,$VerifyCom0com)) {
    if (-not (Test-Path $path -PathType Leaf)) { throw "Required D8F component is missing: $path" }
}

$release = Get-Content -LiteralPath $ReleasePath -Raw | ConvertFrom-Json
$releaseLabel = "$([string]$release.version) / $([string]$release.channel) / $([string]$release.phase)"
$lock = Get-Content -LiteralPath $DependencyLockPath -Raw | ConvertFrom-Json

$setupRaw = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $SetupScript -InstallRoot $InstallRoot -AsJson 2>&1
$setupExit = $LASTEXITCODE
if ($setupExit -ne 0) { throw "setup-vector.ps1 -AsJson failed with exit code $setupExit.`r`n$(($setupRaw | Out-String).Trim())" }
$setupState = (($setupRaw | Out-String).Trim()) | ConvertFrom-Json

$runtimeOk = Test-LockedRuntime $lock
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $VerifyCom0com -InstallRoot $InstallRoot *> $null
$com0comOk = ($LASTEXITCODE -eq 0)
$vectorIniOk = Test-Path $VectorIni -PathType Leaf

$svc = Get-Service -Name "GADXVectorHub" -ErrorAction SilentlyContinue
$serviceRunning = ($svc -and [string]$svc.Status -eq 'Running')
$serviceStartMode = "not installed"
try {
    $svcCim = Get-CimInstance Win32_Service -Filter "Name='GADXVectorHub'" -ErrorAction SilentlyContinue
    if ($svcCim) { $serviceStartMode = [string]$svcCim.StartMode }
} catch {}

$catPorts = if ($vectorIniOk) { Get-CatPorts $VectorIni } else { @() }
$keyingEntries = if ($vectorIniOk) { Get-KeyingEntries $VectorIni } else { @() }
$keyingPorts = @($keyingEntries | ForEach-Object { $_.port } | Where-Object { $_ } | Select-Object -Unique)

$radioPort = Get-IniValue $VectorIni "radio_keying" "port"
$radioBaud = Get-IniValue $VectorIni "radio_keying" "baud"
$pttLine = Get-IniValue $VectorIni "radio_keying" "ptt_line"
$cwLine = Get-IniValue $VectorIni "radio_keying" "cw_line"
$rigHost = Get-IniValue $VectorIni "rig" "host"
$rigPortText = Get-IniValue $VectorIni "rig" "port"
$rigPort = 0
[void][int]::TryParse([string]$rigPortText,[ref]$rigPort)

$rigFrequency = $null
$rigOk = $false
if ($rigHost -and $rigPort -gt 0) {
    try {
        $rigFrequency = Test-Rigctld $rigHost $rigPort "f"
        $rigOk = ($rigFrequency -match '^\d+(\.\d+)?$')
    } catch { $rigFrequency = $_.Exception.Message }
}

$pttResponse = $null
$pttSafe = $false
if ($pttLine -eq 'RIGCTLD' -and $rigHost -and $rigPort -gt 0) {
    try {
        $pttResponse = Test-Rigctld $rigHost $rigPort "t"
        $pttSafe = ($pttResponse -eq '0')
    } catch { $pttResponse = $_.Exception.Message }
} else {
    $pttResponse = "read-only probe not available for PTT=$pttLine"
}

$hubReady = $false
if (Test-Path $HubLog -PathType Leaf) {
    try {
        $tail = @(Get-Content -LiteralPath $HubLog -Tail 200 -ErrorAction SilentlyContinue)
        $hubReady = (($tail -join "`n") -match 'Vector Hub ready')
    } catch {}
}

$latestBackup = Get-LatestBackup $BackupRoot
$rebootPending = Test-Path $RebootMarker -PathType Leaf

$ready = (
    [string]$setupState.classification -eq 'CURRENT' -and
    [string]$setupState.recommended_mode -eq 'NONE' -and
    -not [bool]$setupState.payload_drift -and
    $runtimeOk -and
    $com0comOk -and
    $vectorIniOk -and
    $serviceRunning -and
    $hubReady -and
    $rigOk -and
    $pttSafe -and
    -not $rebootPending
)

$result = [ordered]@{
    schema_version = 1
    product = "GADX Vector"
    release = $releaseLabel
    install_root = $InstallRoot
    detected = [string]$setupState.classification
    recommended = [string]$setupState.recommended_mode
    payload_drift = [bool]$setupState.payload_drift
    runtime_ok = [bool]$runtimeOk
    com0com_ok = [bool]$com0comOk
    vector_ini_ok = [bool]$vectorIniOk
    service = [ordered]@{
        status = $(if ($svc) { [string]$svc.Status } else { "not installed" })
        start_mode = $serviceStartMode
    }
    cat_ports = @($catPorts)
    keying_ports = @($keyingPorts)
    keying_clients = @($keyingEntries)
    radio_keying = [ordered]@{
        port = $radioPort
        baud = $radioBaud
        ptt_line = $pttLine
        cw_line = $cwLine
    }
    rigctld = [ordered]@{
        host = $rigHost
        port = $rigPort
        frequency_response = $rigFrequency
        ok = [bool]$rigOk
    }
    hub_ready_log = [bool]$hubReady
    ptt_safe = [ordered]@{
        ok = [bool]$pttSafe
        response = $pttResponse
    }
    latest_backup = $latestBackup
    reboot_pending = [bool]$rebootPending
    installation_status = $(if ($ready) { "READY" } else { "ATTENTION REQUIRED" })
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 10
    exit $(if ($ready) { 0 } else { 3 })
}

Write-Host ""
Write-Host "GADX Vector - D8F commissioning report" -ForegroundColor Cyan
Write-Host "Product        : GADX Vector"
Write-Host "Release        : $releaseLabel"
Write-Host "Install root   : $InstallRoot"
Write-Host "Detected       : $([string]$setupState.classification)"
Write-Host "Recommended    : $([string]$setupState.recommended_mode)"
Write-Host "Payload drift  : $(if ([bool]$setupState.payload_drift) { 'YES' } else { 'NO' })"
Write-Host "Runtime        : $(if ($runtimeOk) { 'OK - dependency lock' } else { 'FAIL' })"
Write-Host "com0com        : $(if ($com0comOk) { "OK - locked $([string]$lock.com0com.version)" } else { 'FAIL' })"
Write-Host "vector.ini     : $(if ($vectorIniOk) { 'OK' } else { 'MISSING' })"
Write-Host "Service        : $(if ($svc) { [string]$svc.Status } else { 'not installed' }) / $serviceStartMode"
Write-Host "CAT ports      : $(if ($catPorts.Count) { $catPorts -join ', ' } else { 'none' })"
Write-Host "Keying ports   : $(if ($keyingPorts.Count) { $keyingPorts -join ', ' } else { 'none' })"
Write-Host "Radio keying   : $radioPort @ $radioBaud PTT=$pttLine CW=$cwLine"
Write-Host "rigctld        : $rigHost`:$rigPort $(if ($rigOk) { "OK freq=$rigFrequency" } else { "FAIL response=$rigFrequency" })"
Write-Host "Hub ready log  : $(if ($hubReady) { 'OK' } else { 'FAIL' })"
Write-Host "PTT safe state : $(if ($pttSafe) { "OK - t -> $pttResponse" } else { "FAIL - $pttResponse" })"
Write-Host "Latest backup  : $(if ($latestBackup) { $latestBackup } else { 'none' })"
Write-Host "Reboot pending : $rebootPending"
Write-Host ""
if ($ready) {
    Write-Host "INSTALLATION STATUS : READY" -ForegroundColor Green
    Write-Host "D8F_COMMISSIONING_REPORT_OK" -ForegroundColor Green
    exit 0
}

Write-Host "INSTALLATION STATUS : ATTENTION REQUIRED" -ForegroundColor Red
Write-Host "D8F_COMMISSIONING_REPORT_ATTENTION" -ForegroundColor Red
exit 3
