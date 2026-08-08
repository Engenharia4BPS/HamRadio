param(
    [string]$InnoCompiler = "",
    [string]$PythonInstaller = "",
    [string]$Com0comDirectory = ""
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Payload = Join-Path $Root "payload"
$PythonPayload = Join-Path $Payload "python-installer.exe"
$Com0comPayload = Join-Path $Payload "com0com"
$Iss = Join-Path $Root "setup.iss"

function Resolve-Iscc([string]$Preferred) {
    if ($Preferred -and (Test-Path $Preferred)) { return (Resolve-Path $Preferred).Path }
    $candidates = @(
        "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) { return $candidate }
    }
    throw "Inno Setup 6 compiler (ISCC.exe) not found. Install Inno Setup 6 or pass -InnoCompiler."
}

New-Item -ItemType Directory -Force -Path $Payload | Out-Null

if ($PythonInstaller) {
    Copy-Item $PythonInstaller $PythonPayload -Force
}
if (-not (Test-Path $PythonPayload)) {
    throw "Missing payload\python-installer.exe. Supply the homologated official Python Windows installer using -PythonInstaller."
}

if ($Com0comDirectory) {
    if (Test-Path $Com0comPayload) { Remove-Item $Com0comPayload -Recurse -Force }
    Copy-Item $Com0comDirectory $Com0comPayload -Recurse -Force
}
if (-not (Test-Path (Join-Path $Com0comPayload "setupc.exe"))) {
    throw "Missing signed com0com payload. Copy the complete signed distribution to payload\com0com or pass -Com0comDirectory."
}

$iscc = Resolve-Iscc $InnoCompiler
Write-Host "Inno Setup: $iscc"
Write-Host "Python payload: $PythonPayload"
Write-Host "com0com payload: $Com0comPayload"

& $iscc $Iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed with exit code $LASTEXITCODE." }

$exe = Join-Path $Root "dist\GADX-Vector-Setup.exe"
if (-not (Test-Path $exe)) { throw "Build finished but installer was not found: $exe" }
Write-Host "Installer created: $exe" -ForegroundColor Green
