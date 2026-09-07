param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector"
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SetupScript = Join-Path $InstallerRoot "setup-vector.ps1"
$DetectScript = Join-Path $InstallerRoot "detect-installation.ps1"
$PlanScript = Join-Path $InstallerRoot "plan-migration.ps1"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this script from an elevated PowerShell prompt."
    }
}

function Get-RealState {
    $raw = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $SetupScript -InstallRoot $InstallRoot -AsJson 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Could not read real installation state." }
    return (($raw | Out-String).Trim() | ConvertFrom-Json)
}

function Write-Utf8NoBom([string]$Path,[string]$Text) {
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path,$Text,$utf8)
}

Assert-Administrator

foreach ($path in @($SetupScript,$DetectScript,$PlanScript)) {
    if (-not (Test-Path $path -PathType Leaf)) { throw "Required test component is missing: $path" }
}

$before = Get-RealState
$beforeService = Get-Service -Name "GADXVectorHub" -ErrorAction SilentlyContinue
$beforeServiceStatus = if ($beforeService) { [string]$beforeService.Status } else { "not installed" }
$beforeConfigHash = $null
$realConfig = Join-Path $InstallRoot "config\vector.ini"
if (Test-Path $realConfig -PathType Leaf) {
    $beforeConfigHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $realConfig).Hash
}

$tempRoot = Join-Path $env:TEMP ("GADX-Vector-d8g-legacy-" + [Guid]::NewGuid().ToString("N"))
$tempConfig = Join-Path $tempRoot "config"
$legacyIni = Join-Path $tempConfig "bridge_multi.ini"

$legacyText = @"
[cat]
ports = COM9,COM15
baud = 19200

[keying]
client1 = COM29,DTR,RTS
client2 = COM30,DTR,RTS

[radio_keying]
port = COM22
baud = 9600
ptt_line = RIGCTLD
cw_line = RTS

[rig]
host = 127.0.0.1
port = 4532
poll_ms = 250

[bridge]
allow_write = true
allow_ptt = true
allow_cw = true
"@

Write-Host ""
Write-Host "GADX Vector - D8G legacy migration Preview validation" -ForegroundColor Cyan
Write-Host "Real install : $InstallRoot"
Write-Host "Fixture      : $tempRoot"
Write-Host "Safety       : temporary legacy INI + Preview only; real service/config/COMs are not modified"
Write-Host ""

try {
    New-Item -ItemType Directory -Force -Path $tempConfig | Out-Null
    Write-Utf8NoBom $legacyIni $legacyText
    $legacyHashBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $legacyIni).Hash

    Write-Host "[1/3] Detecting isolated legacy fixture..."
    $detectRaw = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $DetectScript -InstallRoot $tempRoot -AsJson 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Legacy fixture detector failed." }
    $fixtureState = (($detectRaw | Out-String).Trim() | ConvertFrom-Json)

    Write-Host "  Detected    : $([string]$fixtureState.classification)"
    Write-Host "  Recommended : $([string]$fixtureState.recommended_mode)"
    if ([string]$fixtureState.classification -ne 'LEGACY') { throw "Fixture was not detected as LEGACY." }
    if (-not [bool]$fixtureState.migration_required) { throw "Legacy fixture did not require migration." }
    if ([string]$fixtureState.recommended_mode -notin @('MIGRATE','MIGRATE_REPAIR')) { throw "Legacy fixture did not recommend a migration mode." }
    Write-Host "D8G_LEGACY_FIXTURE_DETECTED" -ForegroundColor Green

    Write-Host ""
    Write-Host "[2/3] Validating production legacy migration plan..."
    $planRaw = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $PlanScript -InstallRoot $tempRoot -AsJson 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Legacy migration planner failed." }
    $plan = (($planRaw | Out-String).Trim() | ConvertFrom-Json)

    $catPorts = @($plan.cat.ports)
    $keying = @($plan.keying)
    $planOk = (
        [bool]$plan.preserve_com0com -and
        $catPorts.Count -eq 2 -and
        $catPorts[0] -eq 'COM9' -and
        $catPorts[1] -eq 'COM15' -and
        $keying.Count -eq 2 -and
        [string]$plan.radio_keying.port -eq 'COM22' -and
        [string]$plan.radio_keying.ptt_line -eq 'RIGCTLD' -and
        [string]$plan.radio_keying.cw_line -eq 'RTS' -and
        [string]$plan.rig.host -eq '127.0.0.1' -and
        [string]$plan.rig.port -eq '4532' -and
        [string]$plan.service.old -eq 'GADXVectorBridge' -and
        [string]$plan.service.new -eq 'GADXVectorHub'
    )
    if (-not $planOk) { throw "Legacy migration plan did not preserve the expected fixture settings." }

    Write-Host "  CAT          : $($catPorts -join ', ')"
    Write-Host "  Keying       : $($keying.Count) clients"
    Write-Host "  Radio keying : $([string]$plan.radio_keying.port) PTT=$([string]$plan.radio_keying.ptt_line) CW=$([string]$plan.radio_keying.cw_line)"
    Write-Host "  rigctld      : $([string]$plan.rig.host):$([string]$plan.rig.port)"
    Write-Host "  com0com      : preserve existing pairs"
    Write-Host "D8G_LEGACY_PLAN_OK" -ForegroundColor Green

    Write-Host ""
    Write-Host "[3/3] Running full production Setup Preview against legacy fixture..."
    Write-Host ""
    $output = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $SetupScript -InstallRoot $tempRoot 2>&1
    $exitCode = $LASTEXITCODE
    $text = ($output | Out-String).TrimEnd()
    Write-Host $text

    if ($exitCode -ne 0) { throw "Legacy fixture Preview failed with exit code $exitCode." }
    if ($text -notmatch '(?m)^Detected\s+:\s+LEGACY\s*$') { throw "Setup Preview did not report LEGACY." }
    if ($text -notmatch '(?m)^Mode\s+:\s+MIGRATE(_REPAIR)?\s*$') { throw "Setup Preview did not recommend migration." }
    if ($text -notmatch 'Legacy migration planner') { throw "Setup Preview did not invoke the legacy migration planner." }
    if ($text -notmatch 'Existing pairs will be PRESERVED') { throw "Setup Preview did not expose COM-pair preservation." }
    if ($text -notmatch 'PREVIEW complete') { throw "Setup Preview completion marker was not found." }

    if (Test-Path (Join-Path $tempConfig "vector.ini") -PathType Leaf) {
        throw "Preview unexpectedly created vector.ini inside the legacy fixture."
    }
    $legacyHashAfter = (Get-FileHash -Algorithm SHA256 -LiteralPath $legacyIni).Hash
    if ($legacyHashBefore -ne $legacyHashAfter) { throw "Preview changed the legacy fixture INI." }

    $after = Get-RealState
    $afterService = Get-Service -Name "GADXVectorHub" -ErrorAction SilentlyContinue
    $afterServiceStatus = if ($afterService) { [string]$afterService.Status } else { "not installed" }
    $afterConfigHash = $null
    if (Test-Path $realConfig -PathType Leaf) {
        $afterConfigHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $realConfig).Hash
    }

    $realStateOk = (
        [string]$before.classification -eq [string]$after.classification -and
        [string]$before.recommended_mode -eq [string]$after.recommended_mode -and
        [bool]$before.payload_drift -eq [bool]$after.payload_drift
    )
    $serviceOk = ($beforeServiceStatus -eq $afterServiceStatus)
    $configOk = ($beforeConfigHash -eq $afterConfigHash)

    Write-Host ""
    Write-Host "Real installation after legacy fixture Preview:" -ForegroundColor Cyan
    Write-Host "  Detected      : $([string]$after.classification)"
    Write-Host "  Recommended   : $([string]$after.recommended_mode)"
    Write-Host "  Payload drift : $(if ([bool]$after.payload_drift) { 'YES' } else { 'NO' })"
    Write-Host "  Service       : $afterServiceStatus"
    Write-Host "  vector.ini    : $(if ($configOk) { 'SHA256 unchanged' } else { 'CHANGED' })"

    if (-not $realStateOk) { throw "Real installation detector state changed during legacy fixture Preview." }
    if (-not $serviceOk) { throw "Real GADXVectorHub service status changed during legacy fixture Preview." }
    if (-not $configOk) { throw "Real vector.ini changed during legacy fixture Preview." }

    Write-Host ""
    Write-Host "D8G_LEGACY_PREVIEW_SAFE" -ForegroundColor Green
}
finally {
    if (Test-Path $tempRoot -PathType Container) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
