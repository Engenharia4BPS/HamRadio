param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$Repository = "Engenharia4BPS/HamRadio"
$DefaultRef = "main"
$LocalSourceLock = Join-Path $PSScriptRoot "source-lock.json"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this script from an elevated PowerShell prompt."
    }
}

function Get-ReleaseLabel([string]$InstallerPath) {
    $releasePath = Join-Path $InstallerPath "release.json"
    if (-not (Test-Path $releasePath -PathType Leaf)) { return "unversioned" }
    try {
        $release = Get-Content -LiteralPath $releasePath -Raw | ConvertFrom-Json
        $version = if ($release.version) { [string]$release.version } else { "unknown" }
        $channel = if ($release.channel) { [string]$release.channel } else { "unknown" }
        $phase = if ($release.phase) { [string]$release.phase } else { "" }
        $label = "$version / $channel"
        if ($phase) { $label += " / $phase" }
        return $label
    }
    catch { return "invalid release.json" }
}

function Get-PinnedSourceCommit {
    if (-not (Test-Path $LocalSourceLock -PathType Leaf)) { return $null }
    try {
        $lock = Get-Content -LiteralPath $LocalSourceLock -Raw | ConvertFrom-Json
        $sha = [string]$lock.source_commit
        if ($sha -match '^[0-9a-fA-F]{40}$') { return $sha.ToLowerInvariant() }
    }
    catch {}
    return $null
}

function Resolve-GitHubCommit([string]$Ref) {
    $uri = "https://api.github.com/repos/$Repository/commits/$Ref"
    $headers = @{ 'User-Agent' = 'GADX-Vector-Bootstrap' }
    $response = Invoke-RestMethod -UseBasicParsing -Uri $uri -Headers $headers
    $sha = [string]$response.sha
    if ($sha -notmatch '^[0-9a-fA-F]{40}$') {
        throw "GitHub did not return a valid commit SHA for ref '$Ref'."
    }
    return $sha.ToLowerInvariant()
}

function Write-SourceLock([string]$Path,[string]$RequestedRef,[string]$Commit,[string]$Resolution) {
    $lock = [ordered]@{
        format = 1
        repository = $Repository
        requested_ref = $RequestedRef
        source_commit = $Commit
        resolution = $Resolution
        resolved_utc = [DateTime]::UtcNow.ToString('o')
    }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path,($lock | ConvertTo-Json -Depth 4),$utf8)
}

Assert-Administrator

$pinnedCommit = Get-PinnedSourceCommit
if ($pinnedCommit) {
    $sourceCommit = $pinnedCommit
    $requestedRef = $DefaultRef
    $resolution = "package-lock"
}
else {
    $requestedRef = $DefaultRef
    $sourceCommit = Resolve-GitHubCommit $requestedRef
    $resolution = "resolved-ref"
}

$tempRoot = Join-Path $env:TEMP ("GADX-Vector-bootstrap-" + [Guid]::NewGuid().ToString("N"))
$zipPath = Join-Path $tempRoot "HamRadio-$sourceCommit.zip"
$extractRoot = Join-Path $tempRoot "src"
$targetInstaller = Join-Path $InstallRoot "installer"
$repoZipUrl = "https://github.com/$Repository/archive/$sourceCommit.zip"

Write-Host ""
Write-Host "GADX Vector - Installer bootstrap/update" -ForegroundColor Cyan
Write-Host "Install root : $InstallRoot"
Write-Host "Source       : $Repository @ $sourceCommit"
Write-Host "Resolution   : $resolution"
Write-Host "Mode         : $(if ($Apply) { 'APPLY' } else { 'PREVIEW' })"
Write-Host ""

try {
    New-Item -ItemType Directory -Force -Path $tempRoot,$extractRoot,$InstallRoot | Out-Null

    Write-Host "Downloading pinned installer package..."
    Invoke-WebRequest -UseBasicParsing -Uri $repoZipUrl -OutFile $zipPath

    Write-Host "Extracting installer package..."
    Expand-Archive -LiteralPath $zipPath -DestinationPath $extractRoot -Force

    $sourceInstaller = $null
    foreach ($candidate in @(Get-ChildItem -LiteralPath $extractRoot -Directory -ErrorAction SilentlyContinue)) {
        $expected = Join-Path $candidate.FullName "spikes\vector-hub-service\installer"
        if (Test-Path $expected -PathType Container) {
            $sourceInstaller = $expected
            break
        }
    }
    if (-not $sourceInstaller) {
        throw "Downloaded repository does not contain spikes\vector-hub-service\installer."
    }

    Write-Host "Refreshing C:\Ham\GADX-Vector\installer..."
    New-Item -ItemType Directory -Force -Path $targetInstaller | Out-Null
    Copy-Item -Path (Join-Path $sourceInstaller "*") -Destination $targetInstaller -Recurse -Force
    Write-SourceLock (Join-Path $targetInstaller "source-lock.json") $requestedRef $sourceCommit $resolution

    $setup = Join-Path $targetInstaller "setup-vector.ps1"
    if (-not (Test-Path $setup -PathType Leaf)) {
        throw "setup-vector.ps1 was not installed by the bootstrap."
    }

    Write-Host "Installer refresh: OK" -ForegroundColor Green
    Write-Host "Release      : $(Get-ReleaseLabel $targetInstaller)"
    Write-Host "Pinned commit: $sourceCommit"
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
