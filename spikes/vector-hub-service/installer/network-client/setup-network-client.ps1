param(
    [Parameter(Mandatory = $true)]
    [string]$RigHost,
    [ValidateRange(1,65535)]
    [int]$RigPort = 4532,
    [ValidatePattern('^COM\d+$')]
    [string]$N1mmCatPort = "COM15",
    [ValidatePattern('^COM\d+$')]
    [string]$VectorCatPort = "COM101",
    [ValidatePattern('^COM\d+$')]
    [string]$N1mmWinKeyPort = "COM19",
    [ValidatePattern('^COM\d+$')]
    [string]$EmulatorWinKeyPort = "COM108",
    [string]$InstallRoot = "C:\Ham\GADX-Vector",
    [switch]$EnableWinKeyTransmit,
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$InstallerRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PayloadRoot = Join-Path $InstallerRoot "payload"
$EnsureRuntime = Join-Path $InstallerRoot "ensure-runtime.ps1"
$Python = Join-Path $InstallRoot "runtime\python.exe"
$VectorIni = Join-Path $InstallRoot "config\vector.ini"
$NetworkMarker = Join-Path $InstallRoot "config\network-client.json"
$RebootMarker = Join-Path $InstallRoot "config\network-client-reboot-required.flag"

$RigHost = $RigHost.Trim()
$N1mmCatPort = $N1mmCatPort.ToUpperInvariant()
$VectorCatPort = $VectorCatPort.ToUpperInvariant()
$N1mmWinKeyPort = $N1mmWinKeyPort.ToUpperInvariant()
$EmulatorWinKeyPort = $EmulatorWinKeyPort.ToUpperInvariant()

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Execute este script em PowerShell como Administrador."
    }
}

function Require-File([string]$Path,[string]$Label) {
    if (-not (Test-Path $Path -PathType Leaf)) { throw "$Label nao encontrado: $Path" }
}

function Find-Com0comSetup {
    foreach ($candidate in @(
        "C:\Ham\com0com\setupc.exe",
        "$env:ProgramFiles\com0com\setupc.exe",
        "${env:ProgramFiles(x86)}\com0com\setupc.exe"
    )) {
        if ($candidate -and (Test-Path $candidate -PathType Leaf)) {
            return (Resolve-Path $candidate).Path
        }
    }
    throw "com0com setupc.exe nao encontrado."
}

function Invoke-Com0com([string]$SetupExe,[string[]]$Arguments) {
    Push-Location (Split-Path -Parent $SetupExe)
    try { return @(& $SetupExe @Arguments 2>&1) }
    finally { Pop-Location }
}

function Get-Com0comPairs([string]$SetupExe) {
    $ends = @{}
    foreach ($line in (Invoke-Com0com $SetupExe @('list'))) {
        if ([string]$line -match '^\s*CNC([AB])(\d+)\s+PortName=(COM\d+)\s*$') {
            $index = $Matches[2]
            if (-not $ends.ContainsKey($index)) { $ends[$index] = @{} }
            $ends[$index][$Matches[1]] = $Matches[3].ToUpperInvariant()
        }
    }
    $pairs = @()
    foreach ($index in $ends.Keys) {
        if ($ends[$index].ContainsKey('A') -and $ends[$index].ContainsKey('B')) {
            $pairs += [pscustomobject]@{ Index = $index; A = $ends[$index]['A']; B = $ends[$index]['B'] }
        }
    }
    return $pairs
}

function Ensure-VirtualPair([string]$SetupExe,[string]$Left,[string]$Right) {
    $pairs = @(Get-Com0comPairs $SetupExe)
    foreach ($pair in $pairs) {
        $samePair = (($pair.A -eq $Left -and $pair.B -eq $Right) -or ($pair.A -eq $Right -and $pair.B -eq $Left))
        if ($samePair) {
            Write-Host "Par virtual preservado: $Left <-> $Right"
            return $false
        }
        if ($pair.A -in @($Left,$Right) -or $pair.B -in @($Left,$Right)) {
            throw "A porta $Left ou $Right ja pertence ao par $($pair.A) <-> $($pair.B). Nenhuma porta foi alterada."
        }
    }

    Write-Host "Criando par virtual: $Left <-> $Right"
    $output = Invoke-Com0com $SetupExe @('install',("PortName=$Left"),("PortName=$Right"))
    $text = ($output | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "com0com nao criou $Left <-> $Right.`n$text" }
    Write-Host $text.Trim()
    return ($text -match '(?i)reboot required')
}

function Write-Utf8NoBom([string]$Path,[string]$Text) {
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path,$Text,$encoding)
}

function Stop-ManagedService([string]$Name) {
    $service = Get-Service -Name $Name -ErrorAction SilentlyContinue
    if ($service) {
        try { Stop-Service -Name $Name -Force -ErrorAction SilentlyContinue } catch {}
        Start-Sleep -Milliseconds 400
    }
}

function Install-ManagedService([string]$Name,[string]$ScriptPath) {
    $service = Get-Service -Name $Name -ErrorAction SilentlyContinue
    if ($service) {
        Stop-ManagedService $Name
        & $Python $ScriptPath remove 2>$null | Out-Null
        Start-Sleep -Milliseconds 700
    }
    & $Python $ScriptPath install
    if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar o servico $Name." }
    & sc.exe config $Name start= delayed-auto | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Falha ao configurar delayed-auto para $Name." }
    & sc.exe failure $Name reset= 86400 actions= restart/5000/restart/5000/restart/5000 | Out-Null
    & sc.exe failureflag $Name 1 | Out-Null
    Start-Service $Name
    Start-Sleep -Seconds 2
    if ((Get-Service $Name).Status -ne 'Running') { throw "$Name nao permaneceu Running." }
}

if (-not $RigHost -or $RigHost -match '\s') { throw "RigHost deve ser um IP ou nome DNS sem espacos." }
$requestedPorts = @($N1mmCatPort,$VectorCatPort,$N1mmWinKeyPort,$EmulatorWinKeyPort)
if (($requestedPorts | Select-Object -Unique).Count -ne $requestedPorts.Count) {
    throw "As quatro portas COM devem ser diferentes."
}

foreach ($required in @(
    $EnsureRuntime,
    (Join-Path $PayloadRoot "app\vector_hub.py"),
    (Join-Path $PayloadRoot "app\ts2000.py"),
    (Join-Path $PayloadRoot "service\vector_service.py"),
    (Join-Path $PayloadRoot "winkey-emulator\winkey_emulator.py"),
    (Join-Path $PayloadRoot "winkey-emulator\winkey_service.py"),
    (Join-Path $PayloadRoot "winkey-emulator\run-winkey-emulator.ps1")
)) { Require-File $required "Payload" }

Write-Host ""
Write-Host "GADX Vector - Cliente de Rede CAT + WinKey" -ForegroundColor Cyan
Write-Host "Install root      : $InstallRoot"
Write-Host "rigctld remoto    : $RigHost`:$RigPort"
Write-Host "CAT N1MM          : $N1mmCatPort <-> $VectorCatPort (Vector)"
Write-Host "WinKey N1MM       : $N1mmWinKeyPort <-> $EmulatorWinKeyPort (emulador)"
Write-Host "WinKey transmite  : $($EnableWinKeyTransmit.IsPresent)"
Write-Host "Abort remoto      : desativado (seguro para TS-2000)"
Write-Host "Modo              : $(if ($Apply) { 'APPLY' } else { 'PREVIEW' })"
Write-Host ""

$reachable = Test-NetConnection -ComputerName $RigHost -Port $RigPort -InformationLevel Quiet -WarningAction SilentlyContinue
if (-not $reachable) {
    throw "Nao foi possivel alcançar $RigHost`:$RigPort. Conecte a nova maquina à LAN/VPN e libere o rigctld remoto antes de instalar."
}
Write-Host "Rede rigctld      : OK" -ForegroundColor Green

if (-not $Apply) {
    Write-Host "PREVIEW ONLY - nenhuma COM, servico ou configuracao foi alterada." -ForegroundColor Yellow
    Write-Host "Ao aplicar, o perfil cria apenas as duas COMs acima, instala GADXVectorHub e GADXWinKeyEmulator e mantem keying fisico desabilitado nesta maquina."
    exit 0
}

Assert-Administrator
if ((Test-Path $VectorIni -PathType Leaf) -and -not (Test-Path $NetworkMarker -PathType Leaf)) {
    throw "Ja existe vector.ini sem marcador deste perfil de rede. O script recusou sobrescrever uma instalacao desconhecida."
}

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $EnsureRuntime -InstallRoot $InstallRoot -Apply
if ($LASTEXITCODE -ne 0) { throw "ensure-runtime.ps1 falhou." }
Require-File $Python "Runtime privado"

$com0com = Find-Com0comSetup
foreach ($dir in @('app','service','tools','config','logs','winkey-emulator')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $InstallRoot $dir) | Out-Null
}

Copy-Item -Force (Join-Path $PayloadRoot 'app\vector_hub.py') (Join-Path $InstallRoot 'app\vector_hub.py')
Copy-Item -Force (Join-Path $PayloadRoot 'app\ts2000.py') (Join-Path $InstallRoot 'app\ts2000.py')
Copy-Item -Force (Join-Path $PayloadRoot 'service\vector_service.py') (Join-Path $InstallRoot 'service\vector_service.py')
Copy-Item -Force (Join-Path $PayloadRoot 'winkey-emulator\winkey_emulator.py') (Join-Path $InstallRoot 'winkey-emulator\winkey_emulator.py')
Copy-Item -Force (Join-Path $PayloadRoot 'winkey-emulator\winkey_service.py') (Join-Path $InstallRoot 'winkey-emulator\winkey_service.py')
Copy-Item -Force (Join-Path $PayloadRoot 'winkey-emulator\run-winkey-emulator.ps1') (Join-Path $InstallRoot 'winkey-emulator\run-winkey-emulator.ps1')

$vectorConfig = @"
; GADX Vector network-client profile. Managed by installer/network-client.
[cat]
ports = $VectorCatPort
baud = 19200

[radio_keying]
; This client never opens a physical keying port.
port =
baud = 19200
ptt_line = NONE
cw_line = NONE

[rig]
host = $RigHost
port = $RigPort
poll_ms = 250

[runtime]
allow_write = true
allow_ptt = false
allow_cw = false

[service]
startup = delayed-auto
recovery = restart

[logging]
level = INFO
max_mb = 5
backups = 5

[ports]
application_start = 15
vector_start = 101
"@
Write-Utf8NoBom $VectorIni $vectorConfig

$winkeyConfig = @"
; GADX WinKey network-client profile. Separate from vector.ini.
[winkey]
port = $EmulatorWinKeyPort
baud = 1200
text_gap_ms = 15
max_message_chars = 240
firmware_revision = 23
initial_wpm = 22
min_wpm = 5
max_wpm = 60

[rigctld]
host = $RigHost
port = $RigPort
timeout_ms = 1500
abort_mode = none

[safety]
allow_transmit = $($EnableWinKeyTransmit.IsPresent.ToString().ToLowerInvariant())

[logging]
log_text = true
protocol_trace = false
max_mb = 5
backups = 5
"@
Write-Utf8NoBom (Join-Path $InstallRoot 'winkey-emulator\winkey.ini') $winkeyConfig

$marker = [ordered]@{
    format = 1
    profile = 'network-cat-winkey'
    rig_host = $RigHost
    rig_port = $RigPort
    n1mm_cat_port = $N1mmCatPort
    vector_cat_port = $VectorCatPort
    n1mm_winkey_port = $N1mmWinKeyPort
    emulator_winkey_port = $EmulatorWinKeyPort
    winkey_transmit = $EnableWinKeyTransmit.IsPresent
    configured_utc = [DateTime]::UtcNow.ToString('o')
}
Write-Utf8NoBom $NetworkMarker ($marker | ConvertTo-Json -Depth 4)

$rebootNeeded = (Ensure-VirtualPair $com0com $N1mmCatPort $VectorCatPort)
$rebootNeeded = (Ensure-VirtualPair $com0com $N1mmWinKeyPort $EmulatorWinKeyPort) -or $rebootNeeded
if ($rebootNeeded) {
    Set-Content -LiteralPath $RebootMarker -Value 'Virtual COM pairs were created; reboot Windows, then run the same command again.' -Encoding ASCII
    Write-Host "REBOOT_REQUIRED: reinicie o Windows e execute o mesmo comando novamente." -ForegroundColor Yellow
    exit 5
}
Remove-Item -LiteralPath $RebootMarker -Force -ErrorAction SilentlyContinue

& $Python -c "import serial, win32serviceutil, servicemanager" 2>$null
if ($LASTEXITCODE -ne 0) { throw "O runtime privado nao possui pyserial/pywin32." }

Install-ManagedService 'GADXVectorHub' (Join-Path $InstallRoot 'service\vector_service.py')
Install-ManagedService 'GADXWinKeyEmulator' (Join-Path $InstallRoot 'winkey-emulator\winkey_service.py')

Write-Host ""
Write-Host "NETWORK_CLIENT_READY" -ForegroundColor Green
Write-Host "N1MM CAT    : configure TS-2000 em $N1mmCatPort @ 19200 8N1"
Write-Host "N1MM WinKey : configure WinKey em $N1mmWinKeyPort @ 1200 8N1"
Write-Host "Vector log  : $(Join-Path $InstallRoot 'logs\vector-hub.log')"
Write-Host "WinKey log  : $(Join-Path $InstallRoot 'logs\winkey-emulator.log')"
if (-not $EnableWinKeyTransmit) {
    Write-Host "WinKey esta em modo sem RF. Reexecute com -EnableWinKeyTransmit apos validar CAT e o handshake N1MM." -ForegroundColor Yellow
}
