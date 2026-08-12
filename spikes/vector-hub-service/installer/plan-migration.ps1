param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector",
    [switch]$AsJson
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)

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
            $key = $matches[1].Trim().ToLowerInvariant()
            $value = $matches[2].Trim()
            $data[$section][$key] = $value
        }
    }
    return $data
}

function Get-IniValue($Ini,[string]$Section,[string]$Key,$Default=$null) {
    $s = $Section.ToLowerInvariant(); $k = $Key.ToLowerInvariant()
    if ($Ini.Contains($s) -and $Ini[$s].Contains($k)) { return $Ini[$s][$k] }
    return $Default
}

function Split-List([string]$Value) {
    if (-not $Value) { return @() }
    return @($Value.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}

$legacyCandidates = @(
    Join-Path $InstallRoot "config\bridge_multi.ini",
    Join-Path $InstallRoot "config\bridge.ini",
    Join-Path $InstallRoot "config\logger.ini"
)
$legacyExisting = @($legacyCandidates | Where-Object { Test-Path $_ -PathType Leaf })
if ($legacyExisting.Count -eq 0) { throw "No legacy INI files were found under $InstallRoot\config." }

# Prefer bridge_multi.ini because it represents the latest legacy multi-client model.
$sourcePath = $legacyExisting | Where-Object { $_ -like '*bridge_multi.ini' } | Select-Object -First 1
if (-not $sourcePath) { $sourcePath = $legacyExisting | Where-Object { $_ -like '*bridge.ini' } | Select-Object -First 1 }
if (-not $sourcePath) { $sourcePath = $legacyExisting[0] }
$ini = Read-Ini $sourcePath

$catPorts = Split-List (Get-IniValue $ini "cat" "ports" "")
$catBaud = Get-IniValue $ini "cat" "baud" $null
if (-not $catPorts.Count) {
    $singleCat = Get-IniValue $ini "bridge" "port" $null
    if ($singleCat) { $catPorts = @($singleCat) }
    if (-not $catBaud) { $catBaud = Get-IniValue $ini "bridge" "baud" "19200" }
}
if (-not $catBaud) { $catBaud = "19200" }

$keying = @()
if ($ini.Contains("keying")) {
    foreach ($entry in $ini["keying"].GetEnumerator()) {
        $parts = Split-List $entry.Value
        if ($parts.Count -ge 3) {
            $keying += [ordered]@{ id=$entry.Key; name=$entry.Key; port=$parts[0]; ptt=$parts[1]; cw=$parts[2] }
        }
    }
}
if (-not $keying.Count) {
    $kp = Get-IniValue $ini "bridge" "keying_port" $null
    if ($kp) {
        $keying += [ordered]@{ id="client1"; name="client1"; port=$kp; ptt="DTR"; cw="RTS" }
    }
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

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path $InstallRoot ("config\legacy\" + $stamp)
$targetIni = Join-Path $InstallRoot "config\vector.ini"

$warnings = New-Object System.Collections.Generic.List[string]
if (-not $catPorts.Count) { $warnings.Add("No CAT ports could be inferred from the legacy INI.") }
if (-not $keying.Count) { $warnings.Add("No keying clients could be inferred from the legacy INI.") }
if (-not $radioPort) { $warnings.Add("No physical radio keying port could be inferred; Port Manager/manual review will be required.") }

$result = [ordered]@{
    schema_version = 1
    mode = "PREVIEW_ONLY"
    install_root = $InstallRoot
    source_ini = $sourcePath
    legacy_files = $legacyExisting
    backup_directory = $backupDir
    target_ini = $targetIni
    preserve_com0com = $true
    cat = [ordered]@{ ports=$catPorts; baud=$catBaud }
    keying = $keying
    radio_keying = [ordered]@{ port=$radioPort; baud=$radioBaud; ptt_line=$pttLine; cw_line=$cwLine }
    rig = [ordered]@{ host=$rigHost; port=$rigPort; poll_ms=$pollMs }
    runtime = [ordered]@{ allow_write=$allowWrite; allow_ptt=$allowPtt; allow_cw=$allowCw }
    service = [ordered]@{ old="GADXVectorBridge"; new="GADXVectorHub" }
    warnings = @($warnings)
}

if ($AsJson) { $result | ConvertTo-Json -Depth 8; exit 0 }

Write-Host ""
Write-Host "GADX Vector - Legacy migration planner" -ForegroundColor Cyan
Write-Host "MODE         : PREVIEW ONLY - no files or services will be changed" -ForegroundColor Yellow
Write-Host "Install root : $InstallRoot"
Write-Host "Source INI   : $sourcePath"
Write-Host "Backup to    : $backupDir"
Write-Host "Target INI   : $targetIni"
Write-Host ""
Write-Host "CAT:"
if ($catPorts.Count) { Write-Host ("  ports : " + ($catPorts -join ', ')); Write-Host "  baud  : $catBaud" } else { Write-Host "  (not detected)" }
Write-Host ""
Write-Host "KEYING:"
if ($keying.Count) {
    foreach ($k in $keying) { Write-Host ("  {0}: {1} PTT={2} CW={3}" -f $k.id,$k.port,$k.ptt,$k.cw) }
} else { Write-Host "  (not detected)" }
Write-Host ""
Write-Host "RADIO KEYING:"
Write-Host "  port : $radioPort"
Write-Host "  baud : $radioBaud"
Write-Host "  PTT  : $pttLine"
Write-Host "  CW   : $cwLine"
Write-Host ""
Write-Host "RIGCTLD:"
Write-Host "  $rigHost`:$rigPort  poll=$pollMs ms"
Write-Host ""
Write-Host "COM0COM:"
Write-Host "  Existing pairs will be PRESERVED. This planner does not create or remove COM ports."
Write-Host ""
Write-Host "SERVICE:"
Write-Host "  GADXVectorBridge -> GADXVectorHub"
if ($warnings.Count) {
    Write-Host ""
    Write-Host "Warnings:" -ForegroundColor Yellow
    foreach ($w in $warnings) { Write-Host "  ! $w" }
}
Write-Host ""
Write-Host "No changes were made." -ForegroundColor Green
Write-Host ""
$result
