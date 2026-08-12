param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)

if (-not $Apply) {
    throw "This script changes the installation. Re-run with -Apply only after validating plan-migration.ps1 output."
}

function Read-Ini([string]$Path) {
    $data = [ordered]@{}
    if (-not (Test-Path $Path -PathType Leaf)) { return $data }
    $section = ""
    foreach ($raw in Get-Content -LiteralPath $Path) {
        $line = $raw.Trim()
        if (-not $line -or $line.StartsWith(";") -or $line.StartsWith("#")) { continue }
        if ($line -match '^\[(.+)\]$') {
            $section = $matches[1].Trim().ToLowerInvariant()
            if (-not $data.Contains($section)) { $data[$section] = [ordered]@{} }
            continue
        }
        if ($line -match '^([^=]+)=(.*)$') {
            if (-not $section) { continue }
            $data[$section][$matches[1].Trim().ToLowerInvariant()] = $matches[2].Trim()
        }
    }
    return $data
}

function Get-IniValue($Ini,[string]$Section,[string]$Key,$Default=$null) {
    $s=$Section.ToLowerInvariant(); $k=$Key.ToLowerInvariant()
    if ($Ini.Contains($s) -and $Ini[$s].Contains($k)) { return $Ini[$s][$k] }
    return $Default
}

function Split-List([string]$Value) {
    if (-not $Value) { return @() }
    return @($Value.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}

function Write-Utf8NoBom([string]$Path,[string]$Content) {
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path,$Content,$enc)
}

$configDir = Join-Path $InstallRoot "config"
$bridgeMulti = Join-Path $configDir "bridge_multi.ini"
$bridge = Join-Path $configDir "bridge.ini"
$logger = Join-Path $configDir "logger.ini"
$targetIni = Join-Path $configDir "vector.ini"

$legacyExisting = @()
foreach ($p in @($bridgeMulti,$bridge,$logger)) {
    if (Test-Path $p -PathType Leaf) { $legacyExisting += $p }
}
if ($legacyExisting.Count -eq 0) { throw "No legacy INI files found. Nothing to migrate." }
if (Test-Path $targetIni -PathType Leaf) {
    throw "config\vector.ini already exists. Refusing legacy apply to avoid overwriting current configuration."
}

$sourcePath = $null
if (Test-Path $bridgeMulti -PathType Leaf) { $sourcePath = $bridgeMulti }
elseif (Test-Path $bridge -PathType Leaf) { $sourcePath = $bridge }
else { $sourcePath = $logger }
$ini = Read-Ini $sourcePath

$catPorts = Split-List (Get-IniValue $ini "cat" "ports" "")
$catBaud = Get-IniValue $ini "cat" "baud" $null
if (-not $catPorts.Count) {
    $singleCat = Get-IniValue $ini "bridge" "port" $null
    if ($singleCat) { $catPorts = @($singleCat) }
    if (-not $catBaud) { $catBaud = Get-IniValue $ini "bridge" "baud" "19200" }
}
if (-not $catBaud) { $catBaud = "19200" }
if (-not $catPorts.Count) { throw "Could not infer CAT ports from $sourcePath" }

$keying = @()
if ($ini.Contains("keying")) {
    foreach ($entry in $ini["keying"].GetEnumerator()) {
        $parts = Split-List $entry.Value
        if ($parts.Count -ge 3) {
            $keying += [ordered]@{ id=$entry.Key; name=("Cliente " + ($keying.Count + 1)); port=$parts[0]; ptt=$parts[1]; cw=$parts[2] }
        }
    }
}
if (-not $keying.Count) {
    $kp = Get-IniValue $ini "bridge" "keying_port" $null
    if ($kp) { $keying += [ordered]@{ id="client1"; name="Cliente 1"; port=$kp; ptt="DTR"; cw="RTS" } }
}

$radioPort = Get-IniValue $ini "radio_keying" "port" (Get-IniValue $ini "bridge" "radio_keying_port" "")
$radioBaud = Get-IniValue $ini "radio_keying" "baud" (Get-IniValue $ini "bridge" "radio_keying_baud" "19200")
$pttLine = Get-IniValue $ini "radio_keying" "ptt_line" (Get-IniValue $ini "bridge" "ptt_line" "RTS")
$cwLine = Get-IniValue $ini "radio_keying" "cw_line" (Get-IniValue $ini "bridge" "cw_line" "DTR")
$rigHost = Get-IniValue $ini "rig" "host" (Get-IniValue $ini "bridge" "rig_host" "127.0.0.1")
$rigPort = Get-IniValue $ini "rig" "port" (Get-IniValue $ini "bridge" "rig_port" "4532")
$pollMs = Get-IniValue $ini "rig" "poll_ms" (Get-IniValue $ini "bridge" "poll_ms" "250")
$allowWrite = Get-IniValue $ini "bridge" "allow_write" "true"
$allowPtt = Get-IniValue $ini "bridge" "allow_ptt" "true"
$allowCw = Get-IniValue $ini "bridge" "allow_cw" "true"
$logLevel = Get-IniValue $ini "bridge" "log_level" "INFO"
$logMaxMb = Get-IniValue $ini "bridge" "log_max_mb" "5"
$logBackups = Get-IniValue $ini "bridge" "log_backups" "5"

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path $configDir ("legacy\" + $stamp)
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
foreach ($p in $legacyExisting) {
    Copy-Item -LiteralPath $p -Destination (Join-Path $backupDir ([System.IO.Path]::GetFileName($p))) -Force
}

$keyLines = New-Object System.Collections.Generic.List[string]
for ($i=0; $i -lt $keying.Count; $i++) {
    $k = $keying[$i]
    $keyLines.Add(("client{0} = {1},{2},{3},{4}" -f ($i+1),$k.name,$k.port,$k.ptt,$k.cw))
}

$catText = $catPorts -join ", "
$keyText = if ($keyLines.Count) { $keyLines -join "`r`n" } else { "; no keying clients detected" }

$content = @"
; GADX Vector Hub
; Migrated automatically from legacy configuration on $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss').
; Source: $sourcePath
; Legacy files backed up under: $backupDir

[cat]
ports = $catText
baud = $catBaud

[keying]
; clientN = NOME,PORTA_VECTOR,PTT_INPUT,CW_INPUT
$keyText

[radio_keying]
port = $radioPort
baud = $radioBaud
ptt_line = $pttLine
cw_line = $cwLine

[rig]
host = $rigHost
port = $rigPort
poll_ms = $pollMs

[runtime]
allow_write = $allowWrite
allow_ptt = $allowPtt
allow_cw = $allowCw

[service]
startup = delayed-auto
recovery = restart

[logging]
level = $logLevel
max_mb = $logMaxMb
backups = $logBackups

[ports]
application_start = 15
vector_start = 101
"@

Write-Utf8NoBom $targetIni $content

if (-not (Test-Path $targetIni -PathType Leaf)) { throw "vector.ini was not created." }

Write-Host ""
Write-Host "GADX Vector legacy configuration migration completed." -ForegroundColor Green
Write-Host "Source       : $sourcePath"
Write-Host "Backup       : $backupDir"
Write-Host "Created      : $targetIni"
Write-Host "CAT ports    : $catText"
Write-Host "Keying count : $($keying.Count)"
Write-Host ""
Write-Host "IMPORTANT:" -ForegroundColor Yellow
Write-Host "  - Existing com0com pairs were NOT changed."
Write-Host "  - Legacy INI files were NOT deleted."
Write-Host "  - Windows services were NOT changed."
Write-Host "  - Review vector.ini and load it in Port Manager before service migration."
