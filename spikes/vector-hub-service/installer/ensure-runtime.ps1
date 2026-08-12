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
    & $PythonExe -c "import tkinter, serial, win32serviceutil, servicemanager" *> $null
    return ($LASTEXITCODE -eq 0)
}

Assert-Administrator
$pythonInstaller = Find-BundledFile "python-installer.exe"
$com0comInstaller = Find-BundledFile "com0com-installer.exe"
$com0comSetup = Find-Com0comSetup
$runtimeOk = Test-Runtime

Write-Host ""
Write-Host "GADX Vector - Runtime/com0com ensure" -ForegroundColor Cyan
Write-Host "Install root : $InstallRoot"
Write-Host "Runtime      : $(if ($runtimeOk) { 'OK' } elseif (Test-Path $PythonExe) { 'INCOMPLETE' } else { 'MISSING' })"
Write-Host "com0com      : $(if ($com0comSetup) { $com0comSetup } else { 'not installed' })"
Write-Host "Python setup : $(if ($pythonInstaller) { $pythonInstaller } else { 'not bundled' })"
Write-Host "com0com setup: $(if ($com0comInstaller) { $com0comInstaller } else { 'not bundled' })"
Write-Host ""

if (-not $Apply) {
    Write-Host "PREVIEW ONLY - no changes were made." -ForegroundColor Yellow
    if (-not $runtimeOk) { Write-Host "  -> Private Python runtime will be installed/repaired with Tcl/Tk, pip, pyserial and pywin32." }
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
    if (-not $pythonInstaller) { throw "Private runtime is missing/incomplete and bundled python-installer.exe was not found." }
    New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
    Write-Host "Installing/repairing private Python runtime with Tcl/Tk..."
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
    if (-not (Test-Path $PythonExe -PathType Leaf)) { throw "Python installer finished but runtime\python.exe is missing." }

    Write-Host "Installing Python dependencies..."
    & $PythonExe -m pip install --disable-pip-version-check --upgrade "pyserial==3.5" "pywin32==312"
    if ($LASTEXITCODE -ne 0) { throw "Failed to install pyserial/pywin32." }

    $pythonService = Join-Path $RuntimeDir "pythonservice.exe"
    if (-not (Test-Path $pythonService -PathType Leaf)) {
        $postExe = Join-Path $RuntimeDir "Scripts\pywin32_postinstall.exe"
        $postPy = Join-Path $RuntimeDir "Scripts\pywin32_postinstall.py"
        if (Test-Path $postExe -PathType Leaf) { & $postExe -install }
        elseif (Test-Path $postPy -PathType Leaf) { & $PythonExe $postPy -install }
        if ($LASTEXITCODE -ne 0) { throw "pywin32 post-install failed." }
    }
}

if (-not (Test-Runtime)) { throw "Private runtime validation failed after install/repair." }

Write-Host ""
Write-Host "Runtime/com0com ensure completed successfully." -ForegroundColor Green
Write-Host "Python : $PythonExe"
Write-Host "com0com: $com0comSetup"
