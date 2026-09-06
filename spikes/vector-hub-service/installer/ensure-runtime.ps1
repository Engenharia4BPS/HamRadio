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
$PythonVersion = "3.10.11"
$PythonSeries = "3.10"
$PythonDownloadUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe"
$DownloadCache = Join-Path $InstallerRoot "cache"
$DownloadedPythonInstaller = Join-Path $DownloadCache "python-$PythonVersion-amd64.exe"

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

function Test-Runtime {
    if (-not (Test-Path $PythonExe -PathType Leaf)) { return $false }
    $oldNoUserSite = $env:PYTHONNOUSERSITE
    try {
        $env:PYTHONNOUSERSITE = "1"
        & $PythonExe -c "import tkinter, serial, win32serviceutil, servicemanager" *> $null
        return ($LASTEXITCODE -eq 0)
    }
    finally {
        $env:PYTHONNOUSERSITE = $oldNoUserSite
    }
}

function Get-PythonProbe([string]$Candidate) {
    if (-not $Candidate -or -not (Test-Path $Candidate -PathType Leaf)) { return $null }
    try {
        $probe = & $Candidate -c 'import struct,sys,tkinter; print("%d.%d.%d|%d|%s" % (sys.version_info[0],sys.version_info[1],sys.version_info[2],struct.calcsize("P")*8,sys.executable))' 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $probe) { return $null }
        return ([string]$probe).Trim()
    }
    catch { return $null }
}

function Test-CompatiblePython([string]$Candidate) {
    if (-not $Candidate -or -not (Test-Path $Candidate -PathType Leaf)) { return $false }
    try {
        & $Candidate -c 'import struct,sys,tkinter; raise SystemExit(0 if sys.version_info[:2] == (3,10) and struct.calcsize("P")*8 == 64 else 1)' 2>$null
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

    # Python launcher is the most reliable way to locate registered 3.10 installs.
    try {
        $py = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($py) {
            $resolved = & $py.Source -3.10 -c 'import sys; print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0 -and $resolved) { Add-PythonCandidate $candidates ([string]$resolved).Trim() }
        }
    } catch {}

    # PEP 514 registry locations, both machine-wide and per-user.
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

    # Common install locations not always represented in PATH/registry.
    foreach ($candidate in @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python310\python.exe'),
        (Join-Path $env:ProgramFiles 'Python310\python.exe'),
        $(if (${env:ProgramFiles(x86)}) { Join-Path ${env:ProgramFiles(x86)} 'Python310\python.exe' } else { $null }),
        'C:\Python310\python.exe',
        'C:\Python\Python310\python.exe'
    )) {
        Add-PythonCandidate $candidates $candidate
    }

    # An elevated installer may have installed Python under another local profile.
    try {
        foreach ($profile in @(Get-ChildItem 'C:\Users' -Directory -ErrorAction SilentlyContinue)) {
            Add-PythonCandidate $candidates (Join-Path $profile.FullName 'AppData\Local\Programs\Python\Python310\python.exe')
        }
    } catch {}

    # Finally inspect all python.exe commands visible to this PowerShell process.
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
        else { Write-Host "  - $candidate -> not usable (requires Python 3.10 x64 with Tcl/Tk)" }
    }
}

function Initialize-PrivateRuntimeFromExisting([string]$SourcePython) {
    if (-not (Test-CompatiblePython $SourcePython)) {
        throw "Existing Python candidate is not compatible with the required Python $PythonSeries x64 + Tcl/Tk runtime: $SourcePython"
    }

    $sourceRoot = Split-Path -Parent $SourcePython
    if ([System.IO.Path]::GetFullPath($sourceRoot) -ieq [System.IO.Path]::GetFullPath($RuntimeDir)) { return }

    Write-Host "Creating isolated Vector runtime from existing compatible Python: $SourcePython"
    if (Test-Path $RuntimeDir) { Remove-Item -LiteralPath $RuntimeDir -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
    Copy-Item -Path (Join-Path $sourceRoot '*') -Destination $RuntimeDir -Recurse -Force

    if (-not (Test-Path $PythonExe -PathType Leaf)) {
        throw "Existing Python copy completed but runtime\python.exe is missing."
    }

    # Do not inherit third-party packages from the machine-wide/user installation.
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
    if ($bundled) { return $bundled }
    if (Test-Path $DownloadedPythonInstaller -PathType Leaf) { return $DownloadedPythonInstaller }
    if (-not $Download) { return $null }

    New-Item -ItemType Directory -Force -Path $DownloadCache | Out-Null
    Write-Host "Downloading official Python $PythonVersion installer from python.org..."
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri $PythonDownloadUrl -OutFile $DownloadedPythonInstaller
    }
    catch {
        if (Test-Path $DownloadedPythonInstaller) { Remove-Item -Force $DownloadedPythonInstaller -ErrorAction SilentlyContinue }
        throw "Unable to download Python $PythonVersion from python.org. $($_.Exception.Message)"
    }
    if (-not (Test-Path $DownloadedPythonInstaller -PathType Leaf)) {
        throw "Python download finished but installer file was not created."
    }
    return $DownloadedPythonInstaller
}

Assert-Administrator
$pythonInstaller = Get-PythonInstaller
$com0comInstaller = Find-BundledFile "com0com-installer.exe"
$com0comSetup = Find-Com0comSetup
$runtimeOk = Test-Runtime
$existingCompatiblePython = if (-not $runtimeOk) { Find-CompatiblePython } else { $null }

Write-Host ""
Write-Host "GADX Vector - Runtime/com0com ensure" -ForegroundColor Cyan
Write-Host "Install root : $InstallRoot"
Write-Host "Runtime      : $(if ($runtimeOk) { 'OK' } elseif (Test-Path $PythonExe) { 'INCOMPLETE' } else { 'MISSING' })"
Write-Host "com0com      : $(if ($com0comSetup) { $com0comSetup } else { 'not installed' })"
Write-Host "Python setup : $(if ($existingCompatiblePython) { "compatible existing Python: $existingCompatiblePython" } elseif ($pythonInstaller) { $pythonInstaller } else { 'will download official Python 3.10.11 from python.org' })"
Write-Host "com0com setup: $(if ($com0comInstaller) { $com0comInstaller } else { 'not bundled' })"
Write-Host ""

if (-not $Apply) {
    Write-Host "PREVIEW ONLY - no changes were made." -ForegroundColor Yellow
    if (-not $runtimeOk) {
        if ($existingCompatiblePython) {
            Write-Host "  -> A compatible Python $PythonSeries x64 installation with Tcl/Tk already exists on this machine."
            Write-Host "  -> It will be copied into the private Vector runtime without altering the existing installation."
        } else {
            if (-not $pythonInstaller) { Write-Host "  -> Official Python $PythonVersion installer will be downloaded from python.org." }
            Write-Host "  -> Private Python runtime will be installed/repaired with Tcl/Tk, pip, pyserial and pywin32."
            Write-Host "  -> If the official installer does not create TargetDir, Vector will search all common Windows locations for any compatible Python $PythonSeries x64 + Tcl/Tk and clone it."
        }
    }
    if (-not $com0comSetup) { Write-Host "  -> com0com will be installed if its bundled installer is available." }
    exit 0
}

if (-not $com0comSetup) {
    if (-not $com0comInstaller) { throw "com0com is missing and bundled com0com-installer.exe was not found." }
    Write-Host "Installing com0com..."
    $old1 = $env:CNC_INSTALL_CNCA0_CNCB0_PORTS
    $old2 = $env:CNC_INSTALL_COMX_COMX_PORTS
    try {
        $env:CNC_INSTALL_CNCA0_CNCB0_PORTS = "NO"
        $env:CNC_INSTALL_COMX_COMX_PORTS = "NO"
        $p = Start-Process -FilePath $com0comInstaller -ArgumentList @('/S') -Wait -PassThru
        if ($p.ExitCode -ne 0) { throw "com0com installer failed with exit code $($p.ExitCode)." }
    }
    finally {
        $env:CNC_INSTALL_CNCA0_CNCB0_PORTS = $old1
        $env:CNC_INSTALL_COMX_COMX_PORTS = $old2
    }
    Start-Sleep -Seconds 2
    $com0comSetup = Find-Com0comSetup
    if (-not $com0comSetup) { throw "com0com installation completed but setupc.exe was not found." }
}

if (-not $runtimeOk) {
    if ($existingCompatiblePython) {
        Initialize-PrivateRuntimeFromExisting $existingCompatiblePython
    } else {
        $pythonInstaller = Get-PythonInstaller -Download
        New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
        Write-Host "Installing/repairing private Python $PythonVersion runtime with Tcl/Tk..."
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
            # Some Windows Python installer states may reuse/repair an installation
            # instead of honoring TargetDir. Search broadly for a compatible 3.10 x64
            # installation with Tcl/Tk and clone it into Vector's private runtime.
            $fallbackPython = Find-CompatiblePython
            if ($fallbackPython) {
                Write-Host "Python installer did not create TargetDir; cloning compatible Python into the Vector private runtime..." -ForegroundColor Yellow
                Initialize-PrivateRuntimeFromExisting $fallbackPython
            }
        }

        if (-not (Test-Path $PythonExe -PathType Leaf)) {
            Show-PythonDiscoveryDiagnostics
            throw "Python installer finished but runtime\python.exe is missing and no compatible Python $PythonSeries x64 + Tcl/Tk installation could be cloned."
        }
    }

    Write-Host "Installing Python dependencies..."
    $oldNoUserSite = $env:PYTHONNOUSERSITE
    try {
        $env:PYTHONNOUSERSITE = "1"
        & $PythonExe -m pip install --disable-pip-version-check --upgrade "pyserial==3.5" "pywin32==312"
        if ($LASTEXITCODE -ne 0) { throw "Failed to install pyserial/pywin32." }
    }
    finally {
        $env:PYTHONNOUSERSITE = $oldNoUserSite
    }

    $pythonService = Join-Path $RuntimeDir "pythonservice.exe"
    if (-not (Test-Path $pythonService -PathType Leaf)) {
        $postExe = Join-Path $RuntimeDir "Scripts\pywin32_postinstall.exe"
        $postPy = Join-Path $RuntimeDir "Scripts\pywin32_postinstall.py"
        if (Test-Path $postExe -PathType Leaf) { & $postExe -install }
        elseif (Test-Path $postPy -PathType Leaf) { & $PythonExe $postPy -install }
        else { throw "pywin32 post-install tool was not found." }
        if ($LASTEXITCODE -ne 0) { throw "pywin32 post-install failed." }
    }
}

if (-not (Test-Runtime)) { throw "Private runtime validation failed after install/repair." }

Write-Host ""
Write-Host "Runtime/com0com ensure completed successfully." -ForegroundColor Green
Write-Host "Python : $PythonExe"
Write-Host "com0com: $com0comSetup"
