param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector",
    [switch]$AsJson
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)

function Test-File([string]$RelativePath) {
    return Test-Path (Join-Path $InstallRoot $RelativePath) -PathType Leaf
}

function Get-ServiceState([string]$Name) {
    $svc = Get-Service -Name $Name -ErrorAction SilentlyContinue
    if (-not $svc) {
        return [ordered]@{ exists = $false; status = $null }
    }
    return [ordered]@{ exists = $true; status = [string]$svc.Status }
}

function Find-Com0comSetup {
    $candidates = @(
        "C:\Ham\com0com\setupc.exe",
        "$env:ProgramFiles\com0com\setupc.exe",
        "${env:ProgramFiles(x86)}\com0com\setupc.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate -PathType Leaf)) {
            return (Resolve-Path $candidate).Path
        }
    }
    return $null
}

function Test-PythonImport([string]$PythonExe, [string]$Module) {
    if (-not (Test-Path $PythonExe -PathType Leaf)) { return $false }
    & $PythonExe -c "import $Module" 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

$currentFiles = [ordered]@{
    vector_hub       = Test-File "app\vector_hub.py"
    vector_service   = Test-File "service\vector_service.py"
    vector_ini       = Test-File "config\vector.ini"
    port_manager     = Test-File "tools\port_manager.py"
}

$legacyFiles = [ordered]@{
    rigctld_bridge        = Test-File "app\rigctld_bridge.py"
    rigctld_bridge_multi  = Test-File "app\rigctld_bridge_multi.py"
    vector_bridge_service = Test-File "service\vector_bridge_service.py"
    bridge_ini            = Test-File "config\bridge.ini"
    bridge_multi_ini      = Test-File "config\bridge_multi.ini"
    logger_ini            = Test-File "config\logger.ini"
}

$runtimePython = Join-Path $InstallRoot "runtime\python.exe"
$runtime = [ordered]@{
    python_exe = Test-Path $runtimePython -PathType Leaf
    tkinter    = $false
    pyserial   = $false
    pywin32    = $false
}
if ($runtime.python_exe) {
    $runtime.tkinter  = Test-PythonImport $runtimePython "tkinter"
    $runtime.pyserial = Test-PythonImport $runtimePython "serial"
    $runtime.pywin32  = Test-PythonImport $runtimePython "win32serviceutil"
}

$currentService = Get-ServiceState "GADXVectorHub"
$legacyService  = Get-ServiceState "GADXVectorBridge"
$com0comSetup = Find-Com0comSetup

$currentCount = @($currentFiles.Values | Where-Object { $_ }).Count
$legacyCount  = @($legacyFiles.Values | Where-Object { $_ }).Count
$rootExists   = Test-Path $InstallRoot -PathType Container
$hasAnyKnownArtifact = ($currentCount -gt 0 -or $legacyCount -gt 0 -or $runtime.python_exe -or $currentService.exists -or $legacyService.exists)

$requiredCurrent = @(
    $currentFiles.vector_hub,
    $currentFiles.vector_service,
    $currentFiles.vector_ini,
    $currentFiles.port_manager
)
$currentComplete = (@($requiredCurrent | Where-Object { -not $_ }).Count -eq 0)

$issues = New-Object System.Collections.Generic.List[string]
$evidence = New-Object System.Collections.Generic.List[string]
$actions = New-Object System.Collections.Generic.List[string]

if ($currentFiles.vector_hub)     { $evidence.Add("current: app\vector_hub.py") }
if ($currentFiles.vector_service) { $evidence.Add("current: service\vector_service.py") }
if ($currentFiles.vector_ini)     { $evidence.Add("current: config\vector.ini") }
if ($currentFiles.port_manager)   { $evidence.Add("current: tools\port_manager.py") }
foreach ($entry in $legacyFiles.GetEnumerator()) {
    if ($entry.Value) { $evidence.Add("legacy: $($entry.Key)") }
}
if ($currentService.exists) { $evidence.Add("service: GADXVectorHub ($($currentService.status))") }
if ($legacyService.exists)  { $evidence.Add("service: GADXVectorBridge ($($legacyService.status))") }
if ($runtime.python_exe)    { $evidence.Add("runtime: python.exe") }
if ($com0comSetup)          { $evidence.Add("com0com: $com0comSetup") }

$classification = "CLEAN"
$migrationRequired = $false
$repairRequired = $false

if (-not $rootExists -or -not $hasAnyKnownArtifact) {
    $classification = "CLEAN"
    $actions.Add("Perform a clean installation.")
}
elseif ($currentComplete -and $legacyCount -eq 0) {
    # A complete current installation wins over a stale legacy service entry.
    # This is a repair/cleanup scenario, not a migration scenario.
    $classification = "CURRENT"

    if ($legacyService.exists) {
        $repairRequired = $true
        $issues.Add("Stale legacy service GADXVectorBridge is still installed ($($legacyService.status)).")
        $actions.Add("Remove the stale GADXVectorBridge service after confirming GADXVectorHub is healthy.")
    }
}
elseif ($currentCount -gt 0 -and $legacyCount -gt 0) {
    $classification = "BROKEN"
    $migrationRequired = $true
    $repairRequired = $true
    $issues.Add("Current and legacy installation files coexist in the installation root.")
    $actions.Add("Back up legacy configuration before changing files.")
    $actions.Add("Migrate legacy INI values into config\vector.ini only where the current configuration does not already supersede them.")
    $actions.Add("Preserve existing com0com pairs whenever possible.")
    $actions.Add("Remove GADXVectorBridge only after GADXVectorHub is ready.")
}
elseif ($legacyCount -gt 0) {
    $classification = "LEGACY"
    $migrationRequired = $true
    $actions.Add("Back up bridge.ini / bridge_multi.ini / logger.ini into config\legacy.")
    $actions.Add("Preserve existing com0com pairs whenever possible.")
    $actions.Add("Generate config\vector.ini from legacy configuration.")
    $actions.Add("Replace GADXVectorBridge with GADXVectorHub.")
}
elseif ($currentCount -gt 0) {
    $classification = "BROKEN"
    $repairRequired = $true
    if (-not $currentFiles.vector_hub)     { $issues.Add("Missing app\vector_hub.py") }
    if (-not $currentFiles.vector_service) { $issues.Add("Missing service\vector_service.py") }
    if (-not $currentFiles.vector_ini)     { $issues.Add("Missing config\vector.ini") }
    if (-not $currentFiles.port_manager)   { $issues.Add("Missing tools\port_manager.py") }
    $actions.Add("Repair current installation files before starting the service.")

    if ($legacyService.exists) {
        $issues.Add("Legacy service GADXVectorBridge is installed, but no legacy configuration files were found.")
        $actions.Add("Treat GADXVectorBridge as stale service metadata; do not attempt INI migration without legacy files.")
    }
}
elseif ($legacyService.exists) {
    # Service metadata alone is insufficient evidence to call the machine LEGACY.
    $classification = "BROKEN"
    $repairRequired = $true
    $issues.Add("Only the legacy GADXVectorBridge service was found; legacy installation files are missing.")
    $actions.Add("Remove stale legacy service metadata and perform a repair/clean install as appropriate.")
}
else {
    $classification = "BROKEN"
    $repairRequired = $true
    $actions.Add("Repair incomplete GADX Vector installation.")
}

if ($classification -ne "CLEAN") {
    if (-not $runtime.python_exe) {
        $issues.Add("Private runtime\python.exe is missing.")
        $repairRequired = $true
        $actions.Add("Install the private Python runtime.")
    }
    else {
        if (-not $runtime.tkinter) {
            $issues.Add("Private Python runtime is missing Tcl/Tk (tkinter).")
            $repairRequired = $true
            $actions.Add("Repair Python with Include_tcltk=1.")
        }
        if (-not $runtime.pyserial) {
            $issues.Add("Private Python runtime is missing pyserial.")
            $repairRequired = $true
            $actions.Add("Install pyserial==3.5 into the private runtime.")
        }
        if (-not $runtime.pywin32) {
            $issues.Add("Private Python runtime is missing pywin32.")
            $repairRequired = $true
            $actions.Add("Install/repair pywin32==312 in the private runtime.")
        }
    }

    if (-not $com0comSetup) {
        $issues.Add("com0com setupc.exe was not found.")
        $repairRequired = $true
        $actions.Add("Install or repair com0com before provisioning virtual ports.")
    }

    if ($classification -eq "CURRENT" -and -not $currentService.exists) {
        $issues.Add("Current files exist but GADXVectorHub service is not installed.")
        $repairRequired = $true
        $actions.Add("Install GADXVectorHub Windows service.")
    }
}

$recommendedMode = switch ($classification) {
    "CLEAN"   { "INSTALL" }
    "LEGACY"  { "MIGRATE" }
    "BROKEN"  { if ($migrationRequired) { "MIGRATE_REPAIR" } else { "REPAIR" } }
    "CURRENT" { if ($repairRequired) { "REPAIR" } else { "NONE" } }
    default    { "REPAIR" }
}

$result = [ordered]@{
    schema_version = 2
    install_root = $InstallRoot
    classification = $classification
    recommended_mode = $recommendedMode
    migration_required = $migrationRequired
    repair_required = $repairRequired
    current_complete = $currentComplete
    current_files = $currentFiles
    legacy_files = $legacyFiles
    runtime = $runtime
    services = [ordered]@{
        current = $currentService
        legacy = $legacyService
    }
    com0com = [ordered]@{
        found = [bool]$com0comSetup
        setupc = $com0comSetup
    }
    evidence = @($evidence)
    issues = @($issues)
    recommended_actions = @($actions | Select-Object -Unique)
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 8
    exit 0
}

Write-Host ""
Write-Host "GADX Vector - Phase D installation detector" -ForegroundColor Cyan
Write-Host "Install root : $InstallRoot"
Write-Host "State        : $classification" -ForegroundColor Yellow
Write-Host "Mode         : $recommendedMode"
Write-Host ""

if ($evidence.Count -gt 0) {
    Write-Host "Evidence:"
    foreach ($item in $evidence) { Write-Host "  + $item" }
    Write-Host ""
}

if ($issues.Count -gt 0) {
    Write-Host "Issues:" -ForegroundColor Yellow
    foreach ($item in $issues) { Write-Host "  ! $item" }
    Write-Host ""
}

if ($actions.Count -gt 0) {
    Write-Host "Recommended actions:"
    foreach ($item in ($actions | Select-Object -Unique)) { Write-Host "  -> $item" }
    Write-Host ""
}

$result
