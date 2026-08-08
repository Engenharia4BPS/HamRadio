param(
    [string]$RepoRoot = "",
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
    throw "Nao encontrei setupc.exe do com0com. Instale o com0com Signed ou informe -SetupcPath."
}

function Resolve-RuntimeRoot {
    param([string]$Preferred)
    $candidates = New-Object System.Collections.Generic.List[string]
    if ($Preferred) { $candidates.Add($Preferred) }
    $candidates.Add($PSScriptRoot)
    $candidates.Add((Join-Path $PSScriptRoot ".."))
    $candidates.Add((Get-Location).Path)

    foreach ($candidate in $candidates) {
        if (-not $candidate) { continue }
        try { $resolved = (Resolve-Path $candidate -ErrorAction Stop).Path } catch { continue }
        $bridge = Join-Path $resolved "rigctld_bridge.py"
        $ts = Join-Path $resolved "ts2000.py"
        $svc1 = Join-Path $resolved "service\vector_bridge_service.py"
        $svc2 = Join-Path $resolved "vector_bridge_service.py"
        if ((Test-Path $bridge) -and (Test-Path $ts) -and ((Test-Path $svc1) -or (Test-Path $svc2))) {
            return $resolved
        }
    }
    throw @"
Nao encontrei o runtime completo do Vector.

O setup precisa encontrar juntos:
  rigctld_bridge.py
  ts2000.py
  service\vector_bridge_service.py  (ou vector_bridge_service.py)

Baixe a pasta completa spikes\cat-ts2000 do GitHub ou use:
  .\setup.ps1 -RepoRoot C:\caminho\para\cat-ts2000

Nenhuma nova porta COM sera criada enquanto esse pre-flight falhar.
"@
}

function Invoke-Setupc {
    param([string]$Setupc, [string[]]$Arguments, [switch]$Quiet)
    $setupDir = Split-Path -Parent $Setupc
    Push-Location $setupDir
    try {
        $output = @(& $Setupc @Arguments 2>&1)
        $exitCode = [int]$LASTEXITCODE
        if (-not $Quiet) { foreach ($line in $output) { Write-Host $line } }
        return $exitCode
    }
    finally { Pop-Location }
}

function Get-SetupcList {
    param([string]$Setupc)
    $setupDir = Split-Path -Parent $Setupc
    Push-Location $setupDir
    try { return @(& $Setupc --silent list 2>&1) }
    finally { Pop-Location }
}

function Get-BusyComNumbers {
    param([string]$Setupc)
    $setupDir = Split-Path -Parent $Setupc
    Push-Location $setupDir
    try { $output = & $Setupc --silent busynames 'COM?*' 2>&1 }
    finally { Pop-Location }
    $busy = [System.Collections.Generic.HashSet[int]]::new()
    foreach ($line in $output) {
        if ($line -match '^\s*COM(\d+)\s*$') { [void]$busy.Add([int]$Matches[1]) }
    }
    return ,$busy
}

function Test-ComPairExists {
    param([string[]]$ListOutput, [int]$Left, [int]$Right)
    $leftFound = $false; $rightFound = $false
    foreach ($line in $ListOutput) {
        if ($line -match "PortName=COM$Left(?:\s|$)|RealPortName=COM$Left(?:\s|$)") { $leftFound = $true }
        if ($line -match "PortName=COM$Right(?:\s|$)|RealPortName=COM$Right(?:\s|$)") { $rightFound = $true }
    }
    return ($leftFound -and $rightFound)
}

function Find-FreeCom {
    param([System.Collections.Generic.HashSet[int]]$Busy, [int]$Min, [int]$Max, [int[]]$Exclude = @())
    for ($n = $Min; $n -le $Max; $n++) {
        if (($Exclude -notcontains $n) -and (-not $Busy.Contains($n))) { return $n }
    }
    throw "Nao existe porta COM livre entre COM$Min e COM$Max."
}

function Install-ComPair {
    param([string]$Setupc, [int]$Left, [int]$Right)
    Write-Host "Criando par COM$Left <-> COM$Right ..." -ForegroundColor Cyan
    $exitCode = Invoke-Setupc -Setupc $Setupc -Arguments @('--wait','30','install',"PortName=COM$Left","PortName=COM$Right")
    if ($exitCode -ne 0) { throw "Falha ao criar par COM$Left/COM$Right (exit $exitCode)." }
}

function Get-IniComNumber {
    param([string]$Path, [string]$Key)
    if (-not (Test-Path $Path)) { return $null }
    foreach ($line in Get-Content $Path) {
        if ($line -match "^\s*$Key\s*=\s*COM(\d+)\s*$") { return [int]$Matches[1] }
    }
    return $null
}

function Write-BridgeIni {
    param([string]$Path,[int]$VectorCat,[int]$VectorKeying,[string]$RadioKey,[int]$RadioKeyBaud,[string]$HostName,[int]$HostPort)
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

function Invoke-PyWin32PostInstall {
    Write-Host "Executando pywin32 post-install..." -ForegroundColor Cyan

    # Forma oficial preferida (pywin32 >= 309).
    & python -m pywin32_postinstall -install
    if ($LASTEXITCODE -eq 0) { return }

    Write-Host "Modulo pywin32_postinstall nao foi encontrado; tentando console script..." -ForegroundColor Yellow

    $scriptsDir = (& python -c "import sysconfig; print(sysconfig.get_path('scripts'))").Trim()
    $candidates = @(
        (Join-Path $scriptsDir "pywin32_postinstall.exe"),
        (Join-Path $scriptsDir "pywin32_postinstall.py"),
        (Join-Path $scriptsDir "pywin32_postinstall")
    )

    foreach ($candidate in $candidates) {
        if (-not (Test-Path $candidate)) { continue }
        Write-Host "pywin32 post-install: $candidate" -ForegroundColor DarkGray
        if ($candidate.ToLower().EndsWith('.py')) {
            & python $candidate -install
        }
        else {
            & $candidate -install
        }
        if ($LASTEXITCODE -eq 0) { return }
    }

    throw @"
Nao foi possivel executar o pywin32 post-install.
O pywin32 foi instalado, mas nem o modulo nem o console script foram encontrados/aceitos.
Scripts pesquisados em: $scriptsDir
"@
}

Assert-Administrator
$setupc = Find-Setupc -Preferred $SetupcPath
Write-Host "com0com: $setupc" -ForegroundColor DarkGray

$runtimeRoot = $null
if (-not $SkipService) {
    $runtimeRoot = Resolve-RuntimeRoot -Preferred $RepoRoot
    Write-Host "Runtime: $runtimeRoot" -ForegroundColor DarkGray
}

$programData = Join-Path $env:ProgramData "GADXVector"
$logDir = Join-Path $programData "logs"
$iniPath = Join-Path $programData "bridge.ini"
$loggerIniPath = Join-Path $programData "logger.ini"
New-Item -ItemType Directory -Force -Path $programData, $logDir | Out-Null

$loggerCat = Get-IniComNumber -Path $loggerIniPath -Key "cat_port"
$loggerKey = Get-IniComNumber -Path $loggerIniPath -Key "keying_port"
$vectorCat = Get-IniComNumber -Path $iniPath -Key "port"
$vectorKey = Get-IniComNumber -Path $iniPath -Key "keying_port"
$listOutput = Get-SetupcList -Setupc $setupc
$resume = $false

if ($null -ne $loggerCat -and $null -ne $loggerKey -and $null -ne $vectorCat -and $null -ne $vectorKey) {
    if ((Test-ComPairExists -ListOutput $listOutput -Left $loggerCat -Right $vectorCat) -and
        (Test-ComPairExists -ListOutput $listOutput -Left $loggerKey -Right $vectorKey)) {
        $resume = $true
        Write-Host "Instalacao parcial detectada; reutilizando portas existentes." -ForegroundColor Yellow
    }
}

if (-not $resume) {
    $busy = Get-BusyComNumbers -Setupc $setupc
    $loggerCat = Find-FreeCom -Busy $busy -Min 10 -Max 30
    [void]$busy.Add($loggerCat)
    $loggerKey = Find-FreeCom -Busy $busy -Min 10 -Max 30 -Exclude @($loggerCat)
    [void]$busy.Add($loggerKey)
    $vectorCat = Find-FreeCom -Busy $busy -Min 100 -Max 199
    [void]$busy.Add($vectorCat)
    $vectorKey = Find-FreeCom -Busy $busy -Min 100 -Max 199 -Exclude @($vectorCat)
}

Write-Host "Plano de portas:" -ForegroundColor Green
Write-Host "  Logger CAT:    COM$loggerCat  <-> Vector CAT:    COM$vectorCat"
Write-Host "  Logger CW/PTT: COM$loggerKey  <-> Vector Keying: COM$vectorKey"
Write-Host "  Radio keying:  $RadioKeyingPort"
if ($resume) { Write-Host "  Modo: retomada (pares ja existentes)" -ForegroundColor Yellow }

$answer = Read-Host "Continuar? [S/n]"
if ($answer -match '^[Nn]') { exit 1 }

if (-not $resume) {
    Install-ComPair -Setupc $setupc -Left $loggerCat -Right $vectorCat
    Install-ComPair -Setupc $setupc -Left $loggerKey -Right $vectorKey
}

Write-BridgeIni -Path $iniPath -VectorCat $vectorCat -VectorKeying $vectorKey -RadioKey $RadioKeyingPort -RadioKeyBaud $RadioKeyingBaud -HostName $RigHost -HostPort $RigPort
@"
[logger]
cat_port = COM$loggerCat
keying_port = COM$loggerKey
radio_model = TS-2000
cat_baud = 19200
"@ | Set-Content -Path $loggerIniPath -Encoding UTF8
Write-Host "bridge.ini gerado em $iniPath" -ForegroundColor Green

if (-not $SkipService) {
    Write-Host "Preparando runtime do servico..." -ForegroundColor Cyan
    $appDir = Join-Path $env:ProgramFiles "GADX Vector"
    $serviceDir = Join-Path $appDir "service"
    New-Item -ItemType Directory -Force -Path $appDir, $serviceDir | Out-Null

    $serviceSource = Join-Path $runtimeRoot "service\vector_bridge_service.py"
    if (-not (Test-Path $serviceSource)) { $serviceSource = Join-Path $runtimeRoot "vector_bridge_service.py" }
    Copy-Item (Join-Path $runtimeRoot "rigctld_bridge.py") (Join-Path $appDir "rigctld_bridge.py") -Force
    Copy-Item (Join-Path $runtimeRoot "ts2000.py") (Join-Path $appDir "ts2000.py") -Force
    Copy-Item $serviceSource (Join-Path $serviceDir "vector_bridge_service.py") -Force

    & python -m pip install --upgrade pyserial pywin32
    if ($LASTEXITCODE -ne 0) { throw "Falha instalando pyserial/pywin32." }
    Invoke-PyWin32PostInstall

    $serviceScript = Join-Path $serviceDir "vector_bridge_service.py"
    & python $serviceScript stop 2>$null | Out-Null
    & python $serviceScript remove 2>$null | Out-Null
    & python $serviceScript install
    if ($LASTEXITCODE -ne 0) { throw "Falha instalando o servico GADXVectorBridge." }
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
