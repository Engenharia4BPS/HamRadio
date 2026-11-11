param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector"
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$Python = Join-Path $InstallRoot "runtime\python.exe"
$ServiceScript = Join-Path $InstallRoot "winkey-emulator\winkey_service.py"
$Emulator = Join-Path $InstallRoot "winkey-emulator\winkey_emulator.py"
$Config = Join-Path $InstallRoot "winkey-emulator\winkey.ini"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Execute este script em PowerShell como Administrador."
    }
}

Assert-Administrator
foreach ($path in @($Python,$ServiceScript,$Emulator,$Config)) {
    if (-not (Test-Path $path -PathType Leaf)) { throw "Arquivo necessario nao encontrado: $path" }
}

& $Python -c "import serial, win32serviceutil, servicemanager" 2>$null
if ($LASTEXITCODE -ne 0) { throw "O runtime privado nao possui pyserial/pywin32." }

$existing = Get-Service -Name "GADXWinKeyEmulator" -ErrorAction SilentlyContinue
if ($existing) {
    try { Stop-Service -Name "GADXWinKeyEmulator" -Force -ErrorAction SilentlyContinue } catch {}
    & $Python $ServiceScript remove 2>$null | Out-Null
    Start-Sleep -Milliseconds 750
}

& $Python $ServiceScript install
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar GADXWinKeyEmulator." }
& sc.exe config GADXWinKeyEmulator start= delayed-auto | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Falha ao configurar delayed-auto para GADXWinKeyEmulator." }
& sc.exe failure GADXWinKeyEmulator reset= 86400 actions= restart/5000/restart/5000/restart/5000 | Out-Null
& sc.exe failureflag GADXWinKeyEmulator 1 | Out-Null

Start-Service GADXWinKeyEmulator
Start-Sleep -Seconds 2
if ((Get-Service GADXWinKeyEmulator).Status -ne "Running") {
    throw "GADXWinKeyEmulator nao permaneceu Running. Consulte logs\winkey-emulator.log."
}
Write-Host "GADXWinKeyEmulator instalado e Running." -ForegroundColor Green
