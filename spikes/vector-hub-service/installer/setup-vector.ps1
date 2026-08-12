param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this script from an elevated PowerShell prompt."
    }
}

function Require-Script([string]$Name) {
    $path = Join-Path $InstallerRoot $Name
    if (-not (Test-Path $path -PathType Leaf)) { throw "Installer component is missing: $path" }
    return $path
}

function Invoke-Step([string]$Path,[string[]]$Arguments) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Path @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Installer step failed: $(Split-Path -Leaf $Path) (exit $LASTEXITCODE)" }
}

Assert-Administrator
$detect = Require-Script "detect-installation.ps1"
$runtime = Require-Script "ensure-runtime.ps1"
$planMigration = Require-Script "plan-migration.ps1"
$applyMigration = Require-Script "apply-migration.ps1"
$migrateService = Require-Script "migrate-service.ps1"

$json = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $detect -InstallRoot $InstallRoot -AsJson
if ($LASTEXITCODE -ne 0) { throw "Installation detector failed." }
$state = $json | ConvertFrom-Json

Write-Host ""
Write-Host "GADX Vector Setup - Phase D4 Orchestrator" -ForegroundColor Cyan
Write-Host "Install root : $InstallRoot"
Write-Host "Detected     : $($state.classification)"
Write-Host "Mode         : $($state.recommended_mode)"
Write-Host ""

switch ($state.recommended_mode) {
    "NONE" {
        Write-Host "Current installation is healthy. No repair or migration is required." -ForegroundColor Green
        exit 0
    }
    "INSTALL" {
        Write-Host "Clean installation detected." -ForegroundColor Yellow
        Write-Host "D4 will prepare runtime/com0com. Initial station configuration, Port Manager and reboot flow are completed in D5."
        if (-not $Apply) {
            Invoke-Step $runtime @('-InstallRoot',$InstallRoot)
            Write-Host ""
            Write-Host "PREVIEW complete. Use -Apply to prepare runtime/com0com." -ForegroundColor Yellow
            exit 0
        }
        Invoke-Step $runtime @('-InstallRoot',$InstallRoot,'-Apply')
        Write-Host ""
        Write-Host "Clean-install environment prepared. Continue with D5 Port Manager/configuration." -ForegroundColor Green
        exit 0
    }
    "MIGRATE" { }
    "MIGRATE_REPAIR" { }
    "REPAIR" { }
    default { throw "Unsupported detector mode: $($state.recommended_mode)" }
}

if (-not $Apply) {
    Write-Host "PREVIEW ONLY - orchestrator will not modify the machine." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Step 1 - runtime/com0com:"
    Invoke-Step $runtime @('-InstallRoot',$InstallRoot)

    if ($state.migration_required) {
        Write-Host ""
        Write-Host "Step 2 - legacy configuration migration:"
        Invoke-Step $planMigration @('-InstallRoot',$InstallRoot)
    }

    Write-Host ""
    Write-Host "Step 3 - payload/service transaction:"
    # migrate-service preview requires a current vector.ini. For a legacy install
    # that file only exists after D2 Apply, so show the planned action ourselves.
    if ($state.migration_required -and -not (Test-Path (Join-Path $InstallRoot 'config\vector.ini') -PathType Leaf)) {
        Write-Host "  After vector.ini migration, current payload will be deployed and GADXVectorHub will replace GADXVectorBridge transactionally."
    } else {
        Invoke-Step $migrateService @('-InstallRoot',$InstallRoot)
    }

    Write-Host ""
    Write-Host "PREVIEW complete. Re-run with -Apply to execute the detected plan." -ForegroundColor Yellow
    exit 0
}

Write-Host "Executing D4 plan..."
Write-Host ""
Write-Host "[1/3] Ensuring runtime and com0com..."
Invoke-Step $runtime @('-InstallRoot',$InstallRoot,'-Apply')

if ($state.migration_required) {
    Write-Host ""
    Write-Host "[2/3] Migrating legacy configuration with backup..."
    Invoke-Step $applyMigration @('-InstallRoot',$InstallRoot,'-Apply')
} else {
    Write-Host ""
    Write-Host "[2/3] No INI migration required; preserving current vector.ini."
}

Write-Host ""
Write-Host "[3/3] Deploying current payload and validating service transaction..."
Invoke-Step $migrateService @('-InstallRoot',$InstallRoot,'-Apply')

Write-Host ""
Write-Host "D4 completed successfully." -ForegroundColor Green
Write-Host "The machine is now on the current GADX Vector Hub generation."
Write-Host "Next: D5 opens Port Manager for review/configuration and handles reboot state."
