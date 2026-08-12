param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PayloadRoot = Join-Path $InstallerRoot "payload"

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

function Assert-Payload {
    $requiredPayload = @(
        (Join-Path $PayloadRoot "app\vector_hub.py")
        (Join-Path $PayloadRoot "app\ts2000.py")
        (Join-Path $PayloadRoot "service\vector_service.py")
    )
    foreach ($required in $requiredPayload) {
        if (-not (Test-Path $required -PathType Leaf)) {
            throw "Installer payload is incomplete. Missing: $required"
        }
    }
}

function Deploy-Payload {
    $appDir = Join-Path $InstallRoot "app"
    $serviceDir = Join-Path $InstallRoot "service"
    New-Item -ItemType Directory -Force -Path $appDir,$serviceDir | Out-Null

    Copy-Item -LiteralPath (Join-Path $PayloadRoot "app\vector_hub.py") -Destination (Join-Path $appDir "vector_hub.py") -Force
    Copy-Item -LiteralPath (Join-Path $PayloadRoot "app\ts2000.py") -Destination (Join-Path $appDir "ts2000.py") -Force
    Copy-Item -LiteralPath (Join-Path $PayloadRoot "service\vector_service.py") -Destination (Join-Path $serviceDir "vector_service.py") -Force
}

Assert-Administrator
Assert-Payload

$Python = Join-Path $InstallRoot "runtime\python.exe"
$Hub = Join-Path $InstallRoot "app\vector_hub.py"
$Ts2000 = Join-Path $InstallRoot "app\ts2000.py"
$ServiceScript = Join-Path $InstallRoot "service\vector_service.py"
$Config = Join-Path $InstallRoot "config\vector.ini"

if (-not (Test-Path $Python -PathType Leaf)) {
    throw "Private runtime is missing: $Python"
}
if (-not (Test-Path $Config -PathType Leaf)) {
    throw "Migrated/current vector.ini is missing: $Config"
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
Write-Host "Payload      : $PayloadRoot"
Write-Host "Python       : $Python"
Write-Host "Config       : $Config"
Write-Host "Legacy svc   : $(if ($legacy) { [string]$legacy.Status } else { 'not installed' })"
Write-Host "Current svc  : $(if ($current) { [string]$current.Status } else { 'not installed' })"
Write-Host ""

if (-not $Apply) {
    Write-Host "PREVIEW ONLY - no files or services were changed." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Planned transaction:"
    Write-Host "  1. Validate private runtime, vector.ini and installer payload."
    Write-Host "  2. Deploy current vector_hub.py, ts2000.py and vector_service.py from installer\payload."
    Write-Host "  3. Stop GADXVectorBridge temporarily if it is running."
    Write-Host "  4. Install/reinstall GADXVectorHub."
    Write-Host "  5. Configure delayed-auto and failure recovery."
    Write-Host "  6. Start GADXVectorHub and validate it remains Running."
    Write-Host "  7. If validation fails: remove GADXVectorHub and restart GADXVectorBridge."
    Write-Host "  8. If validation succeeds: delete GADXVectorBridge."
    Write-Host ""
    Write-Host "The existing vector.ini and com0com pairs will be preserved."
    exit 0
}

$legacyWasRunning = ($legacy -and [string]$legacy.Status -eq "Running")

try {
    Write-Host "Deploying current-generation payload..."
    Deploy-Payload

    foreach ($required in @($Hub,$Ts2000,$ServiceScript,$Config)) {
        if (-not (Test-Path $required -PathType Leaf)) {
            throw "Required current-generation file is missing after payload deployment: $required"
        }
    }

    if ($legacyWasRunning) {
        Write-Host "Stopping legacy GADXVectorBridge..."
        Stop-Service -Name "GADXVectorBridge" -Force
        if (-not (Wait-ServiceState "GADXVectorBridge" "Stopped" 10)) {
            throw "GADXVectorBridge did not stop within 10 seconds."
        }
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
    Write-Host "GADXVectorHub    : Running"
    Write-Host "GADXVectorBridge : removed (if previously installed)"
    Write-Host "vector.ini       : preserved"
    Write-Host "com0com pairs    : unchanged"
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
