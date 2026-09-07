param(
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ReleasePath = Join-Path $InstallerRoot "release.json"
$SourceLockPath = Join-Path $InstallerRoot "source-lock.json"

if (-not (Test-Path $ReleasePath -PathType Leaf)) {
    throw "release.json was not found: $ReleasePath"
}

$release = Get-Content -LiteralPath $ReleasePath -Raw | ConvertFrom-Json
if (-not $release.version) { throw "release.json does not contain version." }
if (-not $release.product) { throw "release.json does not contain product." }

$version = [string]$release.version
$packageName = "GADX-Vector-$version"

if (-not $OutputDir) {
    $OutputDir = Join-Path (Split-Path -Parent $InstallerRoot) "dist"
}
$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)

function Find-GitRoot([string]$StartPath) {
    $current = [System.IO.DirectoryInfo]$StartPath
    while ($current) {
        if (Test-Path (Join-Path $current.FullName ".git")) { return $current.FullName }
        $current = $current.Parent
    }
    return $null
}

function Write-Utf8NoBom([string]$Path,[string]$Text) {
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path,$Text,$utf8)
}

$sourceCommit = $null
$sourceResolution = $null
if (Test-Path $SourceLockPath -PathType Leaf) {
    try {
        $sourceLock = Get-Content -LiteralPath $SourceLockPath -Raw | ConvertFrom-Json
        $candidate = [string]$sourceLock.source_commit
        if ($candidate -match '^[0-9a-fA-F]{40}$') {
            $sourceCommit = $candidate.ToLowerInvariant()
            $sourceResolution = "source-lock"
        }
    }
    catch {}
}

if (-not $sourceCommit) {
    $gitRoot = Find-GitRoot $InstallerRoot
    if ($gitRoot) {
        try {
            $candidate = (& git -C $gitRoot rev-parse HEAD 2>$null | Select-Object -First 1).Trim()
            if ($candidate -match '^[0-9a-fA-F]{40}$') {
                $sourceCommit = $candidate.ToLowerInvariant()
                $sourceResolution = "git-head"
            }
        }
        catch {}
    }
}

if (-not $sourceCommit) {
    throw "Cannot determine immutable source commit. Refresh this installer with bootstrap-vector.ps1 or build from a Git checkout before creating a release package."
}

$tempRoot = Join-Path $env:TEMP ("GADX-Vector-package-" + [Guid]::NewGuid().ToString("N"))
$stageRoot = Join-Path $tempRoot $packageName
$zipPath = Join-Path $OutputDir ($packageName + ".zip")
$shaPath = $zipPath + ".sha256"

Write-Host ""
Write-Host "GADX Vector - D8D release package builder" -ForegroundColor Cyan
Write-Host "Release      : $version / $([string]$release.channel) / $([string]$release.phase)"
Write-Host "Source commit: $sourceCommit"
Write-Host "Resolution   : $sourceResolution"
Write-Host "Output       : $zipPath"
Write-Host ""

try {
    New-Item -ItemType Directory -Force -Path $stageRoot,$OutputDir | Out-Null

    Write-Host "Staging installer tree..."
    Copy-Item -Path (Join-Path $InstallerRoot "*") -Destination $stageRoot -Recurse -Force

    foreach ($relative in @(
        "cache",
        "D8C-Repair-Simulation.cmd",
        "setup-repair-simulation.ps1"
    )) {
        $path = Join-Path $stageRoot $relative
        if (Test-Path $path) { Remove-Item -LiteralPath $path -Recurse -Force }
    }

    $stageLock = [ordered]@{
        format = 1
        repository = [string]$release.repository
        requested_ref = "release-package"
        source_commit = $sourceCommit
        resolution = "immutable-package-lock"
        resolved_utc = [DateTime]::UtcNow.ToString('o')
    }
    Write-Utf8NoBom (Join-Path $stageRoot "source-lock.json") ($stageLock | ConvertTo-Json -Depth 4)

    $manifestPath = Join-Path $stageRoot "package-manifest.json"
    if (Test-Path $manifestPath) { Remove-Item -LiteralPath $manifestPath -Force }

    $packageReadme = @"
GADX Vector $version

This is a D8D development distribution package.

Quick start
-----------
1. Extract the ZIP to a normal local folder.
2. Double-click GADX-Vector-Setup.cmd.
3. Review the detected state.
4. Run Preview before any Apply operation.
5. Apply only after reviewing the safety plan.

Default install root
--------------------
C:\Ham\GADX-Vector

Safety
------
Repair and migration reuse the validated D1-D7 backend. The backend preserves vector.ini and existing com0com pairs where applicable, uses backup/rollback, and requires the Hub and radio to reach a safe state before READY.

Package verification
--------------------
Run:

powershell -NoProfile -ExecutionPolicy Bypass -File .\verify-package.ps1

Expected result:
PACKAGE_VERIFY_OK

Immutable source
----------------
This package is pinned to the exact Git commit below. bootstrap-vector.ps1 will use source-lock.json from the package and download that exact commit instead of following the moving main branch.

Release metadata
----------------
Product : $([string]$release.product)
Version : $version
Phase   : $([string]$release.phase)
Channel : $([string]$release.channel)
Baseline: $([string]$release.baseline)
Source  : $sourceCommit
"@
    Write-Utf8NoBom (Join-Path $stageRoot "PACKAGE-README.txt") $packageReadme

    $files = @()
    foreach ($file in @(Get-ChildItem -LiteralPath $stageRoot -Recurse -File | Sort-Object FullName)) {
        $relative = $file.FullName.Substring($stageRoot.Length).TrimStart('\')
        if ($relative -ieq "package-manifest.json") { continue }
        $files += [pscustomobject]@{
            path = ($relative -replace '\\','/')
            size = [int64]$file.Length
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant()
        }
    }

    $manifest = [ordered]@{
        format = 1
        product = [string]$release.product
        version = $version
        phase = [string]$release.phase
        channel = [string]$release.channel
        baseline = [string]$release.baseline
        repository = [string]$release.repository
        repository_path = [string]$release.path
        source_commit = $sourceCommit
        source_resolution = $sourceResolution
        files = $files
    }
    Write-Utf8NoBom $manifestPath ($manifest | ConvertTo-Json -Depth 8)

    Write-Host "Package files : $($files.Count + 1)"
    Write-Host "Writing package manifest..."

    if (Test-Path $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
    if (Test-Path $shaPath) { Remove-Item -LiteralPath $shaPath -Force }

    Write-Host "Creating ZIP..."
    Compress-Archive -LiteralPath $stageRoot -DestinationPath $zipPath -CompressionLevel Optimal -Force

    $zipHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath).Hash.ToLowerInvariant()
    Write-Utf8NoBom $shaPath ($zipHash + "  " + [System.IO.Path]::GetFileName($zipPath) + "`r`n")

    Write-Host ""
    Write-Host "D8D package created successfully." -ForegroundColor Green
    Write-Host "ZIP           : $zipPath"
    Write-Host "ZIP SHA256    : $zipHash"
    Write-Host "SHA256 file   : $shaPath"
    Write-Host "Pinned commit : $sourceCommit"
}
finally {
    if (Test-Path $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
