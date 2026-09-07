param(
    [switch]$Online
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$LockPath = Join-Path $InstallerRoot "dependency-lock.json"

if (-not (Test-Path $LockPath -PathType Leaf)) {
    throw "dependency-lock.json was not found: $LockPath"
}

$lock = Get-Content -LiteralPath $LockPath -Raw | ConvertFrom-Json
if ([int]$lock.format -ne 1) { throw "Unsupported dependency-lock format." }

function Assert-Artifact($artifact,[string]$label) {
    foreach ($field in @('version','filename','url','size','sha256')) {
        if (-not $artifact.$field) { throw "$label is missing required field '$field'." }
    }
    if ([string]$artifact.url -notmatch '^https://') { throw "$label URL must use HTTPS." }
    if ([string]$artifact.sha256 -notmatch '^[0-9a-fA-F]{64}$') { throw "$label SHA256 is invalid." }
    if ([int64]$artifact.size -le 0) { throw "$label size is invalid." }
}

$artifacts = New-Object System.Collections.Generic.List[object]
Assert-Artifact $lock.python 'Python'
$artifacts.Add([pscustomobject]@{ Label='Python'; Artifact=$lock.python }) | Out-Null

foreach ($pkg in @($lock.python_packages)) {
    if (-not $pkg.name) { throw "Python package entry is missing name." }
    Assert-Artifact $pkg ("Python package " + [string]$pkg.name)
    $artifacts.Add([pscustomobject]@{ Label=("Python package " + [string]$pkg.name); Artifact=$pkg }) | Out-Null
}

Write-Host ""
Write-Host "GADX Vector - D8D dependency lock verification" -ForegroundColor Cyan
Write-Host "Lock          : $LockPath"
Write-Host "Artifacts     : $($artifacts.Count) locked downloadable artifact(s)"
Write-Host "com0com pinned: $([bool]$lock.com0com.pinned_distribution)"
Write-Host "Mode          : $(if ($Online) { 'ONLINE HASH VERIFY' } else { 'STRUCTURE ONLY' })"
Write-Host ""

foreach ($entry in $artifacts) {
    $a = $entry.Artifact
    Write-Host ("{0}: {1}  sha256={2}" -f $entry.Label,[string]$a.filename,[string]$a.sha256)
}

if (-not $Online) {
    Write-Host ""
    Write-Host "DEPENDENCY_LOCK_STRUCTURE_OK" -ForegroundColor Green
    exit 0
}

$tempRoot = Join-Path $env:TEMP ("GADX-Vector-dependency-verify-" + [Guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

    foreach ($entry in $artifacts) {
        $a = $entry.Artifact
        $target = Join-Path $tempRoot ([string]$a.filename)
        Write-Host "Downloading $($entry.Label)..."
        Invoke-WebRequest -UseBasicParsing -Uri ([string]$a.url) -OutFile $target

        $file = Get-Item -LiteralPath $target
        if ([int64]$file.Length -ne [int64]$a.size) {
            throw "$($entry.Label) size mismatch. expected=$([int64]$a.size) actual=$([int64]$file.Length)"
        }

        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant()
        $expected = ([string]$a.sha256).ToLowerInvariant()
        if ($hash -ne $expected) {
            throw "$($entry.Label) SHA256 mismatch. expected=$expected actual=$hash"
        }
        Write-Host "  OK: size + SHA256"
    }

    Write-Host ""
    Write-Host "DEPENDENCY_LOCK_ONLINE_OK" -ForegroundColor Green
}
finally {
    if (Test-Path $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
