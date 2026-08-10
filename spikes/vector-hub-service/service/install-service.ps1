param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector"
)

$ErrorActionPreference = "Stop"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Execute este script em PowerShell como Administrador."
    }
}

function Resolve-VectorPython([string]$Root) {
    $privatePython = Join-Path $Root "runtime\python.exe"

    if (Test-Path $privatePython) {
        Write-Host "Python runtime: privado do Vector ($privatePython)"
        return $privatePython
    }

    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($command -and $command.Source -and (Test-Path $command.Source)) {
        Write-Warning "Runtime privado do Vector nao encontrado."
        Write-Warning "Usando Python global SOMENTE para validacao da Fase B: $($command.Source)"
        return $command.Source
    }

    $legacy310 = "C:\Python\Python310\python.exe"
    if (Test-Path $legacy310) {
        Write-Warning "Runtime privado do Vector nao encontrado."
        Write-Warning "Usando Python 3.10 legado SOMENTE para validacao da Fase B: $legacy310"
        return $legacy310
    }

    throw "Nenhum Python utilizavel encontrado."
}

Assert-Administrator

$Python = Resolve-VectorPython $InstallRoot
$ServiceScript = Join-Path $InstallRoot "service\vector_service.py"
$Hub = Join-Path $InstallRoot "app\vector_hub.py"
$Config = Join-Path $InstallRoot "config\vector.ini"

foreach ($required in @($ServiceScript, $Hub, $Config)) {
    if (-not (Test-Path $required)) {
        throw "Arquivo necessario nao encontrado: $required"
    }
}

& $Python -c "import serial, win32serviceutil, servicemanager" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Python encontrado em $Python, mas faltam pyserial/pywin32."
}

$legacy = Get-Service -Name "GADXVectorBridge" -ErrorAction SilentlyContinue
if ($legacy -and $legacy.Status -ne "Stopped") {
    Write-Host "Parando servico legado GADXVectorBridge..."
    Stop-Service GADXVectorBridge -Force
    $legacy.WaitForStatus("Stopped", [TimeSpan]::FromSeconds(10))
}

$existing = Get-Service -Name "GADXVectorHub" -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removendo instalacao anterior de GADXVectorHub..."
    try { Stop-Service GADXVectorHub -Force -ErrorAction SilentlyContinue } catch {}
    & $Python $ServiceScript remove 2>$null | Out-Null
    Start-Sleep -Milliseconds 750
}

Write-Host "Instalando GADXVectorHub com: $Python"
& $Python $ServiceScript install
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar GADXVectorHub." }

& sc.exe config GADXVectorHub start= delayed-auto | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Falha ao configurar delayed-auto." }

& sc.exe failure GADXVectorHub reset= 86400 actions= restart/5000/restart/5000/restart/5000 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Falha ao configurar recovery." }

& sc.exe failureflag GADXVectorHub 1 | Out-Null

Write-Host "Iniciando GADXVectorHub..."
Start-Service GADXVectorHub
Start-Sleep -Seconds 2

$service = Get-Service GADXVectorHub
if ($service.Status -ne "Running") {
    throw "Servico instalado, mas nao permaneceu Running. Consulte logs e Event Viewer."
}

Write-Host ""
Write-Host "GADX Vector Hub - Phase B service instalado e Running."
Write-Host "Servico: GADXVectorHub"
Write-Host "Python:  $Python"
Write-Host "Config:  $Config"
Write-Host "Log:     $(Join-Path $InstallRoot 'logs\vector-hub.log')"
