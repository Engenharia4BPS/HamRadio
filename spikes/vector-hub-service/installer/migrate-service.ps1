param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this script from an elevated PowerShell prompt."
    }
}

function Wait-ServiceState([string]$Name,[string]$State,[int]$Seconds=10) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        $svc = Get-Service -Name $Name -ErrorAction SilentlyContinue
        if ($svc -and [string]$svc.Status -eq $State) { return $true }
        Start-Sleep -Milliseconds 300
    } while ((Get-Date) -lt $deadline)
    return $false
}

function Remove-CurrentService([string]$Python,[string]$ServiceScript) {
    $svc = Get-Service -Name "GADXVectorHub" -ErrorAction SilentlyContinue
    if (-not $svc) { return }
    try { Stop-Service -Name "GADXVectorHub" -Force -ErrorAction SilentlyContinue } catch {}
    Start-Sleep -Milliseconds 500
    & $Python $ServiceScript remove 2>$null | Out-Null
    Start-Sleep -Milliseconds 700
}

Assert-Administrator

$Python = Join-Path $InstallRoot "runtime\python.exe"
$Hub = Join-Path $InstallRoot "app\vector_hub.py"
$Ts2000 = Join-Path $InstallRoot "app\ts2000.py"
$ServiceScript = Join-Path $InstallRoot "service\vector_service.py"
$Config = Join-Path $InstallRoot "config\vector.ini"

foreach ($required in @($Python,$Hub,$Ts2000,$ServiceScript,$Config)) {
    if (-not (Test-Path $required -PathType Leaf)) {
        throw "Required current-generation file is missing: $required"
    }
}

& $Python -c "import serial, win32serviceutil, servicemanager, tkinter" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Private runtime validation failed. tkinter, pyserial and pywin32 are required."
}

$legacy = Get-Service -Name "GADXVectorBridge" -ErrorAction SilentlyContinue
$current = Get-Service -Name "GADXVectorHub" -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "GADX Vector - Service migration" -ForegroundColor Cyan
Write-Host "Install root : $InstallRoot"
Write-Host "Python       : $Python"
Write-Host "Config       : $Config"
Write-Host "Legacy svc   : $(if ($legacy) { [string]$legacy.Status } else { 'not installed' })"
Write-Host "Current svc  : $(if ($current) { [string]$current.Status } else { 'not installed' })"
Write-Host ""

if (-not $Apply) {
    Write-Host "PREVIEW ONLY - no service changes were made." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Planned transaction:"
    Write-Host "  1. Validate private runtime and current-generation files."
    Write-Host "  2. Stop GADXVectorBridge temporarily if it is running."
    Write-Host "  3. Install/reinstall GADXVectorHub."
    Write-Host "  4. Configure delayed-auto and failure recovery."
    Write-Host "  5. Start GADXVectorHub and validate it remains Running."
    Write-Host "  6. If validation fails: remove GADXVectorHub and restart GADXVectorBridge."
    Write-Host "  7. If validation succeeds: delete GADXVectorBridge."
    exit 0
}

$legacyWasRunning = ($legacy -and [string]$legacy.Status -eq "Running")
$legacyStopped = $false

try {
    if ($legacyWasRunning) {
        Write-Host "Stopping legacy GADXVectorBridge..."
        Stop-Service -Name "GADXVectorBridge" -Force
        if (-not (Wait-ServiceState "GADXVectorBridge" "Stopped" 10)) {
            throw "GADXVectorBridge did not stop within 10 seconds."
        }
        $legacyStopped = $true
    }

    if ($current) {
        Write-Host "Removing previous GADXVectorHub service registration..."
        Remove-CurrentService $Python $ServiceScript
    }

    Write-Host "Installing GADXVectorHub..."
    & $Python $ServiceScript install
    if ($LASTEXITCODE -ne 0) { throw "vector_service.py install failed with exit code $LASTEXITCODE." }

    & sc.exe config GADXVectorHub start= delayed-auto | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not configure GADXVectorHub delayed-auto start." }

    & sc.exe failure GADXVectorHub reset= 86400 actions= restart/5000/restart/5000/restart/5000 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not configure GADXVectorHub recovery actions." }
    & sc.exe failureflag GADXVectorHub 1 | Out-Null

    Write-Host "Starting GADXVectorHub..."
    Start-Service -Name "GADXVectorHub"
    if (-not (Wait-ServiceState "GADXVectorHub" "Running" 10)) {
        throw "GADXVectorHub did not reach Running state."
    }

    # The service itself validates that vector_hub.py does not exit immediately.
    # Give it additional time so a startup failure is observed before legacy removal.
    Write-Host "Validating GADXVectorHub stability..."
    Start-Sleep -Seconds 4
    $check = Get-Service -Name "GADXVectorHub" -ErrorAction SilentlyContinue
    if (-not $check -or [string]$check.Status -ne "Running") {
        throw "GADXVectorHub did not remain Running during startup validation."
    }

    if ($legacy) {
        Write-Host "New service is healthy. Removing legacy GADXVectorBridge registration..."
        & sc.exe delete GADXVectorBridge | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "GADXVectorHub is healthy, but GADXVectorBridge could not be deleted." }
        Start-Sleep -Milliseconds 700
    }

    Write-Host ""
    Write-Host "Service migration completed successfully." -ForegroundColor Green
    Write-Host "GADXVectorHub : Running"
    Write-Host "GADXVectorBridge : removed (if previously installed)"
    Write-Host "Existing com0com pairs were not changed."
    Write-Host ""
}
catch {
    $failure = $_.Exception.Message
    Write-Warning "Service migration failed: $failure"
    Write-Warning "Starting rollback..."

    try { Remove-CurrentService $Python $ServiceScript } catch {}

    if ($legacyWasRunning) {
        try {
            $legacyNow = Get-Service -Name "GADXVectorBridge" -ErrorAction SilentlyContinue
            if ($legacyNow) {
                Start-Service -Name "GADXVectorBridge" -ErrorAction Stop
                if (Wait-ServiceState "GADXVectorBridge" "Running" 10) {
                    Write-Host "Rollback OK: GADXVectorBridge is Running again." -ForegroundColor Yellow
                } else {
                    Write-Warning "Rollback attempted, but GADXVectorBridge did not reach Running state."
                }
            } else {
                Write-Warning "Rollback could not restart GADXVectorBridge because its service registration is missing."
            }
        } catch {
            Write-Warning "Rollback error while restarting GADXVectorBridge: $($_.Exception.Message)"
        }
    }

    throw "D3 service migration aborted. Legacy service was preserved whenever possible. Original error: $failure"
}
