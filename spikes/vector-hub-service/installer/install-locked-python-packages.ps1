param(
    [Parameter(Mandatory=$true)]
    [string]$PythonExe,
    [string[]]$Package = @(),
    [string]$TargetDirectory = "",
    [switch]$ForceReinstall
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$LockPath = Join-Path $InstallerRoot "dependency-lock.json"
$CacheRoot = Join-Path $InstallerRoot "cache\locked-dependencies"

if (-not (Test-Path $PythonExe -PathType Leaf)) {
    throw "Python executable was not found: $PythonExe"
}
if (-not (Test-Path $LockPath -PathType Leaf)) {
    throw "dependency-lock.json was not found: $LockPath"
}

$lock = Get-Content -LiteralPath $LockPath -Raw | ConvertFrom-Json
if ([int]$lock.format -ne 1) { throw "Unsupported dependency-lock format." }

function Assert-LockedArtifact($artifact,[string]$label) {
    foreach ($field in @('name','version','filename','url','size','sha256')) {
        if (-not $artifact.$field) { throw "$label is missing required field '$field'." }
    }
    if ([string]$artifact.url -notmatch '^https://') { throw "$label URL must use HTTPS." }
    if ([string]$artifact.sha256 -notmatch '^[0-9a-fA-F]{64}$') { throw "$label SHA256 is invalid." }
    if ([int64]$artifact.size -le 0) { throw "$label size is invalid." }
}

function Test-ArtifactFile([string]$Path,$artifact,[string]$label) {
    if (-not (Test-Path $Path -PathType Leaf)) { return $false }
    $file = Get-Item -LiteralPath $Path
    if ([int64]$file.Length -ne [int64]$artifact.size) { return $false }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
    $expected = ([string]$artifact.sha256).ToLowerInvariant()
    return ($actual -eq $expected)
}

function Get-LockedArtifact($artifact,[string]$label) {
    New-Item -ItemType Directory -Force -Path $CacheRoot | Out-Null
    $target = Join-Path $CacheRoot ([string]$artifact.filename)

    if (Test-ArtifactFile $target $artifact $label) {
        Write-Host "$label cache: verified"
        return $target
    }

    if (Test-Path $target) {
        Write-Host "$label cache: invalid artifact removed" -ForegroundColor Yellow
        Remove-Item -LiteralPath $target -Force
    }

    Write-Host "Downloading locked $label..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -UseBasicParsing -Uri ([string]$artifact.url) -OutFile $target

    if (-not (Test-ArtifactFile $target $artifact $label)) {
        if (Test-Path $target) { Remove-Item -LiteralPath $target -Force -ErrorAction SilentlyContinue }
        throw "$label failed locked size/SHA256 validation after download."
    }

    Write-Host "$label download: verified size + SHA256"
    return $target
}

$selected = New-Object System.Collections.Generic.List[object]
$requested = @($Package | Where-Object { $_ })

foreach ($entry in @($lock.python_packages)) {
    $label = "Python package $([string]$entry.name)"
    Assert-LockedArtifact $entry $label
    if ($requested.Count -eq 0 -or $requested -contains [string]$entry.name) {
        $selected.Add($entry) | Out-Null
    }
}

if ($selected.Count -eq 0) {
    throw "No locked Python packages matched the request."
}

if ($requested.Count -gt 0) {
    foreach ($name in $requested) {
        if (-not (@($selected | ForEach-Object { [string]$_.name }) -contains $name)) {
            throw "Requested package is not present in dependency-lock.json: $name"
        }
    }
}

$wheelPaths = New-Object System.Collections.Generic.List[string]
foreach ($entry in $selected) {
    $wheelPaths.Add((Get-LockedArtifact $entry ("Python package " + [string]$entry.name))) | Out-Null
}

if ($TargetDirectory) {
    $TargetDirectory = [System.IO.Path]::GetFullPath($TargetDirectory)
    New-Item -ItemType Directory -Force -Path $TargetDirectory | Out-Null
}

$args = @('-m','pip','install','--disable-pip-version-check','--no-index','--no-deps')
if ($TargetDirectory) {
    $args += @('--target',$TargetDirectory)
}
else {
    $args += '--upgrade'
}
if ($ForceReinstall) { $args += '--force-reinstall' }
foreach ($wheel in $wheelPaths) { $args += $wheel }

Write-Host ""
Write-Host "Installing only verified locked wheel files..." -ForegroundColor Cyan
& $PythonExe @args
if ($LASTEXITCODE -ne 0) {
    throw "pip failed while installing verified locked Python packages."
}

Write-Host "LOCKED_PYTHON_PACKAGES_INSTALLED" -ForegroundColor Green
