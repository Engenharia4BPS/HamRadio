param(
    [string]$PackageRoot = ""
)

$ErrorActionPreference = "Stop"

if (-not $PackageRoot) {
    $PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
}
$PackageRoot = [System.IO.Path]::GetFullPath($PackageRoot)
$ManifestPath = Join-Path $PackageRoot "package-manifest.json"

if (-not (Test-Path $ManifestPath -PathType Leaf)) {
    throw "package-manifest.json was not found: $ManifestPath"
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
if (-not $manifest.files) { throw "Package manifest does not contain files." }

$failures = New-Object System.Collections.Generic.List[string]
$count = 0

foreach ($entry in $manifest.files) {
    $count++
    $relative = ([string]$entry.path).Replace('/','\')
    $path = Join-Path $PackageRoot $relative

    if (-not (Test-Path $path -PathType Leaf)) {
        $failures.Add("MISSING: $relative") | Out-Null
        continue
    }

    $file = Get-Item -LiteralPath $path
    if ([int64]$file.Length -ne [int64]$entry.size) {
        $failures.Add("SIZE: $relative expected=$([int64]$entry.size) actual=$([int64]$file.Length)") | Out-Null
        continue
    }

    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant()
    if ($hash -ne ([string]$entry.sha256).ToLowerInvariant()) {
        $failures.Add("SHA256: $relative") | Out-Null
    }
}

Write-Host ""
Write-Host "GADX Vector - Package verification" -ForegroundColor Cyan
Write-Host "Package root : $PackageRoot"
Write-Host "Release      : $([string]$manifest.version) / $([string]$manifest.channel) / $([string]$manifest.phase)"
Write-Host "Source commit: $([string]$manifest.source_commit)"
Write-Host "Files checked: $count"
Write-Host ""

if ($failures.Count -gt 0) {
    foreach ($failure in $failures) { Write-Host $failure -ForegroundColor Red }
    throw "PACKAGE_VERIFY_FAILED: $($failures.Count) file(s) failed integrity validation."
}

Write-Host "PACKAGE_VERIFY_OK" -ForegroundColor Green
