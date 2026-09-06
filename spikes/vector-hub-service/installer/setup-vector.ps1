param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PayloadRoot = Join-Path $InstallerRoot "payload"
$ReleasePath = Join-Path $InstallerRoot "release.json"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this script from an elevated PowerShell prompt."
    }
}

function Get-ReleaseLabel {
    if (-not (Test-Path $ReleasePath -PathType Leaf)) { return "unversioned" }
    try {
        $release = Get-Content -LiteralPath $ReleasePath -Raw | ConvertFrom-Json
        $version = if ($release.version) { [string]$release.version } else { "unknown" }
        $channel = if ($release.channel) { [string]$release.channel } else { "unknown" }
        $phase = if ($release.phase) { [string]$release.phase } else { "" }
        return "$version / $channel$(if ($phase) { " / $phase" } else { "" })"
    }
    catch { return "invalid release.json" }
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

function Test-PayloadDrift {
    $pairs = @(
        @{ Installed = "app\vector_hub.py"; Payload = "app\vector_hub.py" },
        @{ Installed = "app\ts2000.py"; Payload = "app\ts2000.py" },
        @{ Installed = "service\vector_service.py"; Payload = "service\vector_service.py" },
        @{ Installed = "tools\port_manager.py"; Payload = "tools\port_manager.py" }
    )

    foreach ($pair in $pairs) {
        $installed = Join-Path $InstallRoot $pair.Installed
        $payload = Join-Path $PayloadRoot $pair.Payload
        if (-not (Test-Path $payload -PathType Leaf)) { continue }
        if (-not (Test-Path $installed -PathType Leaf)) { return $true }
        $installedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $installed).Hash
        $payloadHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $payload).Hash
        if ($installedHash -ne $payloadHash) { return $true }
    }
    return $false
}

function Wait-ServiceState([string]$Name,[string]$State,[int]$Seconds=12) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        $svc = Get-Service -Name $Name -ErrorAction SilentlyContinue
        if ($svc -and [string]$svc.Status -eq $State) { return $true }
        Start-Sleep -Milliseconds 300
    } while ((Get-Date) -lt $deadline)
    return $false
}

function Quiesce-CurrentHub {
    $svc = Get-Service -Name "GADXVectorHub" -ErrorAction SilentlyContinue
    if (-not $svc) { return }

    Write-Host "Safety: disabling GADXVectorHub before runtime/update work..." -ForegroundColor Yellow
    & sc.exe config GADXVectorHub start= disabled | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not temporarily disable GADXVectorHub before D7 repair." }

    try { Stop-Service -Name "GADXVectorHub" -Force -ErrorAction SilentlyContinue } catch {}
    if (-not (Wait-ServiceState "GADXVectorHub" "Stopped" 12)) {
        throw "Could not keep GADXVectorHub stopped before D7 repair. Update was aborted for radio safety."
    }
    Write-Host "Safety: GADXVectorHub is Disabled / Stopped." -ForegroundColor Green
}

Assert-Administrator
$detect = Require-Script "detect-installation.ps1"
$runtime = Require-Script "ensure-runtime.ps1"
$planMigration = Require-Script "plan-migration.ps1"
$applyMigration = Require-Script "apply-migration.ps1"
$migrateService = Require-Script "migrate-service.ps1"
$repairCurrent = Require-Script "repair-current.ps1"
$prepareClean = Require-Script "prepare-clean-install.ps1"

$json = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $detect -InstallRoot $InstallRoot -AsJson
if ($LASTEXITCODE -ne 0) { throw "Installation detector failed." }
$state = $json | ConvertFrom-Json
$payloadDrift = ($state.classification -eq "CURRENT" -and (Test-PayloadDrift))
if ($payloadDrift -and $state.recommended_mode -eq "NONE") {
    $state.recommended_mode = "REPAIR"
}
$currentRepair = ($state.classification -eq "CURRENT" -and $state.recommended_mode -eq "REPAIR")

Write-Host ""
Write-Host "GADX Vector Setup - D1-D7 Backend Orchestrator" -ForegroundColor Cyan
Write-Host "Release      : $(Get-ReleaseLabel)"
Write-Host "Install root : $InstallRoot"
Write-Host "Detected     : $($state.classification)"
Write-Host "Mode         : $($state.recommended_mode)"
if ($state.classification -eq "CURRENT") {
    Write-Host "Payload drift: $(if ($payloadDrift) { 'YES - installed files differ from current installer payload' } else { 'NO' })"
}
Write-Host ""

switch ($state.recommended_mode) {
    "NONE" {
        Write-Host "Current installation is healthy and matches the installer generation. No repair or migration is required." -ForegroundColor Green
        exit 0
    }
    "INSTALL" {
        Write-Host "Clean installation detected." -ForegroundColor Yellow
        if (-not $Apply) {
            Write-Host ""
            Write-Host "Step 1 - runtime/com0com:"
            Invoke-Step $runtime @('-InstallRoot',$InstallRoot)
            Write-Host ""
            Write-Host "Step 2 - clean station preparation:"
            Write-Host "  -> Deploy Vector Hub, TS-2000 adapter, Windows service code and Port Manager."
            Write-Host "  -> Create an initial vector.ini without overwriting an existing configuration."
            Write-Host "  -> Open Port Manager for operator review and COM-pair creation."
            Write-Host "  -> Mark reboot pending if virtual COM pairs change."
            Write-Host "  -> Do not start GADXVectorHub until [radio_keying] and [rig] are reviewed."
            Write-Host ""
            Write-Host "PREVIEW complete. Re-run with -Apply to execute the clean-install preparation." -ForegroundColor Yellow
            exit 0
        }

        Write-Host "[1/2] Ensuring runtime and com0com..."
        Invoke-Step $runtime @('-InstallRoot',$InstallRoot,'-Apply')
        Write-Host ""
        Write-Host "[2/2] Deploying current generation and opening Port Manager..."
        Invoke-Step $prepareClean @('-InstallRoot',$InstallRoot,'-Apply')
        Write-Host ""
        Write-Host "Clean-install preparation completed successfully." -ForegroundColor Green
        Write-Host "Next: review station-specific [radio_keying] and [rig], then run D6 commissioning."
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
    if ($currentRepair) {
        $previewSvc = Get-Service -Name "GADXVectorHub" -ErrorAction SilentlyContinue
        Write-Host "D7 safety gate:"
        Write-Host "  -> On Apply, GADXVectorHub will be set Disabled and forced Stopped BEFORE runtime/download/update work."
        Write-Host "  -> Current service status: $(if ($previewSvc) { [string]$previewSvc.Status } else { 'not installed' })"
        Write-Host ""
    }
    Write-Host "Step 1 - runtime/com0com:"
    Invoke-Step $runtime @('-InstallRoot',$InstallRoot)

    if ($currentRepair) {
        Write-Host ""
        Write-Host "Step 2 - D7 current installation repair/update:"
        Invoke-Step $repairCurrent @('-InstallRoot',$InstallRoot)
        Write-Host ""
        Write-Host "PREVIEW complete. Re-run with -Apply to execute the detected CURRENT/REPAIR plan." -ForegroundColor Yellow
        exit 0
    }

    if ($state.migration_required) {
        Write-Host ""
        Write-Host "Step 2 - legacy configuration migration:"
        Invoke-Step $planMigration @('-InstallRoot',$InstallRoot)
    }

    Write-Host ""
    Write-Host "Step 3 - payload/service transaction:"
    if ($state.migration_required -and -not (Test-Path (Join-Path $InstallRoot 'config\vector.ini') -PathType Leaf)) {
        Write-Host "  After vector.ini migration, current payload will be deployed and GADXVectorHub will replace GADXVectorBridge transactionally."
    } else {
        Invoke-Step $migrateService @('-InstallRoot',$InstallRoot)
    }

    Write-Host ""
    Write-Host "PREVIEW complete. Re-run with -Apply to execute the detected plan." -ForegroundColor Yellow
    exit 0
}

if ($currentRepair) {
    Write-Host "Executing D7 CURRENT/REPAIR plan..."
    Write-Host ""
    Write-Host "[0/2] Quiescing the currently installed Hub for radio safety..."
    Quiesce-CurrentHub
    Write-Host ""
    Write-Host "[1/2] Ensuring runtime and com0com..."
    Invoke-Step $runtime @('-InstallRoot',$InstallRoot,'-Apply')
    Write-Host ""
    Write-Host "[2/2] Backing up, updating and validating the current installation..."
    Invoke-Step $repairCurrent @('-InstallRoot',$InstallRoot,'-Apply')
    Write-Host ""
    Write-Host "D7 completed successfully." -ForegroundColor Green
    Write-Host "The current station configuration and virtual COM pairs were preserved."
    exit 0
}

Write-Host "Executing migration/repair plan..."
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
Write-Host "Migration/repair completed successfully." -ForegroundColor Green
Write-Host "The machine is now on the current GADX Vector Hub generation."
