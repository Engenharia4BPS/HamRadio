param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeDir = Join-Path $InstallRoot "runtime"
$ThirdPartyCandidates = @(
    (Join-Path $InstallRoot "thirdparty"),
    (Join-Path $InstallerRoot "thirdparty")
)
$PythonExe = Join-Path $RuntimeDir "python.exe"
$DependencyLockPath = Join-Path $InstallerRoot "dependency-lock.json"
$LockedPackageInstaller = Join-Path $InstallerRoot "install-locked-python-packages.ps1"
$DownloadCache = Join-Path $InstallerRoot "cache"

if (-not (Test-Path $DependencyLockPath -PathType Leaf)) {
    throw "dependency-lock.json was not found: $DependencyLockPath"
}
if (-not (Test-Path $LockedPackageInstaller -PathType Leaf)) {
    throw "Locked Python package installer was not found: $LockedPackageInstaller"
}

$DependencyLock = Get-Content -LiteralPath $DependencyLockPath -Raw | ConvertFrom-Json
if ([int]$DependencyLock.format -ne 1) { throw "Unsupported dependency-lock format." }

$PythonArtifact = $DependencyLock.python
foreach ($field in @('version','filename','url','size','sha256')) {
    if (-not $PythonArtifact.$field) { throw "Python dependency lock is missing required field '$field'." }
}
if ([string]$PythonArtifact.url -notmatch '^https://') { throw "Python dependency lock URL must use HTTPS." }
if ([string]$PythonArtifact.sha256 -notmatch '^[0-9a-fA-F]{64}$') { throw "Python dependency lock SHA256 is invalid." }
if ([int64]$PythonArtifact.size -le 0) { throw "Python dependency lock size is invalid." }

$PythonVersion = [string]$PythonArtifact.version
$pythonParts = $PythonVersion.Split('.')
if ($pythonParts.Count -lt 2) { throw "Python dependency lock version is invalid: $PythonVersion" }
$PythonSeries = "$($pythonParts[0]).$($pythonParts[1])"
$PythonDownloadUrl = [string]$PythonArtifact.url
$DownloadedPythonInstaller = Join-Path $DownloadCache ([string]$PythonArtifact.filename)

$PySerialVersion = $null
$PyWin32Version = $null
foreach ($pkg in @($DependencyLock.python_packages)) {
    if ([string]$pkg.name -eq 'pyserial') { $PySerialVersion = [string]$pkg.version }
    if ([string]$pkg.name -eq 'pywin32') { $PyWin32Version = [string]$pkg.version }
}
if (-not $PySerialVersion) { throw "dependency-lock.json does not contain pyserial." }
if (-not $PyWin32Version) { throw "dependency-lock.json does not contain pywin32." }

$Com0comArtifact = $DependencyLock.com0com
if (-not $Com0comArtifact -or -not [bool]$Com0comArtifact.pinned_distribution) {
    throw "dependency-lock.json does not contain a pinned com0com distribution."
}
foreach ($field in @('version','filename','url','size','sha256','required_executable')) {
    if (-not $Com0comArtifact.$field) { throw "com0com dependency lock is missing required field '$field'." }
}
if ([string]$Com0comArtifact.url -notmatch '^https://') { throw "com0com dependency lock URL must use HTTPS." }
if ([string]$Com0comArtifact.sha256 -notmatch '^[0-9a-fA-F]{64}$') { throw "com0com dependency lock SHA256 is invalid." }
if ([int64]$Com0comArtifact.size -le 0) { throw "com0com dependency lock size is invalid." }
if (@($Com0comArtifact.installed_files).Count -eq 0) { throw "com0com dependency lock does not contain installed file fingerprints." }
$Com0comVersion = [string]$Com0comArtifact.version
$DownloadedCom0comInstaller = Join-Path $DownloadCache ([string]$Com0comArtifact.filename)

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this script from an elevated PowerShell prompt."
    }
}

function Find-BundledFile([string]$Name) {
    foreach ($dir in $ThirdPartyCandidates) {
        $candidate = Join-Path $dir $Name
        if (Test-Path $candidate -PathType Leaf) { return $candidate }
    }
    return $null
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

function Test-LockedArtifactFile([string]$Path,$Artifact) {
    if (-not (Test-Path $Path -PathType Leaf)) { return $false }
    $file = Get-Item -LiteralPath $Path
    if ([int64]$file.Length -ne [int64]$Artifact.size) { return $false }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
    $expected = ([string]$Artifact.sha256).ToLowerInvariant()
    return ($actual -eq $expected)
}

function Test-Com0comInstalledLock([string]$SetupPath) {
    if (-not $SetupPath -or -not (Test-Path $SetupPath -PathType Leaf)) { return $false }
    $installDir = Split-Path -Parent $SetupPath
    foreach ($entry in @($Com0comArtifact.installed_files)) {
        foreach ($field in @('name','size','sha256')) {
            if (-not $entry.$field) { throw "com0com installed file lock is missing required field '$field'." }
        }
        $candidate = Join-Path $installDir ([string]$entry.name)
        if (-not (Test-LockedArtifactFile $candidate $entry)) { return $false }
    }
    return $true
}

function Get-Com0comInstaller([switch]$Download) {
    $bundled = Find-BundledFile ([string]$Com0comArtifact.filename)
    if (-not $bundled) { $bundled = Find-BundledFile "com0com-installer.exe" }
    if ($bundled) {
        if (-not (Test-LockedArtifactFile $bundled $Com0comArtifact)) {
            throw "Bundled com0com installer does not match dependency-lock.json size/SHA256."
        }
        return $bundled
    }

    if (Test-Path $DownloadedCom0comInstaller -PathType Leaf) {
        if (Test-LockedArtifactFile $DownloadedCom0comInstaller $Com0comArtifact) {
            return $DownloadedCom0comInstaller
        }
        if (-not $Download) { return $null }
        Write-Host "Cached com0com installer failed dependency lock validation; removing it." -ForegroundColor Yellow
        Remove-Item -LiteralPath $DownloadedCom0comInstaller -Force
    }

    if (-not $Download) { return $null }

    New-Item -ItemType Directory -Force -Path $DownloadCache | Out-Null
    Write-Host "Downloading locked com0com $Com0comVersion distribution..."
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri ([string]$Com0comArtifact.url) -OutFile $DownloadedCom0comInstaller
    }
    catch {
        if (Test-Path $DownloadedCom0comInstaller) { Remove-Item -LiteralPath $DownloadedCom0comInstaller -Force -ErrorAction SilentlyContinue }
        throw "Unable to download locked com0com $Com0comVersion. $($_.Exception.Message)"
    }

    if (-not (Test-LockedArtifactFile $DownloadedCom0comInstaller $Com0comArtifact)) {
        $actualSize = if (Test-Path $DownloadedCom0comInstaller -PathType Leaf) { (Get-Item -LiteralPath $DownloadedCom0comInstaller).Length } else { 0 }
        $actualHash = if (Test-Path $DownloadedCom0comInstaller -PathType Leaf) { (Get-FileHash -Algorithm SHA256 -LiteralPath $DownloadedCom0comInstaller).Hash.ToLowerInvariant() } else { "missing" }
        if (Test-Path $DownloadedCom0comInstaller) { Remove-Item -LiteralPath $DownloadedCom0comInstaller -Force -ErrorAction SilentlyContinue }
        throw "com0com installer failed dependency-lock validation after download. expectedSize=$([int64]$Com0comArtifact.size) actualSize=$actualSize expectedSha=$([string]$Com0comArtifact.sha256) actualSha=$actualHash"
    }

    Write-Host "Locked com0com installer verified: size + SHA256"
    return $DownloadedCom0comInstaller
}

function Test-Runtime {
    if (-not (Test-Path $PythonExe -PathType Leaf)) { return $false }
    $oldNoUserSite = $env:PYTHONNOUSERSITE
    try {
        $env:PYTHONNOUSERSITE = "1"
        $code = "import platform,tkinter,serial,win32serviceutil,servicemanager; from importlib.metadata import version; raise SystemExit(0 if platform.python_version() == '$PythonVersion' and version('pyserial') == '$PySerialVersion' and version('pywin32') == '$PyWin32Version' else 1)"
        & $PythonExe -c $code *> $null
        return ($LASTEXITCODE -eq 0)
    }
    finally {
        $env:PYTHONNOUSERSITE = $oldNoUserSite
    }
}

function Test-Pywin32ServiceHost {
    if (-not (Test-Path (Join-Path $RuntimeDir "pythonservice.exe") -PathType Leaf)) { return $false }
    foreach ($name in @("pywintypes310.dll","pythoncom310.dll")) {
        if (-not (Test-Path (Join-Path $RuntimeDir $name) -PathType Leaf)) { return $false }
    }
    return $true
}

function Ensure-Pywin32ServiceHost {
    $win32Dir = Join-Path $RuntimeDir "Lib\site-packages\win32"
    $system32Dir = Join-Path $RuntimeDir "Lib\site-packages\pywin32_system32"
    $serviceSource = Join-Path $win32Dir "pythonservice.exe"
    $serviceDestination = Join-Path $RuntimeDir "pythonservice.exe"

    if (Test-Path $serviceSource -PathType Leaf) {
        Copy-Item -LiteralPath $serviceSource -Destination $serviceDestination -Force
    }
    elseif (Test-Path $serviceDestination -PathType Leaf) {
        Write-Host "Using existing private pythonservice.exe already staged in runtime."
    }
    else {
        Write-Host "pythonservice.exe is missing; repairing pywin32 from locked wheel..." -ForegroundColor Yellow
        $oldNoUserSite = $env:PYTHONNOUSERSITE
        try {
            $env:PYTHONNOUSERSITE = "1"
            & $LockedPackageInstaller -PythonExe $PythonExe -Package "pywin32" -ForceReinstall
        }
        finally {
            $env:PYTHONNOUSERSITE = $oldNoUserSite
        }

        if (Test-Path $serviceSource -PathType Leaf) {
            Copy-Item -LiteralPath $serviceSource -Destination $serviceDestination -Force
        }
        elseif (-not (Test-Path $serviceDestination -PathType Leaf)) {
            throw "pywin32 service host was not found after locked package repair."
        }
    }

    foreach ($name in @("pywintypes310.dll","pythoncom310.dll")) {
        $source = Join-Path $system32Dir $name
        $destination = Join-Path $RuntimeDir $name
        if (-not (Test-Path $source -PathType Leaf)) {
            throw "pywin32 service DLL was not found: $source"
        }
        Copy-Item -LiteralPath $source -Destination $destination -Force
    }

    $oldNoUserSite = $env:PYTHONNOUSERSITE
    try {
        $env:PYTHONNOUSERSITE = "1"
        & $PythonExe -c "import pythoncom, pywintypes, servicemanager, win32serviceutil; print('PYWIN32_SERVICE_HOST_OK')"
        if ($LASTEXITCODE -ne 0) { throw "Private pywin32 service-host validation failed." }
    }
    finally {
        $env:PYTHONNOUSERSITE = $oldNoUserSite
    }

    if (-not (Test-Pywin32ServiceHost)) {
        throw "Private pywin32 service host is incomplete after staging."
    }
}

function Get-PythonProbe([string]$Candidate) {
    if (-not $Candidate -or -not (Test-Path $Candidate -PathType Leaf)) { return $null }
    try {
        $probe = & $Candidate -c "import struct,sys,tkinter; print('%d.%d.%d|%d|%s' % (sys.version_info[0],sys.version_info[1],sys.version_info[2],struct.calcsize('P')*8,sys.executable))" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $probe) { return $null }
        return ([string]$probe).Trim()
    }
    catch { return $null }
}

function Test-CompatiblePython([string]$Candidate) {
    if (-not $Candidate -or -not (Test-Path $Candidate -PathType Leaf)) { return $false }
    try {
        $versionTuple = ($PythonVersion.Split('.') | ForEach-Object { [int]$_ }) -join ','
        & $Candidate -c "import struct,sys,tkinter; raise SystemExit(0 if sys.version_info[:3] == ($versionTuple) and struct.calcsize('P')*8 == 64 else 1)" 2>$null
        return ($LASTEXITCODE -eq 0)
    }
    catch { return $false }
}

function Add-PythonCandidate([System.Collections.Generic.List[string]]$List,[string]$Candidate) {
    if (-not $Candidate) { return }
    try { $Candidate = [System.IO.Path]::GetFullPath($Candidate) } catch { return }
    if ($Candidate -ieq $PythonExe) { return }
    if (-not $List.Contains($Candidate)) { [void]$List.Add($Candidate) }
}

function Get-PythonCandidates {
    $candidates = New-Object 'System.Collections.Generic.List[string]'

    try {
        $py = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($py) {
            $resolved = & $py.Source -3.10 -c 'import sys; print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0 -and $resolved) { Add-PythonCandidate $candidates ([string]$resolved).Trim() }
        }
    } catch {}

    foreach ($registryRoot in @(
        'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Python\PythonCore',
        'Registry::HKEY_CURRENT_USER\SOFTWARE\Python\PythonCore',
        'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Python\PythonCore',
        'Registry::HKEY_CURRENT_USER\SOFTWARE\WOW6432Node\Python\PythonCore'
    )) {
        if (-not (Test-Path $registryRoot)) { continue }
        foreach ($versionKey in @(Get-ChildItem -LiteralPath $registryRoot -ErrorAction SilentlyContinue)) {
            if ($versionKey.PSChildName -notlike '3.10*') { continue }
            $installKey = Join-Path $versionKey.PSPath 'InstallPath'
            if (-not (Test-Path $installKey)) { continue }
            try {
                $props = Get-ItemProperty -LiteralPath $installKey -ErrorAction SilentlyContinue
                if ($props.ExecutablePath) { Add-PythonCandidate $candidates ([string]$props.ExecutablePath) }
            } catch {}
            try {
                $dir = (Get-Item -LiteralPath $installKey).GetValue('')
                if ($dir) { Add-PythonCandidate $candidates (Join-Path ([string]$dir) 'python.exe') }
            } catch {}
        }
    }

    foreach ($candidate in @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python310\python.exe'),
        (Join-Path $env:ProgramFiles 'Python310\python.exe'),
        $(if (${env:ProgramFiles(x86)}) { Join-Path ${env:ProgramFiles(x86)} 'Python310\python.exe' } else { $null }),
        'C:\Python310\python.exe',
        'C:\Python\Python310\python.exe'
    )) {
        Add-PythonCandidate $candidates $candidate
    }

    try {
        foreach ($profile in @(Get-ChildItem 'C:\Users' -Directory -ErrorAction SilentlyContinue)) {
            Add-PythonCandidate $candidates (Join-Path $profile.FullName 'AppData\Local\Programs\Python\Python310\python.exe')
        }
    } catch {}

    try {
        foreach ($cmd in @(Get-Command python.exe -All -ErrorAction SilentlyContinue)) {
            Add-PythonCandidate $candidates $cmd.Source
        }
    } catch {}

    return $candidates
}

function Find-CompatiblePython {
    foreach ($candidate in @(Get-PythonCandidates)) {
        if (Test-CompatiblePython $candidate) { return $candidate }
    }
    return $null
}

function Show-PythonDiscoveryDiagnostics {
    $candidates = @(Get-PythonCandidates)
    if ($candidates.Count -eq 0) {
        Write-Host "Python discovery: no candidate python.exe paths were found." -ForegroundColor Yellow
        return
    }
    Write-Host "Python discovery candidates:" -ForegroundColor Yellow
    foreach ($candidate in $candidates) {
        $probe = Get-PythonProbe $candidate
        if ($probe) { Write-Host "  + $candidate -> $probe" }
        else { Write-Host "  - $candidate -> not usable (requires locked Python $PythonVersion x64 with Tcl/Tk)" }
    }
}

function Initialize-PrivateRuntimeFromExisting([string]$SourcePython) {
    if (-not (Test-CompatiblePython $SourcePython)) {
        throw "Existing Python candidate is not compatible with the locked Python $PythonVersion x64 + Tcl/Tk runtime: $SourcePython"
    }

    $sourceRoot = Split-Path -Parent $SourcePython
    if ([System.IO.Path]::GetFullPath($sourceRoot) -ieq [System.IO.Path]::GetFullPath($RuntimeDir)) { return }

    Write-Host "Creating isolated Vector runtime from existing locked-version Python: $SourcePython"
    if (Test-Path $RuntimeDir) { Remove-Item -LiteralPath $RuntimeDir -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
    Copy-Item -Path (Join-Path $sourceRoot '*') -Destination $RuntimeDir -Recurse -Force

    if (-not (Test-Path $PythonExe -PathType Leaf)) {
        throw "Existing Python copy completed but runtime\python.exe is missing."
    }

    $sitePackages = Join-Path $RuntimeDir 'Lib\site-packages'
    if (Test-Path $sitePackages) {
        Get-ChildItem -LiteralPath $sitePackages -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    } else {
        New-Item -ItemType Directory -Force -Path $sitePackages | Out-Null
    }
    $scripts = Join-Path $RuntimeDir 'Scripts'
    if (Test-Path $scripts) {
        Get-ChildItem -LiteralPath $scripts -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    } else {
        New-Item -ItemType Directory -Force -Path $scripts | Out-Null
    }

    $oldNoUserSite = $env:PYTHONNOUSERSITE
    try {
        $env:PYTHONNOUSERSITE = "1"
        & $PythonExe -m ensurepip --upgrade
        if ($LASTEXITCODE -ne 0) { throw "ensurepip failed while preparing the private runtime." }
    }
    finally {
        $env:PYTHONNOUSERSITE = $oldNoUserSite
    }
}

function Get-PythonInstaller([switch]$Download) {
    $bundled = Find-BundledFile "python-installer.exe"
    if ($bundled) {
        if (-not (Test-LockedArtifactFile $bundled $PythonArtifact)) {
            throw "Bundled python-installer.exe does not match dependency-lock.json size/SHA256."
        }
        return $bundled
    }

    if (Test-Path $DownloadedPythonInstaller -PathType Leaf) {
        if (Test-LockedArtifactFile $DownloadedPythonInstaller $PythonArtifact) {
            return $DownloadedPythonInstaller
        }
        if (-not $Download) { return $null }
        Write-Host "Cached Python installer failed dependency lock validation; removing it." -ForegroundColor Yellow
        Remove-Item -LiteralPath $DownloadedPythonInstaller -Force
    }

    if (-not $Download) { return $null }

    New-Item -ItemType Directory -Force -Path $DownloadCache | Out-Null
    Write-Host "Downloading locked Python $PythonVersion installer from python.org..."
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri $PythonDownloadUrl -OutFile $DownloadedPythonInstaller
    }
    catch {
        if (Test-Path $DownloadedPythonInstaller) { Remove-Item -Force $DownloadedPythonInstaller -ErrorAction SilentlyContinue }
        throw "Unable to download locked Python $PythonVersion from python.org. $($_.Exception.Message)"
    }

    if (-not (Test-LockedArtifactFile $DownloadedPythonInstaller $PythonArtifact)) {
        if (Test-Path $DownloadedPythonInstaller) { Remove-Item -Force $DownloadedPythonInstaller -ErrorAction SilentlyContinue }
        throw "Python installer failed dependency-lock size/SHA256 validation after download."
    }

    Write-Host "Locked Python installer verified: size + SHA256"
    return $DownloadedPythonInstaller
}

Assert-Administrator
$pythonInstaller = Get-PythonInstaller
$com0comSetup = Find-Com0comSetup
$com0comInstalledLocked = if ($com0comSetup) { Test-Com0comInstalledLock $com0comSetup } else { $false }
$com0comInstaller = if (-not $com0comInstalledLocked) { Get-Com0comInstaller } else { $null }
$runtimeOk = Test-Runtime
$serviceHostOk = if ($runtimeOk) { Test-Pywin32ServiceHost } else { $false }
$existingCompatiblePython = if (-not $runtimeOk) { Find-CompatiblePython } else { $null }

Write-Host ""
Write-Host "GADX Vector - Runtime/com0com ensure" -ForegroundColor Cyan
Write-Host "Install root : $InstallRoot"
Write-Host "Dependency lock: Python $PythonVersion / pyserial $PySerialVersion / pywin32 $PyWin32Version / com0com $Com0comVersion"
Write-Host "Runtime      : $(if ($runtimeOk) { 'OK - locked versions' } elseif (Test-Path $PythonExe) { 'INCOMPLETE OR VERSION DRIFT' } else { 'MISSING' })"
Write-Host "Service host : $(if ($serviceHostOk) { 'OK' } elseif ($runtimeOk) { 'INCOMPLETE - pywin32 service DLL staging required' } else { 'pending runtime creation' })"
Write-Host "com0com      : $(if ($com0comInstalledLocked) { "OK - locked $Com0comVersion ($com0comSetup)" } elseif ($com0comSetup) { "VERSION/HASH DRIFT ($com0comSetup)" } else { 'MISSING' })"
Write-Host "Python setup : $(if ($existingCompatiblePython) { "locked-version existing Python: $existingCompatiblePython" } elseif ($pythonInstaller) { "$pythonInstaller (verified by dependency lock)" } else { "will download locked Python $PythonVersion from python.org and verify SHA256" })"
Write-Host "com0com setup: $(if ($com0comInstalledLocked) { 'not required - installed files match dependency lock' } elseif ($com0comInstaller) { "$com0comInstaller (verified by dependency lock)" } elseif (-not $com0comSetup) { "will download locked $([string]$Com0comArtifact.filename) and verify SHA256" } else { 'blocked - installed com0com does not match dependency lock' })"
Write-Host ""

if (-not $Apply) {
    Write-Host "PREVIEW ONLY - no changes were made." -ForegroundColor Yellow
    if (-not $runtimeOk) {
        if ($existingCompatiblePython) {
            Write-Host "  -> Exact locked Python $PythonVersion x64 with Tcl/Tk already exists on this machine."
            Write-Host "  -> It will be copied into the private Vector runtime without altering the existing installation."
        } else {
            if (-not $pythonInstaller) { Write-Host "  -> Locked Python $PythonVersion installer will be downloaded and SHA256-verified before execution." }
            Write-Host "  -> Private runtime will receive only dependency-lock verified pyserial/pywin32 wheels."
            Write-Host "  -> If the official installer does not create TargetDir, Vector will search for exact Python $PythonVersion x64 + Tcl/Tk and clone it."
        }
    }
    if ($runtimeOk -and -not $serviceHostOk) {
        Write-Host "  -> pywin32 service host will be repaired from the verified locked pywin32 wheel."
    }
    if ($com0comSetup -and -not $com0comInstalledLocked) {
        Write-Host "  -> Existing com0com does not match the dependency lock and will NOT be replaced automatically." -ForegroundColor Yellow
        Write-Host "  -> Repair requires an explicit controlled com0com migration path."
    }
    elseif (-not $com0comSetup) {
        Write-Host "  -> Locked com0com $Com0comVersion will be downloaded, size/SHA256 verified, then installed without default COM pairs."
    }
    if ($com0comInstalledLocked) { Write-Host "COM0COM_DEPENDENCY_LOCK_OK" -ForegroundColor Green }
    exit 0
}

if ($com0comSetup -and -not $com0comInstalledLocked) {
    throw "Existing com0com installation does not match dependency-lock.json. Automatic replacement is intentionally blocked."
}

if (-not $com0comSetup) {
    $com0comInstaller = Get-Com0comInstaller -Download
    if (-not $com0comInstaller) { throw "Locked com0com installer could not be acquired." }
    Write-Host "Installing locked com0com $Com0comVersion..."
    $old1 = $env:CNC_INSTALL_CNCA0_CNCB0_PORTS
    $old2 = $env:CNC_INSTALL_COMX_COMX_PORTS
    try {
        $env:CNC_INSTALL_CNCA0_CNCB0_PORTS = "NO"
        $env:CNC_INSTALL_COMX_COMX_PORTS = "NO"
        $p = Start-Process -FilePath $com0comInstaller -ArgumentList @('/S') -Wait -PassThru
        if ($p.ExitCode -ne 0) { throw "Locked com0com installer failed with exit code $($p.ExitCode)." }
    }
    finally {
        $env:CNC_INSTALL_CNCA0_CNCB0_PORTS = $old1
        $env:CNC_INSTALL_COMX_COMX_PORTS = $old2
    }
    Start-Sleep -Seconds 2
    $com0comSetup = Find-Com0comSetup
    if (-not $com0comSetup) { throw "com0com installation completed but setupc.exe was not found." }
    if (-not (Test-Com0comInstalledLock $com0comSetup)) {
        throw "Installed com0com files do not match dependency-lock.json after installation."
    }
    $com0comInstalledLocked = $true
}

if (-not $runtimeOk) {
    if ($existingCompatiblePython) {
        Initialize-PrivateRuntimeFromExisting $existingCompatiblePython
    } else {
        $pythonInstaller = Get-PythonInstaller -Download
        New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
        Write-Host "Installing/repairing private locked Python $PythonVersion runtime with Tcl/Tk..."
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
            'Include_tcltk=1',
            'Include_pip=1',
            'Include_exe=1',
            'Include_lib=1',
            'Include_dev=1'
        )
        $p = Start-Process -FilePath $pythonInstaller -ArgumentList $args -Wait -PassThru
        if ($p.ExitCode -ne 0) { throw "Private Python installation/repair failed with exit code $($p.ExitCode)." }

        if (-not (Test-Path $PythonExe -PathType Leaf)) {
            $fallbackPython = Find-CompatiblePython
            if ($fallbackPython) {
                Write-Host "Python installer did not create TargetDir; cloning exact locked Python into the Vector private runtime..." -ForegroundColor Yellow
                Initialize-PrivateRuntimeFromExisting $fallbackPython
            }
        }

        if (-not (Test-Path $PythonExe -PathType Leaf)) {
            Show-PythonDiscoveryDiagnostics
            throw "Python installer finished but runtime\python.exe is missing and no exact Python $PythonVersion x64 + Tcl/Tk installation could be cloned."
        }
    }

    Write-Host "Installing locked Python dependencies..."
    $oldNoUserSite = $env:PYTHONNOUSERSITE
    try {
        $env:PYTHONNOUSERSITE = "1"
        & $LockedPackageInstaller -PythonExe $PythonExe
    }
    finally {
        $env:PYTHONNOUSERSITE = $oldNoUserSite
    }
}

Write-Host "Staging private pywin32 Windows-service host..."
Ensure-Pywin32ServiceHost

if (-not (Test-Runtime)) { throw "Private runtime validation failed after locked install/repair." }
if (-not $com0comSetup -or -not (Test-Com0comInstalledLock $com0comSetup)) {
    throw "com0com validation failed after locked install/repair."
}

Write-Host ""
Write-Host "Runtime/com0com ensure completed successfully." -ForegroundColor Green
Write-Host "Python : $PythonExe"
Write-Host "Service: $(Join-Path $RuntimeDir 'pythonservice.exe')"
Write-Host "com0com: $com0comSetup"
Write-Host "RUNTIME_DEPENDENCY_LOCK_OK" -ForegroundColor Green
Write-Host "COM0COM_DEPENDENCY_LOCK_OK" -ForegroundColor Green