param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector"
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SetupScript = Join-Path $InstallerRoot "setup-vector.ps1"
$PayloadHub = Join-Path $InstallerRoot "payload\app\vector_hub.py"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this script from an elevated PowerShell prompt."
    }
}

function Get-RealState {
    $raw = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $SetupScript -InstallRoot $InstallRoot -AsJson 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Could not read real installation state." }
    return (($raw | Out-String).Trim() | ConvertFrom-Json)
}

Assert-Administrator

foreach ($path in @($SetupScript,$PayloadHub)) {
    if (-not (Test-Path $path -PathType Leaf)) { throw "Required test component is missing: $path" }
}

$before = Get-RealState
$beforeService = Get-Service -Name "GADXVectorHub" -ErrorAction SilentlyContinue
$beforeServiceStatus = if ($beforeService) { [string]$beforeService.Status } else { "not installed" }
$beforeConfigHash = $null
$realConfig = Join-Path $InstallRoot "config\vector.ini"
if (Test-Path $realConfig -PathType Leaf) {
    $beforeConfigHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $realConfig).Hash
}

$tempRoot = Join-Path $env:TEMP ("GADX-Vector-d8g-broken-" + [Guid]::NewGuid().ToString("N"))
$tempApp = Join-Path $tempRoot "app"

Write-Host ""
Write-Host "GADX Vector - D8G broken/incomplete Preview validation" -ForegroundColor Cyan
Write-Host "Real install : $InstallRoot"
Write-Host "Fixture      : $tempRoot"
Write-Host "Safety       : temporary fixture + Preview only; real service/config/COMs are not modified"
Write-Host ""

try {
    New-Item -ItemType Directory -Force -Path $tempApp | Out-Null
    Copy-Item -LiteralPath $PayloadHub -Destination (Join-Path $tempApp "vector_hub.py") -Force

    Write-Host "Fixture contains only app\vector_hub.py; service/config/tools/runtime are intentionally absent."
    Write-Host "Running production setup-vector.ps1 in Preview mode against fixture..."
    Write-Host ""

    $output = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $SetupScript -InstallRoot $tempRoot 2>&1
    $exitCode = $LASTEXITCODE
    $text = ($output | Out-String).TrimEnd()
    Write-Host $text

    if ($exitCode -ne 0) { throw "Broken fixture Preview failed with exit code $exitCode." }
    if ($text -notmatch '(?m)^Detected\s+:\s+BROKEN\s*$') { throw "Fixture was not detected as BROKEN." }
    if ($text -notmatch '(?m)^Mode\s+:\s+REPAIR\s*$') { throw "Fixture did not recommend REPAIR." }
    if ($text -notmatch 'PREVIEW ONLY') { throw "Preview safety marker was not found." }
    if ($text -notmatch 'Config\s+:\s+MISSING') { throw "Repair Preview did not expose the intentionally missing vector.ini." }

    $after = Get-RealState
    $afterService = Get-Service -Name "GADXVectorHub" -ErrorAction SilentlyContinue
    $afterServiceStatus = if ($afterService) { [string]$afterService.Status } else { "not installed" }
    $afterConfigHash = $null
    if (Test-Path $realConfig -PathType Leaf) {
        $afterConfigHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $realConfig).Hash
    }

    $realStateOk = (
        [string]$before.classification -eq [string]$after.classification -and
        [string]$before.recommended_mode -eq [string]$after.recommended_mode -and
        [bool]$before.payload_drift -eq [bool]$after.payload_drift
    )
    $serviceOk = ($beforeServiceStatus -eq $afterServiceStatus)
    $configOk = ($beforeConfigHash -eq $afterConfigHash)

    Write-Host ""
    Write-Host "Real installation after fixture Preview:" -ForegroundColor Cyan
    Write-Host "  Detected      : $([string]$after.classification)"
    Write-Host "  Recommended   : $([string]$after.recommended_mode)"
    Write-Host "  Payload drift : $(if ([bool]$after.payload_drift) { 'YES' } else { 'NO' })"
    Write-Host "  Service       : $afterServiceStatus"
    Write-Host "  vector.ini    : $(if ($configOk) { 'SHA256 unchanged' } else { 'CHANGED' })"

    if (-not $realStateOk) { throw "Real installation detector state changed during isolated Preview test." }
    if (-not $serviceOk) { throw "Real GADXVectorHub service status changed during isolated Preview test." }
    if (-not $configOk) { throw "Real vector.ini changed during isolated Preview test." }

    Write-Host ""
    Write-Host "D8G_BROKEN_FIXTURE_DETECTED" -ForegroundColor Green
    Write-Host "D8G_BROKEN_PREVIEW_SAFE" -ForegroundColor Green
}
finally {
    if (Test-Path $tempRoot -PathType Container) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
