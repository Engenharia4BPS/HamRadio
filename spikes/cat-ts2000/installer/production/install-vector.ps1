param(
    [Parameter(Mandatory=$true)][string]$InstallRoot,
    [string]$RadioKeyingPort = "COM22",
    [int]$RadioKeyingBaud = 9600,
    [string]$RigHost = "127.0.0.1",
    [int]$RigPort = 4532
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$RuntimeDir = Join-Path $InstallRoot "runtime"
$ConfigDir = Join-Path $InstallRoot "config"
$LogDir = Join-Path $InstallRoot "logs"
$ThirdPartyDir = Join-Path $InstallRoot "thirdparty"
$PythonInstaller = Join-Path $ThirdPartyDir "python-installer.exe"
$Com0comInstaller = Join-Path $ThirdPartyDir "com0com-installer.exe"
$BridgeIni = Join-Path $ConfigDir "bridge.ini"
$LoggerIni = Join-Path $ConfigDir "logger.ini"
$ServiceScript = Join-Path $InstallRoot "service\vector_bridge_service.py"
$PythonExe = Join-Path $RuntimeDir "python.exe"
$script:Com0comSetup = $null

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "GADX Vector Setup requires Administrator privileges."
    }
}

function Write-Utf8NoBom([string]$Path, [string]$Content) {
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function Find-Com0comSetup {
    $candidates = @(
        "$env:ProgramFiles\com0com\setupc.exe",
        "${env:ProgramFiles(x86)}\com0com\setupc.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) { return (Resolve-Path $candidate).Path }
    }
    return $null
}

function Ensure-Com0com {
    $existing = Find-Com0comSetup
    if ($existing) {
        $script:Com0comSetup = $existing
        Write-Host "com0com already installed: $existing"
        return
    }

    if (-not (Test-Path $Com0comInstaller)) {
        throw "Bundled com0com installer not found: $Com0comInstaller"
    }

    Write-Host "Installing signed com0com 3.0.0.0..."
    $oldPair1 = $env:CNC_INSTALL_CNCA0_CNCB0_PORTS
    $oldPair2 = $env:CNC_INSTALL_COMX_COMX_PORTS
    try {
        $env:CNC_INSTALL_CNCA0_CNCB0_PORTS = "NO"
        $env:CNC_INSTALL_COMX_COMX_PORTS = "NO"
        $p = Start-Process -FilePath $Com0comInstaller -ArgumentList @('/S') -Wait -PassThru
        if ($p.ExitCode -ne 0) { throw "com0com installer failed with exit code $($p.ExitCode)." }
    }
    finally {
        $env:CNC_INSTALL_CNCA0_CNCB0_PORTS = $oldPair1
        $env:CNC_INSTALL_COMX_COMX_PORTS = $oldPair2
    }

    Start-Sleep -Seconds 2
    $script:Com0comSetup = Find-Com0comSetup
    if (-not $script:Com0comSetup) {
        throw "com0com installer completed but setupc.exe was not found."
    }
}

function Invoke-Com0com([string[]]$Arguments, [switch]$Capture) {
    if (-not $script:Com0comSetup) { throw "com0com setupc.exe is not initialized." }
    $cwd = Split-Path -Parent $script:Com0comSetup
    Push-Location $cwd
    try {
        if ($Capture) {
            $output = @(& $script:Com0comSetup @Arguments 2>&1)
            $exitCode = [int]$LASTEXITCODE
            if ($exitCode -ne 0) { throw "com0com failed with exit code $exitCode" }
            return ,$output
        }
        & $script:Com0comSetup @Arguments
        if ($LASTEXITCODE -ne 0) { throw "com0com failed with exit code $LASTEXITCODE" }
    }
    finally { Pop-Location }
}

function Get-BusyComNumbers {
    $output = Invoke-Com0com -Arguments @('--silent','busynames','COM?*') -Capture
    $busy = [System.Collections.Generic.HashSet[int]]::new()
    foreach ($line in $output) {
        if ([string]$line -match '^\s*COM(\d+)\s*$') { [void]$busy.Add([int]$Matches[1]) }
    }
    return ,$busy
}

function Find-FreeCom([System.Collections.Generic.HashSet[int]]$Busy, [int]$Min, [int]$Max) {
    for ($n=$Min; $n -le $Max; $n++) {
        if (-not $Busy.Contains($n)) { return $n }
    }
    throw "No free COM port between COM$Min and COM$Max."
}

function Get-IniCom([string]$Path, [string]$Key) {
    if (-not (Test-Path $Path)) { return $null }
    foreach ($line in Get-Content $Path) {
        if ($line -match "^\s*$Key\s*=\s*COM(\d+)\s*$") { return [int]$Matches[1] }
    }
    return $null
}

function Test-ComPair([int]$Left, [int]$Right) {
    $output = Invoke-Com0com -Arguments @('--silent','list') -Capture
    $lf = $false; $rf = $false
    foreach ($line in $output) {
        $s = [string]$line
        if ($s -match "PortName=COM$Left(?:\s|$)|RealPortName=COM$Left(?:\s|$)") { $lf=$true }
        if ($s -match "PortName=COM$Right(?:\s|$)|RealPortName=COM$Right(?:\s|$)") { $rf=$true }
    }
    return ($lf -and $rf)
}

function Ensure-PythonRuntime {
    if (-not (Test-Path $PythonExe)) {
        if (-not (Test-Path $PythonInstaller)) { throw "Python installer payload not found: $PythonInstaller" }
        New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
        Write-Host "Installing private Python 3.10.11 runtime..."
        $args = @(
            '/quiet',
            'InstallAllUsers=1',
            "TargetDir=$RuntimeDir",
            'PrependPath=0',
            'AppendPath=0',
            'AssociateFiles=0',
            'Shortcuts=0',
            'Include_launcher=0',
            'Include_doc=0',
            'Include_test=0',
            'Include_tcltk=0',
            'Include_pip=1',
            'Include_exe=1',
            'Include_lib=1',
            'Include_dev=1'
        )
        $p = Start-Process -FilePath $PythonInstaller -ArgumentList $args -Wait -PassThru
        if ($p.ExitCode -ne 0) { throw "Private Python installation failed with exit code $($p.ExitCode)." }
        if (-not (Test-Path $PythonExe)) { throw "Python installer finished but $PythonExe does not exist." }
    }
    else {
        Write-Host "Private Python runtime already present: $PythonExe"
    }

    & $PythonExe -m pip install --disable-pip-version-check --upgrade "pyserial==3.5" "pywin32==312"
    if ($LASTEXITCODE -ne 0) { throw "Failed to install Vector Python dependencies." }

    $PythonServiceExe = Join-Path $RuntimeDir "pythonservice.exe"
    if (-not (Test-Path $PythonServiceExe)) {
        $postExe = Join-Path $RuntimeDir "Scripts\pywin32_postinstall.exe"
        $postPy = Join-Path $RuntimeDir "Scripts\pywin32_postinstall.py"
        if (Test-Path $postExe) { & $postExe -install }
        elseif (Test-Path $postPy) { & $PythonExe $postPy -install }
        else { throw "pywin32 post-install tool not found in private runtime." }
        if ($LASTEXITCODE -ne 0) { throw "pywin32 post-install failed." }
    }
}

function Ensure-ComPairs {
    $loggerCat = Get-IniCom $LoggerIni 'cat_port'
    $loggerKey = Get-IniCom $LoggerIni 'keying_port'
    $vectorCat = Get-IniCom $BridgeIni 'port'
    $vectorKey = Get-IniCom $BridgeIni 'keying_port'

    if ($null -ne $loggerCat -and $null -ne $loggerKey -and $null -ne $vectorCat -and $null -ne $vectorKey -and
        (Test-ComPair $loggerCat $vectorCat) -and (Test-ComPair $loggerKey $vectorKey)) {
        return @($loggerCat,$loggerKey,$vectorCat,$vectorKey)
    }

    $busy = Get-BusyComNumbers
    $loggerCat = Find-FreeCom $busy 10 30; [void]$busy.Add($loggerCat)
    $loggerKey = Find-FreeCom $busy 10 30; [void]$busy.Add($loggerKey)
    $vectorCat = Find-FreeCom $busy 100 199; [void]$busy.Add($vectorCat)
    $vectorKey = Find-FreeCom $busy 100 199; [void]$busy.Add($vectorKey)

    Invoke-Com0com -Arguments @('--wait','30','install',"PortName=COM$loggerCat","PortName=COM$vectorCat")
    Invoke-Com0com -Arguments @('--wait','30','install',"PortName=COM$loggerKey","PortName=COM$vectorKey")
    return @($loggerCat,$loggerKey,$vectorCat,$vectorKey)
}

function Install-Service {
    & $PythonExe $ServiceScript stop 2>$null | Out-Null
    & $PythonExe $ServiceScript remove 2>$null | Out-Null
    & $PythonExe $ServiceScript install
    if ($LASTEXITCODE -ne 0) { throw "Failed to install GADXVectorBridge service." }
    & sc.exe config GADXVectorBridge start= delayed-auto | Out-Null
    & sc.exe failure GADXVectorBridge reset= 86400 actions= restart/5000/restart/5000/restart/5000 | Out-Null
    & sc.exe failureflag GADXVectorBridge 1 | Out-Null
    & $PythonExe $ServiceScript start
    if ($LASTEXITCODE -ne 0) { throw "GADXVectorBridge service installed but did not start." }
}

Assert-Administrator
New-Item -ItemType Directory -Force -Path $InstallRoot,$RuntimeDir,$ConfigDir,$LogDir | Out-Null
Ensure-Com0com
Ensure-PythonRuntime
$ports = Ensure-ComPairs
$loggerCat,$loggerKey,$vectorCat,$vectorKey = $ports

$bridge = @"
[bridge]
port = COM$vectorCat
baud = 19200

keying_port = COM$vectorKey
keying_baud = 19200

radio_keying_port = $RadioKeyingPort
radio_keying_baud = $RadioKeyingBaud

rig_host = $RigHost
rig_port = $RigPort
poll_ms = 250

allow_write = true
allow_ptt = true
allow_cw = true

log_level = INFO
log_max_mb = 5
log_backups = 5
"@
Write-Utf8NoBom $BridgeIni $bridge

$logger = @"
[logger]
cat_port = COM$loggerCat
keying_port = COM$loggerKey
radio_model = TS-2000
cat_baud = 19200
"@
Write-Utf8NoBom $LoggerIni $logger

Install-Service

$summary = @"
GADX Vector installed successfully.

Logger configuration:
  Radio: Kenwood TS-2000
  CAT: COM$loggerCat @ 19200 8N1
  CW/PTT: COM$loggerKey
  DTR: PTT
  RTS: CW

Vector internal:
  CAT: COM$vectorCat
  Keying: COM$vectorKey

Radio:
  rigctld: ${RigHost}:$RigPort
  CW keying: $RadioKeyingPort @ $RadioKeyingBaud

Service: GADXVectorBridge
Install root: $InstallRoot
"@
Write-Utf8NoBom (Join-Path $InstallRoot 'config\install-summary.txt') $summary
Write-Host $summary
