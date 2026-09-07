param(
    [string]$PythonExe = "C:\Ham\GADX-Vector\runtime\python.exe"
)

$ErrorActionPreference = "Stop"
$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Installer = Join-Path $InstallerRoot "install-locked-python-packages.ps1"

if (-not (Test-Path $PythonExe -PathType Leaf)) {
    throw "Python executable was not found: $PythonExe"
}
if (-not (Test-Path $Installer -PathType Leaf)) {
    throw "Locked package installer was not found: $Installer"
}

$tempRoot = Join-Path $env:TEMP ("GADX-Vector-locked-install-test-" + [Guid]::NewGuid().ToString('N'))
$target = Join-Path $tempRoot "site-packages"
$oldTarget = $env:GADX_VECTOR_LOCKED_TEST_SITE

try {
    New-Item -ItemType Directory -Force -Path $target | Out-Null

    Write-Host ""
    Write-Host "GADX Vector - Locked Python install test" -ForegroundColor Cyan
    Write-Host "Python : $PythonExe"
    Write-Host "Target : $target"
    Write-Host "Mode   : isolated temporary target; runtime is not modified"
    Write-Host ""

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Installer -PythonExe $PythonExe -TargetDirectory $target
    if ($LASTEXITCODE -ne 0) { throw "Locked package installer test failed." }

    $env:GADX_VECTOR_LOCKED_TEST_SITE = $target
    $code = "import os,site; site.addsitedir(os.environ['GADX_VECTOR_LOCKED_TEST_SITE']); import serial,win32serviceutil,servicemanager,pythoncom,pywintypes; from importlib.metadata import version; assert version('pyserial') == '3.5'; assert version('pywin32') == '312'; print('LOCKED_PYTHON_IMPORTS_OK')"
    & $PythonExe -c $code
    if ($LASTEXITCODE -ne 0) { throw "Locked package import/version validation failed." }

    Write-Host "LOCKED_PYTHON_INSTALL_TEST_OK" -ForegroundColor Green
}
finally {
    $env:GADX_VECTOR_LOCKED_TEST_SITE = $oldTarget
    if (Test-Path $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
