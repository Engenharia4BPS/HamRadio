param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PayloadRoot = Join-Path $InstallerRoot "payload"
$Python = Join-Path $InstallRoot "runtime\python.exe"
$Config = Join-Path $InstallRoot "config\vector.ini"
$HubLog = Join-Path $InstallRoot "logs\vector-hub.log"
$ServiceName = "GADXVectorHub"
$LegacyServiceName = "GADXVectorBridge"
$RebootMarker = Join-Path $InstallRoot "config\reboot-pending.flag"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this script from an elevated PowerShell prompt."
    }
}

function Wait-ServiceState([string]$Name,[string]$State,[int]$Seconds=12) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        $svc = Get-Service -Name $Name -ErrorAction SilentlyContinue
        if ($svc -and [string]$svc.Status -eq $State) { return $true }
        Start-Sleep -Milliseconds 300
    } while ((Get-Date) -lt $deadline)
    return $false
}

function Assert-Payload {
    foreach ($relative in @(
        "app\vector_hub.py",
        "app\ts2000.py",
        "service\vector_service.py",
        "tools\port_manager.py"
    )) {
        $path = Join-Path $PayloadRoot $relative
        if (-not (Test-Path $path -PathType Leaf)) {
            throw "Installer payload is incomplete. Missing: $path"
        }
    }
}

function Copy-RelativeFile([string]$SourceRoot,[string]$DestinationRoot,[string]$RelativePath) {
    $source = Join-Path $SourceRoot $RelativePath
    if (-not (Test-Path $source -PathType Leaf)) { return }
    $destination = Join-Path $DestinationRoot $RelativePath
    $parent = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Force
}

function Deploy-Payload {
    foreach ($relative in @(
        "app\vector_hub.py",
        "app\ts2000.py",
        "service\vector_service.py",
        "tools\port_manager.py"
    )) {
        $source = Join-Path $PayloadRoot $relative
        $destination = Join-Path $InstallRoot $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination -Force
    }
}

function Remove-CurrentService([string]$ServiceScript) {
    $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if (-not $svc) { return }
    try { Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue } catch {}
    Start-Sleep -Milliseconds 500
    & $Python $ServiceScript remove 2>$null | Out-Null
    Start-Sleep -Milliseconds 700
}

function Validate-VectorConfig {
    $appDir = Join-Path $InstallRoot "app"
    & $Python -c "import sys; sys.path.insert(0, sys.argv[1]); import vector_hub; vector_hub.load_config(sys.argv[2]); print('CONFIG_OK')" $appDir $Config
    if ($LASTEXITCODE -ne 0) { throw "Current vector.ini is not compatible with the new Vector Hub payload." }
}

function Find-Com0comSetup {
    foreach ($candidate in @(
        "C:\Ham\com0com\setupc.exe",
        "$env:ProgramFiles\com0com\setupc.exe",
        "${env:ProgramFiles(x86)}\com0com\setupc.exe"
    )) {
        if ($candidate -and (Test-Path $candidate -PathType Leaf)) {
            return (Resolve-Path $candidate).Path
        }
    }
    return $null
}

function Invoke-Com0com([string]$SetupExe,[string[]]$Arguments) {
    $cwd = Split-Path -Parent $SetupExe
    Push-Location $cwd
    try {
        return @(& $SetupExe @Arguments 2>&1)
    }
    finally {
        Pop-Location
    }
}

function Get-Com0comSnapshot([string]$SetupExe) {
    if (-not $SetupExe) { return "" }
    $output = Invoke-Com0com $SetupExe @('list')
    return (($output | ForEach-Object { [string]$_ }) -join "`n")
}

function Get-ConfiguredVectorPorts {
    if (-not (Test-Path $Config -PathType Leaf)) { return @() }

    $section = ""
    $ports = @()

    foreach ($line in Get-Content -LiteralPath $Config) {
        $trim = ([string]$line).Trim()

        if ($trim -match '^\[([^\]]+)\]$') {
            $section = $Matches[1].ToLowerInvariant()
            continue
        }

        if (-not $trim -or $trim.StartsWith(';') -or $trim.StartsWith('#')) {
            continue
        }

        if ($section -eq 'cat' -and $trim -match '^ports\s*=\s*(.+)$') {
            foreach ($item in $Matches[1].Split(',')) {
                $port = $item.Trim().ToUpperInvariant()
                if ($port -match '^COM\d+$') {
                    $ports += $port
                }
            }
        }
        elseif ($section -eq 'keying' -and $trim -match '^client\d+\s*=\s*(.+)$') {
            $parts = @($Matches[1].Split(',') | ForEach-Object { $_.Trim() })
            if ($parts.Count -ge 4) {
                $port = $parts[1].ToUpperInvariant()
            }
            elseif ($parts.Count -ge 3) {
                $port = $parts[0].ToUpperInvariant()
            }
            else {
                $port = ""
            }

            if ($port -match '^COM\d+$') {
                $ports += $port
            }
        }
    }

    return @($ports | Select-Object -Unique)
}

function Get-VirtualComPreflight {
    $configured = @(Get-ConfiguredVectorPorts)
    $setupc = Find-Com0comSetup
    $snapshot = if ($setupc) { Get-Com0comSnapshot $setupc } else { "" }

    $driverCode52 = @()
    try {
        $driverCode52 = @(
            Get-CimInstance Win32_PnPEntity -ErrorAction Stop |
            Where-Object {
                $_.PNPDeviceID -like 'ROOT\COM0COM*' -and
                [int]$_.ConfigManagerErrorCode -eq 52
            }
        )
    }
    catch {}

    $missingPairs = @()
    foreach ($port in $configured) {
        if ($snapshot -notmatch ('(?i)\b' + [regex]::Escape($port) + '\b')) {
            $missingPairs += $port
        }
    }

    $windowsPorts = @()
    try {
        $windowsPorts = @(
            [System.IO.Ports.SerialPort]::GetPortNames() |
            ForEach-Object { $_.ToUpperInvariant() }
        )
    }
    catch {}

    $notEnumerated = @()
    foreach ($port in $configured) {
        if ($windowsPorts -notcontains $port) {
            $notEnumerated += $port
        }
    }

    return [pscustomobject]@{
        Setupc = $setupc
        Configured = $configured
        MissingPairs = @($missingPairs)
        NotEnumerated = @($notEnumerated)
        RebootMarker = (Test-Path $RebootMarker -PathType Leaf)
        DriverCode52 = @($driverCode52)
    }
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
    finally { $client.Close() }
}

function Get-IniValue([string]$Path,[string]$Section,[string]$Key) {
    $inside = $false
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trim = $line.Trim()
        if ($trim -match '^\[(.+)\]$') { $inside = ($Matches[1] -ieq $Section); continue }
        if ($inside -and $trim -match ('^' + [regex]::Escape($Key) + '\s*=\s*(.*)$')) { return $Matches[1].Trim() }
    }
    return $null
}

function Write-BuildManifest([string]$BackupRoot) {
    $manifest = Join-Path $InstallRoot "config\installed-build.txt"
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("installed_utc = $([DateTime]::UtcNow.ToString('o'))") | Out-Null
    $lines.Add("installer_phase = D7") | Out-Null

    $releasePath = Join-Path $InstallerRoot "release.json"
    if (Test-Path $releasePath -PathType Leaf) {
        try {
            $release = Get-Content -LiteralPath $releasePath -Raw | ConvertFrom-Json
            if ($release.product) { $lines.Add("product = $([string]$release.product)") | Out-Null }
            if ($release.version) { $lines.Add("product_version = $([string]$release.version)") | Out-Null }
            if ($release.phase) { $lines.Add("release_phase = $([string]$release.phase)") | Out-Null }
            if ($release.channel) { $lines.Add("release_channel = $([string]$release.channel)") | Out-Null }
            if ($release.baseline) { $lines.Add("release_baseline = $([string]$release.baseline)") | Out-Null }
        }
        catch {
            $lines.Add("release_metadata = invalid") | Out-Null
        }
    }
    else {
        $lines.Add("release_metadata = missing") | Out-Null
    }

    $lines.Add("backup = $BackupRoot") | Out-Null
    foreach ($relative in @("app\vector_hub.py","app\ts2000.py","service\vector_service.py","tools\port_manager.py")) {
        $path = Join-Path $InstallRoot $relative
        if (Test-Path $path -PathType Leaf) {
            $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant()
            $lines.Add("$relative = $hash") | Out-Null
        }
    }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllLines($manifest,$lines,$utf8)
}

Assert-Administrator
Assert-Payload

$current = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
$legacy = Get-Service -Name $LegacyServiceName -ErrorAction SilentlyContinue
$runtimeReady = Test-Path $Python -PathType Leaf
$configReady = Test-Path $Config -PathType Leaf
$virtualPreflight = if ($configReady) { Get-VirtualComPreflight } else { $null }

Write-Host ""
Write-Host "GADX Vector - Phase D7 current installation repair/update" -ForegroundColor Cyan
Write-Host "Install root : $InstallRoot"
Write-Host "Python       : $(if ($runtimeReady) { $Python } else { 'MISSING - setup-vector will install it before Apply' })"
Write-Host "Config       : $(if ($configReady) { $Config } else { 'MISSING' })"
Write-Host "Current svc  : $(if ($current) { [string]$current.Status } else { 'not installed' })"
Write-Host "Legacy svc   : $(if ($legacy) { [string]$legacy.Status } else { 'not installed' })"
Write-Host ""

if (-not $Apply) {
    Write-Host "PREVIEW ONLY - no application files, configuration or services were changed." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Planned D7 transaction:"
    Write-Host "  1. Ensure the private Python runtime is healthy."
    Write-Host "  2. Back up current app/service/tools, vector.ini and the current Hub log."
    Write-Host "  3. Stop GADXVectorHub and keep the radio in fail-safe state."
    Write-Host "  4. Deploy the current app/service/tools payload; preserve vector.ini and all com0com pairs."
    Write-Host "  5. Validate the preserved vector.ini against the new Hub before starting the service."
    Write-Host "  6. Reinstall GADXVectorHub as delayed-auto with recovery actions."
    Write-Host "  7. Start it and require a fresh 'Vector Hub ready' log plus PTT=OFF through rigctld."
    Write-Host "  8. Remove stale GADXVectorBridge only after the new Hub is healthy."
    Write-Host "  9. If anything fails, preserve the failed Hub log, restore the backup and leave GADXVectorHub stopped/disabled."
    Write-Host ""
    Write-Host "vector.ini and virtual COM pairs are never rewritten by D7." -ForegroundColor Green
    if (-not $runtimeReady) { Write-Host "Preview note: runtime is currently missing; setup-vector will create it before D7 Apply." -ForegroundColor Yellow }
    if (-not $configReady) { Write-Host "Preview warning: vector.ini is missing; D7 Apply cannot proceed until it exists." -ForegroundColor Red }

    if ($virtualPreflight) {
        Write-Host ""
        Write-Host "Virtual COM preflight:"
        Write-Host "  Configured Vector ports: $($virtualPreflight.Configured -join ', ')"

        if ($virtualPreflight.MissingPairs.Count -gt 0) {
            Write-Host "  BLOCKED - missing from com0com: $($virtualPreflight.MissingPairs -join ', ')" -ForegroundColor Red
            Write-Host "  Open Port Manager, create/apply the required pairs, then run Preview again." -ForegroundColor Yellow
            exit 4
        }

        if ($virtualPreflight.DriverCode52.Count -gt 0) {
            Write-Host "  BLOCKED - com0com driver is present but Windows rejected its kernel signature (Code 52)." -ForegroundColor Red
            Write-Host "  The locked 2017 com0com package is not usable with the current Windows driver-signing policy on this machine." -ForegroundColor Yellow
            Write-Host "  For this disposable VM test, Secure Boot can be disabled in the VM firmware; production requires a modern properly signed virtual-COM driver." -ForegroundColor Yellow
            exit 6
        }

        if ($virtualPreflight.NotEnumerated.Count -gt 0) {
            Write-Host "  BLOCKED - configured ports are not yet enumerated by Windows: $($virtualPreflight.NotEnumerated -join ', ')" -ForegroundColor Red
            Write-Host "  Reboot Windows after com0com changes, then run Preview again." -ForegroundColor Yellow
            exit 5
        }

        Write-Host "  com0com pairs / Windows enumeration: OK" -ForegroundColor Green
    }

    exit 0
}

if (-not $runtimeReady) { throw "Private runtime is missing: $Python" }
if (-not $configReady) { throw "Current vector.ini is missing: $Config" }

if ($virtualPreflight) {
    if ($virtualPreflight.MissingPairs.Count -gt 0) {
        throw "Required Vector COM pairs are missing from com0com: $($virtualPreflight.MissingPairs -join ', '). Open Port Manager and apply the required pairs before D7."
    }

    if ($virtualPreflight.DriverCode52.Count -gt 0) {
        throw "com0com kernel driver was rejected by Windows with Code 52 (CM_PROB_UNSIGNED_DRIVER). The current locked 2017 com0com baseline is not compatible with this machine's driver-signing policy."
    }

    if ($virtualPreflight.NotEnumerated.Count -gt 0) {
        throw "Required Vector COM ports are not enumerated by Windows: $($virtualPreflight.NotEnumerated -join ', '). Reboot Windows after com0com changes before D7."
    }

    if ($virtualPreflight.RebootMarker) {
        Remove-Item -LiteralPath $RebootMarker -Force -ErrorAction SilentlyContinue
        Write-Host "Virtual COM reboot marker cleared: all configured Vector ports are enumerated." -ForegroundColor Green
    }
}

& $Python -c "import tkinter, serial, win32serviceutil, servicemanager" *> $null
if ($LASTEXITCODE -ne 0) { throw "Private runtime validation failed." }

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupRoot = Join-Path $InstallRoot "backups\repair-$timestamp"
New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null

$relativeFiles = @(
    "app\vector_hub.py",
    "app\ts2000.py",
    "service\vector_service.py",
    "tools\port_manager.py",
    "config\vector.ini",
    "logs\vector-hub.log"
)
foreach ($relative in $relativeFiles) { Copy-RelativeFile $InstallRoot $BackupRoot $relative }

$configHashBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash
$serviceState = @(
    "current_exists=$([bool]$current)",
    "current_status=$(if ($current) { [string]$current.Status } else { 'not-installed' })",
    "legacy_exists=$([bool]$legacy)",
    "legacy_status=$(if ($legacy) { [string]$legacy.Status } else { 'not-installed' })"
)
[System.IO.File]::WriteAllLines((Join-Path $BackupRoot "service-state.txt"),$serviceState,(New-Object System.Text.UTF8Encoding($false)))

$ServiceScript = Join-Path $InstallRoot "service\vector_service.py"

try {
    if ($current -and [string]$current.Status -ne "Stopped") {
        Write-Host "Stopping GADXVectorHub..."
        Stop-Service -Name $ServiceName -Force
        if (-not (Wait-ServiceState $ServiceName "Stopped" 12)) { throw "GADXVectorHub did not stop within 12 seconds." }
    }

    Write-Host "Deploying current D7 payload..."
    Deploy-Payload

    $configHashAfter = (Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash
    if ($configHashBefore -ne $configHashAfter) { throw "Safety check failed: vector.ini changed during payload deployment." }

    Write-Host "Validating preserved vector.ini against the new Hub..."
    Validate-VectorConfig

    if (Test-Path $HubLog -PathType Leaf) { Clear-Content -LiteralPath $HubLog -ErrorAction SilentlyContinue }

    Write-Host "Reinstalling GADXVectorHub on the private runtime..."
    Remove-CurrentService $ServiceScript
    & $Python $ServiceScript install
    if ($LASTEXITCODE -ne 0) { throw "vector_service.py install failed with exit code $LASTEXITCODE." }

    & sc.exe config $ServiceName start= delayed-auto | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not configure delayed-auto startup." }
    & sc.exe failure $ServiceName reset= 86400 actions= restart/5000/restart/5000/restart/5000 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not configure service recovery." }
    & sc.exe failureflag $ServiceName 1 | Out-Null

    Write-Host "Starting GADXVectorHub..."
    Start-Service -Name $ServiceName
    if (-not (Wait-ServiceState $ServiceName "Running" 12)) { throw "GADXVectorHub did not reach Running state." }
    Start-Sleep -Seconds 5
    $check = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if (-not $check -or [string]$check.Status -ne "Running") { throw "GADXVectorHub did not remain Running during D7 health validation." }

    $tail = if (Test-Path $HubLog -PathType Leaf) { @(Get-Content -LiteralPath $HubLog -Tail 160 -ErrorAction SilentlyContinue) } else { @() }
    $joined = $tail -join "`n"
    if ($joined -notmatch 'Vector Hub ready') { throw "Fresh Hub log does not contain 'Vector Hub ready'." }

    $rigHost = Get-IniValue $Config "rig" "host"
    if (-not $rigHost) { $rigHost = "127.0.0.1" }
    $rigPortRaw = Get-IniValue $Config "rig" "port"
    $rigPort = if ($rigPortRaw) { [int]$rigPortRaw } else { 4532 }
    $ptt = Test-Rigctld $rigHost $rigPort "t"
    if ($ptt -ne "0") { throw "PTT safety validation failed: rigctld t returned '$ptt' instead of 0." }

    if ($legacy) {
        Write-Host "New Hub is healthy. Removing stale GADXVectorBridge..."
        try { Stop-Service -Name $LegacyServiceName -Force -ErrorAction SilentlyContinue } catch {}
        & sc.exe delete $LegacyServiceName | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "New Hub is healthy, but stale GADXVectorBridge could not be deleted." }
    }

    Write-BuildManifest $BackupRoot

    Write-Host ""
    Write-Host "D7 REPAIR/UPDATE completed successfully." -ForegroundColor Green
    Write-Host "Backup             : $BackupRoot"
    Write-Host "vector.ini         : preserved (SHA256 unchanged)"
    Write-Host "com0com pairs      : unchanged"
    Write-Host "GADXVectorHub      : Running / delayed-auto"
    Write-Host "PTT safe state     : OFF"
    Write-Host "INSTALLATION STATUS: READY"
    exit 0
}
catch {
    $failure = $_.Exception.Message
    Write-Warning "D7 repair failed: $failure"
    Write-Warning "Preserving failed Hub evidence, restoring backed-up application files and leaving the Hub stopped/disabled for safety..."

    try { Remove-CurrentService $ServiceScript } catch {}

    if (Test-Path $HubLog -PathType Leaf) {
        $failedLog = Join-Path $BackupRoot "logs\failed-vector-hub.log"
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $failedLog) | Out-Null
        Copy-Item -LiteralPath $HubLog -Destination $failedLog -Force -ErrorAction SilentlyContinue
        if (Test-Path $failedLog -PathType Leaf) {
            Write-Warning "Failed Hub log preserved at: $failedLog"
            $failedTail = @(Get-Content -LiteralPath $failedLog -Tail 40 -ErrorAction SilentlyContinue)
            if ($failedTail.Count -gt 0) {
                Write-Host "----- failed Vector Hub log tail -----" -ForegroundColor Yellow
                $failedTail | ForEach-Object { Write-Host $_ }
                Write-Host "--------------------------------------" -ForegroundColor Yellow
            }
        }
    }

    foreach ($relative in $relativeFiles) {
        $source = Join-Path $BackupRoot $relative
        if (Test-Path $source -PathType Leaf) {
            $destination = Join-Path $InstallRoot $relative
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
            Copy-Item -LiteralPath $source -Destination $destination -Force
        }
    }

    $restoredServiceScript = Join-Path $InstallRoot "service\vector_service.py"
    if (Test-Path $restoredServiceScript -PathType Leaf) {
        try {
            & $Python $restoredServiceScript install 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                & sc.exe config $ServiceName start= disabled | Out-Null
                try { Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue } catch {}
            }
        } catch {}
    }

    throw "D7 repair aborted safely. Backup: $BackupRoot. GADXVectorHub was left stopped/disabled whenever possible. Original error: $failure"
}
