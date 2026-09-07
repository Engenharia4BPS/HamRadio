param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector",
    [switch]$Online
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$LockPath = Join-Path $InstallerRoot "dependency-lock.json"

if (-not (Test-Path $LockPath -PathType Leaf)) {
    throw "dependency-lock.json was not found: $LockPath"
}

$lock = Get-Content -LiteralPath $LockPath -Raw | ConvertFrom-Json
if ([int]$lock.format -ne 1) { throw "Unsupported dependency-lock format." }
$c = $lock.com0com
if (-not $c -or -not [bool]$c.pinned_distribution) {
    throw "com0com distribution is not pinned in dependency-lock.json."
}
foreach ($field in @('version','filename','url','size','sha256')) {
    if (-not $c.$field) { throw "com0com lock is missing required field '$field'." }
}
if ([string]$c.url -notmatch '^https://') { throw "com0com URL must use HTTPS." }
if ([string]$c.sha256 -notmatch '^[0-9a-fA-F]{64}$') { throw "com0com SHA256 is invalid." }
if ([int64]$c.size -le 0) { throw "com0com size is invalid." }

function Test-LockedFile([string]$Path,$Artifact) {
    if (-not (Test-Path $Path -PathType Leaf)) { return $false }
    $file = Get-Item -LiteralPath $Path
    if ([int64]$file.Length -ne [int64]$Artifact.size) { return $false }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
    $expected = ([string]$Artifact.sha256).ToLowerInvariant()
    return ($actual -eq $expected)
}

function Get-FileFingerprint([string]$Path) {
    if (-not (Test-Path $Path -PathType Leaf)) { return $null }
    $file = Get-Item -LiteralPath $Path
    return [pscustomobject]@{
        size = [int64]$file.Length
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
    }
}

function Find-Com0comSetup {
    foreach ($candidate in @(
        "C:\Ham\com0com\setupc.exe",
        "$env:ProgramFiles\com0com\setupc.exe",
        "${env:ProgramFiles(x86)}\com0com\setupc.exe"
    )) {
        if ($candidate -and (Test-Path $candidate -PathType Leaf)) {
            return (Resolve-Path $candidate).Path
        }
    }
    return $null
}

Write-Host ""
Write-Host "GADX Vector - com0com dependency-lock verification" -ForegroundColor Cyan
Write-Host "Version      : $([string]$c.version)"
Write-Host "Distribution : $([string]$c.filename)"
Write-Host "URL          : $([string]$c.url)"
Write-Host "SHA256       : $([string]$c.sha256)"
Write-Host "Mode         : $(if ($Online) { 'INSTALLED + ONLINE DISTRIBUTION' } else { 'INSTALLED FILES ONLY' })"
Write-Host ""

$setupc = Find-Com0comSetup
if (-not $setupc) {
    throw "Installed com0com setupc.exe was not found."
}
$installDir = Split-Path -Parent $setupc

foreach ($entry in @($c.installed_files)) {
    $path = Join-Path $installDir ([string]$entry.name)
    if (-not (Test-LockedFile $path $entry)) {
        throw "Installed com0com file does not match dependency lock: $path"
    }
    Write-Host "Installed $([string]$entry.name): OK"
}

Write-Host "COM0COM_INSTALLED_LOCK_OK" -ForegroundColor Green

if (-not $Online) {
    Write-Host "COM0COM_LOCK_STRUCTURE_OK" -ForegroundColor Green
    exit 0
}

$tempRoot = Join-Path $env:TEMP ("GADX-Vector-com0com-lock-" + [Guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
    $target = Join-Path $tempRoot ([string]$c.filename)
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

    Write-Host "Downloading locked com0com distribution..."
    $headers = @{ 'User-Agent' = 'GADX-Vector-Installer/0.8' }
    Invoke-WebRequest -UseBasicParsing -Uri ([string]$c.url) -Headers $headers -OutFile $target

    if (-not (Test-LockedFile $target $c)) {
        $actual = Get-FileFingerprint $target
        if ($actual) {
            Write-Host "Downloaded size   : $($actual.size)" -ForegroundColor Yellow
            Write-Host "Downloaded SHA256 : $($actual.sha256)" -ForegroundColor Yellow
            Write-Host "Expected size     : $([int64]$c.size)" -ForegroundColor Yellow
            Write-Host "Expected SHA256   : $([string]$c.sha256)" -ForegroundColor Yellow
        }
        throw "Downloaded com0com distribution failed size/SHA256 validation."
    }

    Write-Host "Downloaded distribution: OK size + SHA256"
    Write-Host "COM0COM_DISTRIBUTION_LOCK_OK" -ForegroundColor Green
    Write-Host "COM0COM_LOCK_ONLINE_OK" -ForegroundColor Green
}
finally {
    if (Test-Path $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
