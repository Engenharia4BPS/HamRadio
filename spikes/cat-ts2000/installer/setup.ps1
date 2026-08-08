param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")),
    [string]$SetupcPath = "",
    [string]$RadioKeyingPort = "COM22",
    [int]$RadioKeyingBaud = 9600,
    [string]$RigHost = "127.0.0.1",
    [int]$RigPort = 4532,
    [switch]$SkipService
)

$ErrorActionPreference = "Stop"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Execute este setup em um PowerShell 'Executar como administrador'."
    }
}

function Find-Setupc {
    param([string]$Preferred)
    if ($Preferred -and (Test-Path $Preferred)) { return (Resolve-Path $Preferred).Path }

    $candidates = @(
        "$env:ProgramFiles\com0com\setupc.exe",
        "${env:ProgramFiles(x86)}\com0com\setupc.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) { return $candidate }
    }
    throw "Nao encontrei setupc.exe do com0com. Instale o com0com Signed ou informe -SetupcPath C:\caminho\setupc.exe"
}

function Get-BusyComNumbers {
    param([string]$Setupc)
    $output = & $Setupc --silent busynames 'COM?*' 2>&1
    $busy = New-Object 'System.Collections.Generic.HashSet[int]'
    foreach ($line in $output) {
        if ($line -match '^\s*COM(\d+)\s*$') { [void]$busy.Add([int]$Matches[1]) }
    }
    return $busy
}

function Find-FreeCom {
    param(
        [System.Collections.Generic.HashSet[int]]$Busy,
        [int]$Min,
        [int]$Max,
        [int[]]$Exclude = @()
    )
    for ($n = $Min; $n -le $Max; $n++) {
        if (($Exclude -notcontains $n) -and (-not $Busy.Contains($n))) { return $n }
    }
    throw "Nao existe porta COM livre entre COM$Min e COM$Max."
}

function Install-ComPair {
    param([string]$Setupc, [int]$Left, [int]$Right)
    Write-Host "Criando par COM$Left <-> COM$Right ..." -ForegroundColor Cyan
    & $Setupc --wait 30 install "PortName=COM$Left" "PortName=COM$Right"
    if ($LASTEXITCODE -ne 0) { throw "Falha ao criar par COM$Left/COM$Right (exit $LASTEXITCODE)." }
}

function Write-BridgeIni {
    param(
        [string]$Path,
        [int]$VectorCat,
        [int]$VectorKeying,
        [string]$RadioKey,
        [int]$RadioKeyBaud,
        [string]$HostName,
        [int]$HostPort
    )
    @"
[bridge]
port = COM$VectorCat
baud = 19200

keying_port = COM$VectorKeying
keying_baud = 19200

radio_keying_port = $RadioKey
radio_keying_baud = $RadioKeyBaud

rig_host = $HostName
rig_port = $HostPort
poll_ms = 250

allow_write = true
allow_ptt = true
allow_cw = true

log_level = INFO
"@ | Set-Content -Path $Path -Encoding UTF8
}

Assert-Administrator
$setupc = Find-Setupc -Preferred $SetupcPath
Write-Host "com0com: $setupc" -ForegroundColor DarkGray

$busy = Get-BusyComNumbers -Setupc $setupc

# Requisito: as duas portas apresentadas ao logger devem ficar entre COM10 e COM30.
$loggerCat = Find-FreeCom -Busy $busy -Min 10 -Max 30
[void]$busy.Add($loggerCat)
$loggerKey = Find-FreeCom -Busy $busy -Min 10 -Max 30 -Exclude @($loggerCat)
[void]$busy.Add($loggerKey)

# As pontas internas do Vector podem usar numeros altos.
$vectorCat = Find-FreeCom -Busy $busy -Min 100 -Max 199
[void]$busy.Add($vectorCat)
$vectorKey = Find-FreeCom -Busy $busy -Min 100 -Max 199 -Exclude @($vectorCat)

Write-Host "Plano de portas:" -ForegroundColor Green
Write-Host "  Logger CAT:    COM$loggerCat  <-> Vector CAT:    COM$vectorCat"
Write-Host "  Logger CW/PTT: COM$loggerKey  <-> Vector Keying: COM$vectorKey"
Write-Host "  Radio keying:  $RadioKeyingPort"

$answer = Read-Host "Continuar? [S/n]"
if ($answer -match '^[Nn]') { exit 1 }

Install-ComPair -Setupc $setupc -Left $loggerCat -Right $vectorCat
Install-ComPair -Setupc $setupc -Left $loggerKey -Right $vectorKey

$programData = Join-Path $env:ProgramData "GADXVector"
$logDir = Join-Path $programData "logs"
New-Item -ItemType Directory -Force -Path $programData, $logDir | Out-Null

$iniPath = Join-Path $programData "bridge.ini"
Write-BridgeIni -Path $iniPath -VectorCat $vectorCat -VectorKeying $vectorKey -RadioKey $RadioKeyingPort -RadioKeyBaud $RadioKeyingBaud -HostName $RigHost -HostPort $RigPort

@"
[logger]
cat_port = COM$loggerCat
keying_port = COM$loggerKey
radio_model = TS-2000
cat_baud = 19200
"@ | Set-Content -Path (Join-Path $programData "logger.ini") -Encoding UTF8

Write-Host "bridge.ini gerado em $iniPath" -ForegroundColor Green

if (-not $SkipService) {
    Write-Host "Preparando runtime do servico..." -ForegroundColor Cyan

    $appDir = Join-Path $env:ProgramFiles "GADX Vector"
    $serviceDir = Join-Path $appDir "service"
    New-Item -ItemType Directory -Force -Path $appDir, $serviceDir | Out-Null

    Copy-Item (Join-Path $RepoRoot "rigctld_bridge.py") (Join-Path $appDir "rigctld_bridge.py") -Force
    Copy-Item (Join-Path $RepoRoot "ts2000.py") (Join-Path $appDir "ts2000.py") -Force
    Copy-Item (Join-Path $RepoRoot "service\vector_bridge_service.py") (Join-Path $serviceDir "vector_bridge_service.py") -Force

    & python -m pip install --upgrade pyserial pywin32
    if ($LASTEXITCODE -ne 0) { throw "Falha instalando pyserial/pywin32." }

    # A documentacao do pywin32 recomenda o post-install global/elevado para servicos.
    & python -m pywin32_postinstall -install
    if ($LASTEXITCODE -ne 0) { throw "Falha no pywin32_postinstall." }

    $serviceScript = Join-Path $serviceDir "vector_bridge_service.py"

    # Remove uma instalacao anterior do wrapper, se houver.
    & python $serviceScript stop 2>$null | Out-Null
    & python $serviceScript remove 2>$null | Out-Null

    & python $serviceScript install
    if ($LASTEXITCODE -ne 0) { throw "Falha instalando o servico GADXVectorBridge." }

    # Configuracao nativa do Windows: delayed-auto + tres tentativas de reinicio.
    & sc.exe config GADXVectorBridge start= delayed-auto | Out-Null
    & sc.exe failure GADXVectorBridge reset= 86400 actions= restart/5000/restart/5000/restart/5000 | Out-Null
    & sc.exe failureflag GADXVectorBridge 1 | Out-Null

    & python $serviceScript start
    if ($LASTEXITCODE -ne 0) { throw "Servico instalado, mas nao iniciou. Consulte Event Viewer e $logDir." }
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Green
Write-Host " GADX Vector - setup concluido" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
Write-Host "Configure o logger assim:"
Write-Host "  Radio:  Kenwood TS-2000"
Write-Host "  CAT:    COM$loggerCat @ 19200 8N1"
Write-Host "  CW/PTT: COM$loggerKey"
Write-Host "  DTR:    PTT"
Write-Host "  RTS:    CW"
Write-Host ""
Write-Host "Vector interno: COM$vectorCat (CAT), COM$vectorKey (keying)"
Write-Host "Config: $iniPath"
Write-Host "Logs:   $logDir"
if (-not $SkipService) { Write-Host "Servico: GADX Vector Bridge (Automatic Delayed Start)" }
