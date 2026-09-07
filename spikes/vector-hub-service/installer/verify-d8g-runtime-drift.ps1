param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector"
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnsureRuntime = Join-Path $InstallerRoot "ensure-runtime.ps1"
$DetectScript = Join-Path $InstallerRoot "detect-installation.ps1"
$RealConfig = Join-Path $InstallRoot "config\vector.ini"
$TempRoot = Join-Path $env:TEMP ("GADX-Vector-d8g-runtime-drift-" + [Guid]::NewGuid().ToString('N'))

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this validation from an elevated PowerShell prompt."
    }
}

function Get-RealState {
    $json = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $DetectScript -InstallRoot $InstallRoot -AsJson
    if ($LASTEXITCODE -ne 0) { throw "Real installation detector failed." }
    return ($json | ConvertFrom-Json)
}

function Get-PyserialVersion([string]$PythonExe) {
    $value = & $PythonExe -c "from importlib.metadata import version; print(version('pyserial'))" 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $value) { return $null }
    return ([string]$value).Trim()
}

Assert-Administrator

foreach ($path in @($EnsureRuntime,$DetectScript)) {
    if (-not (Test-Path $path -PathType Leaf)) { throw "Required D8G component is missing: $path" }
}
if (-not (Test-Path $RealConfig -PathType Leaf)) { throw "Real vector.ini is missing: $RealConfig" }

$beforeState = Get-RealState
$beforeSvc = Get-Service -Name "GADXVectorHub" -ErrorAction SilentlyContinue
$beforeSvcStatus = if ($beforeSvc) { [string]$beforeSvc.Status } else { "not installed" }
$beforeConfigHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $RealConfig).Hash

Write-Host ""
Write-Host "GADX Vector - D8G runtime version-drift validation" -ForegroundColor Cyan
Write-Host "Real install : $InstallRoot"
Write-Host "Fixture      : $TempRoot"
Write-Host "Safety       : temporary runtime only; no real service/config/COM changes"
Write-Host ""

try {
    New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null

    Write-Host "[1/4] Creating a healthy locked runtime in the temporary fixture..."
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $EnsureRuntime -InstallRoot $TempRoot -Apply
    if ($LASTEXITCODE -ne 0) { throw "Initial temporary runtime creation failed with exit code $LASTEXITCODE." }

    $python = Join-Path $TempRoot "runtime\python.exe"
    if (-not (Test-Path $python -PathType Leaf)) { throw "Temporary runtime python.exe was not created." }
    $initialVersion = Get-PyserialVersion $python
    if ($initialVersion -ne '3.5') { throw "Initial temporary pyserial version is '$initialVersion', expected 3.5." }

    $sitePackages = Join-Path $TempRoot "runtime\Lib\site-packages"
    $distInfo = Get-ChildItem -LiteralPath $sitePackages -Directory -Filter "pyserial-*.dist-info" -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $distInfo) { throw "Temporary pyserial dist-info directory was not found." }
    $metadataPath = Join-Path $distInfo.FullName "METADATA"
    if (-not (Test-Path $metadataPath -PathType Leaf)) { throw "Temporary pyserial METADATA was not found." }

    Write-Host "[2/4] Introducing controlled pyserial version drift in the temporary fixture..."
    $metadata = Get-Content -LiteralPath $metadataPath -Raw
    $drifted = [regex]::Replace($metadata,'(?m)^Version:\s*3\.5\s*$','Version: 3.4',1)
    if ($drifted -eq $metadata) { throw "Could not introduce controlled pyserial metadata drift." }
    [System.IO.File]::WriteAllText($metadataPath,$drifted,(New-Object System.Text.UTF8Encoding($false)))

    $driftVersion = Get-PyserialVersion $python
    if ($driftVersion -ne '3.4') { throw "Controlled version drift was not visible; pyserial reports '$driftVersion'." }
    Write-Host "D8G_RUNTIME_DRIFT_INTRODUCED pyserial=$driftVersion" -ForegroundColor Yellow

    Write-Host ""
    Write-Host "[3/4] Running production ensure-runtime Preview against the drifted fixture..."
    $preview = @(& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $EnsureRuntime -InstallRoot $TempRoot 2>&1)
    $previewExit = $LASTEXITCODE
    $previewText = ($preview | Out-String).TrimEnd()
    Write-Host $previewText
    if ($previewExit -ne 0) { throw "Drift Preview failed with exit code $previewExit." }
    if ($previewText -match 'Runtime\s*:\s*OK - locked versions') {
        throw "Production Preview incorrectly accepted the drifted runtime as locked/healthy."
    }
    if ((Get-PyserialVersion $python) -ne '3.4') {
        throw "Preview modified the temporary runtime; Preview must be read-only."
    }
    Write-Host "D8G_RUNTIME_DRIFT_DETECTED" -ForegroundColor Green

    Write-Host ""
    Write-Host "[4/4] Applying production runtime repair only inside the temporary fixture..."
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $EnsureRuntime -InstallRoot $TempRoot -Apply
    if ($LASTEXITCODE -ne 0) { throw "Temporary drift repair failed with exit code $LASTEXITCODE." }

    $repairedVersion = Get-PyserialVersion $python
    if ($repairedVersion -ne '3.5') { throw "Repaired pyserial version is '$repairedVersion', expected 3.5." }
    & $python -c "import platform,tkinter,serial,win32serviceutil,servicemanager; from importlib.metadata import version; assert platform.python_version() == '3.10.11'; assert version('pyserial') == '3.5'; assert version('pywin32') == '312'"
    if ($LASTEXITCODE -ne 0) { throw "Repaired temporary runtime failed locked import/version validation." }
    foreach ($name in @('pythonservice.exe','pywintypes310.dll','pythoncom310.dll')) {
        if (-not (Test-Path (Join-Path $TempRoot "runtime\$name") -PathType Leaf)) {
            throw "Repaired temporary runtime is missing $name."
        }
    }
    Write-Host "D8G_RUNTIME_DRIFT_REPAIR_OK" -ForegroundColor Green

    $afterState = Get-RealState
    $afterSvc = Get-Service -Name "GADXVectorHub" -ErrorAction SilentlyContinue
    $afterSvcStatus = if ($afterSvc) { [string]$afterSvc.Status } else { "not installed" }
    $afterConfigHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $RealConfig).Hash

    if ([string]$beforeState.classification -ne [string]$afterState.classification) { throw "Real detector classification changed during fixture test." }
    if ([string]$beforeState.recommended_mode -ne [string]$afterState.recommended_mode) { throw "Real detector recommended mode changed during fixture test." }
    if ($beforeSvcStatus -ne $afterSvcStatus) { throw "Real GADXVectorHub service status changed during fixture test." }
    if ($beforeConfigHash -ne $afterConfigHash) { throw "Real vector.ini changed during fixture test." }

    Write-Host ""
    Write-Host "Real installation after runtime-drift fixture:" -ForegroundColor Cyan
    Write-Host "  Detected      : $([string]$afterState.classification)"
    Write-Host "  Recommended   : $([string]$afterState.recommended_mode)"
    Write-Host "  Service       : $afterSvcStatus"
    Write-Host "  vector.ini    : SHA256 unchanged"
    Write-Host ""
    Write-Host "D8G_RUNTIME_DRIFT_FIXTURE_SAFE" -ForegroundColor Green
}
finally {
    if (Test-Path $TempRoot) {
        Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
