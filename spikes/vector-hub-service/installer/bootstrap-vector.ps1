param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this script from an elevated PowerShell prompt."
    }
}

Assert-Administrator

$repoZipUrl = "https://github.com/Engenharia4BPS/HamRadio/archive/refs/heads/main.zip"
$tempRoot = Join-Path $env:TEMP ("GADX-Vector-bootstrap-" + [Guid]::NewGuid().ToString("N"))
$zipPath = Join-Path $tempRoot "HamRadio-main.zip"
$extractRoot = Join-Path $tempRoot "src"
$sourceInstaller = Join-Path $extractRoot "HamRadio-main\spikes\vector-hub-service\installer"
$targetInstaller = Join-Path $InstallRoot "installer"

Write-Host ""
Write-Host "GADX Vector - Installer bootstrap/update" -ForegroundColor Cyan
Write-Host "Install root : $InstallRoot"
Write-Host "Source       : Engenharia4BPS/HamRadio main"
Write-Host "Mode         : $(if ($Apply) { 'APPLY' } else { 'PREVIEW' })"
Write-Host ""

try {
    New-Item -ItemType Directory -Force -Path $tempRoot,$extractRoot,$InstallRoot | Out-Null

    Write-Host "Downloading current installer package..."
    Invoke-WebRequest -UseBasicParsing -Uri $repoZipUrl -OutFile $zipPath

    Write-Host "Extracting installer package..."
    Expand-Archive -LiteralPath $zipPath -DestinationPath $extractRoot -Force

    if (-not (Test-Path $sourceInstaller -PathType Container)) {
        throw "Downloaded repository does not contain the expected installer path: $sourceInstaller"
    }

    Write-Host "Refreshing C:\Ham\GADX-Vector\installer..."
    New-Item -ItemType Directory -Force -Path $targetInstaller | Out-Null
    Copy-Item -Path (Join-Path $sourceInstaller "*") -Destination $targetInstaller -Recurse -Force

    $setup = Join-Path $targetInstaller "setup-vector.ps1"
    if (-not (Test-Path $setup -PathType Leaf)) {
        throw "setup-vector.ps1 was not installed by the bootstrap."
    }

    Write-Host "Installer refresh: OK" -ForegroundColor Green
    Write-Host ""

    $args = @('-NoProfile','-ExecutionPolicy','Bypass','-File',$setup,'-InstallRoot',$InstallRoot)
    if ($Apply) { $args += '-Apply' }

    Write-Host "Launching setup-vector.ps1..."
    & powershell.exe @args
    if ($LASTEXITCODE -ne 0) {
        throw "setup-vector.ps1 failed with exit code $LASTEXITCODE."
    }
}
finally {
    if (Test-Path $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
