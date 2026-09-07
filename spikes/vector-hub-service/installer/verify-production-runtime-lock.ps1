param()

$ErrorActionPreference = "Stop"
$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnsureRuntime = Join-Path $InstallerRoot "ensure-runtime.ps1"
$TempRoot = Join-Path $env:TEMP ("GADX-Vector-production-runtime-test-" + [Guid]::NewGuid().ToString('N'))

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this validation from an elevated PowerShell prompt."
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

Assert-Administrator

if (-not (Test-Path $EnsureRuntime -PathType Leaf)) {
    throw "ensure-runtime.ps1 was not found: $EnsureRuntime"
}

$com0com = Find-Com0comSetup
if (-not $com0com) {
    throw "This isolated validation requires com0com to already be installed so the test cannot change system COM state."
}

Write-Host ""
Write-Host "GADX Vector - Production runtime dependency-lock validation" -ForegroundColor Cyan
Write-Host "Test root : $TempRoot"
Write-Host "com0com   : $com0com"
Write-Host "Safety    : temporary runtime only; no Vector service/config/COM changes"
Write-Host ""

try {
    New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null

    & $EnsureRuntime -InstallRoot $TempRoot -Apply

    $python = Join-Path $TempRoot "runtime\python.exe"
    if (-not (Test-Path $python -PathType Leaf)) {
        throw "Temporary runtime python.exe was not created."
    }

    & $python -c "import platform; from importlib.metadata import version; import tkinter,serial,win32serviceutil,servicemanager; assert platform.python_version() == '3.10.11'; assert version('pyserial') == '3.5'; assert version('pywin32') == '312'; print('PRODUCTION_RUNTIME_IMPORTS_OK')"
    if ($LASTEXITCODE -ne 0) { throw "Temporary production runtime import/version validation failed." }

    foreach ($name in @('pythonservice.exe','pywintypes310.dll','pythoncom310.dll')) {
        if (-not (Test-Path (Join-Path $TempRoot "runtime\$name") -PathType Leaf)) {
            throw "Temporary production runtime is missing $name."
        }
    }

    Write-Host "PRODUCTION_RUNTIME_SERVICE_HOST_OK" -ForegroundColor Green
    Write-Host "PRODUCTION_RUNTIME_LOCK_TEST_OK" -ForegroundColor Green
}
finally {
    if (Test-Path $TempRoot) {
        Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
