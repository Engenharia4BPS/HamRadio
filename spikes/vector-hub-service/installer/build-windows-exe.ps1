param(
    [string]$OutputDir = "",
    [string]$IsccPath = ""
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ReleasePath = Join-Path $InstallerRoot "release.json"
$PackageBuilder = Join-Path $InstallerRoot "build-release-package.ps1"
$IssPath = Join-Path $InstallerRoot "windows-exe\GADX-Vector-Setup.iss"

foreach ($required in @($ReleasePath,$PackageBuilder,$IssPath)) {
    if (-not (Test-Path $required -PathType Leaf)) {
        throw "Required EXE build component is missing: $required"
    }
}

$release = Get-Content -LiteralPath $ReleasePath -Raw | ConvertFrom-Json
if (-not $release.version) { throw "release.json does not contain version." }
$version = [string]$release.version
$packageName = "GADX-Vector-$version"

if (-not $OutputDir) {
    $OutputDir = Join-Path (Split-Path -Parent $InstallerRoot) "dist"
}
$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
$ExeOutputDir = Join-Path $OutputDir "exe"

function Find-Iscc {
    if ($IsccPath) {
        if (-not (Test-Path $IsccPath -PathType Leaf)) {
            throw "ISCC.exe was not found at the requested path: $IsccPath"
        }
        return (Resolve-Path $IsccPath).Path
    }

    try {
        $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    catch {}

    foreach ($candidate in @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    )) {
        if ($candidate -and (Test-Path $candidate -PathType Leaf)) {
            return (Resolve-Path $candidate).Path
        }
    }

    throw "Inno Setup 6 compiler (ISCC.exe) was not found. Install Inno Setup 6 or pass -IsccPath."
}

$iscc = Find-Iscc
New-Item -ItemType Directory -Force -Path $OutputDir,$ExeOutputDir | Out-Null

Write-Host ""
Write-Host "GADX Vector - Windows EXE builder" -ForegroundColor Cyan
Write-Host "Release      : $version / $([string]$release.channel) / $([string]$release.phase)"
Write-Host "Inno compiler: $iscc"
Write-Host "Output       : $ExeOutputDir"
Write-Host ""

Write-Host "[1/3] Building immutable release package..."
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $PackageBuilder -OutputDir $OutputDir
if ($LASTEXITCODE -ne 0) { throw "build-release-package.ps1 failed with exit code $LASTEXITCODE." }

$zipPath = Join-Path $OutputDir ($packageName + ".zip")
if (-not (Test-Path $zipPath -PathType Leaf)) {
    throw "Expected release ZIP was not created: $zipPath"
}

$tempRoot = Join-Path $env:TEMP ("GADX-Vector-exe-" + [Guid]::NewGuid().ToString("N"))
try {
    Write-Host "[2/3] Expanding immutable package for Inno Setup..."
    New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
    Expand-Archive -LiteralPath $zipPath -DestinationPath $tempRoot -Force
    $packageRoot = Join-Path $tempRoot $packageName
    if (-not (Test-Path $packageRoot -PathType Container)) {
        throw "Expanded package root was not found: $packageRoot"
    }

    Write-Host "[3/3] Compiling Windows installer EXE..."
    $args = @(
        "/DAppVersion=$version",
        "/DPackageRoot=$packageRoot",
        "/DOutputDir=$ExeOutputDir",
        $IssPath
    )
    & $iscc @args
    if ($LASTEXITCODE -ne 0) { throw "ISCC.exe failed with exit code $LASTEXITCODE." }

    $exePath = Join-Path $ExeOutputDir ("GADX-Vector-Setup-$version.exe")
    if (-not (Test-Path $exePath -PathType Leaf)) {
        throw "Expected installer EXE was not created: $exePath"
    }

    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $exePath).Hash.ToLowerInvariant()
    $shaPath = $exePath + ".sha256"
    Set-Content -LiteralPath $shaPath -Value ($hash + "  " + [System.IO.Path]::GetFileName($exePath)) -Encoding ASCII

    Write-Host ""
    Write-Host "WINDOWS_EXE_BUILD_OK" -ForegroundColor Green
    Write-Host "EXE        : $exePath"
    Write-Host "SHA256     : $hash"
    Write-Host "SHA256 file: $shaPath"
}
finally {
    if (Test-Path $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
