param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector"
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

function Get-FirmwareMode {
    try {
        $value = (Get-ItemProperty -LiteralPath "HKLM:\SYSTEM\CurrentControlSet\Control" -Name PEFirmwareType -ErrorAction Stop).PEFirmwareType
        switch ([int]$value) {
            1 { return "BIOS" }
            2 { return "UEFI" }
        }
    }
    catch {}

    try {
        $info = Get-ComputerInfo -Property BiosFirmwareType -ErrorAction Stop
        $value = [string]$info.BiosFirmwareType
        if ($value -match 'UEFI') { return "UEFI" }
        if ($value -match 'Legacy|BIOS') { return "BIOS" }
    }
    catch {}

    return "UNKNOWN"
}

function Get-SecureBootState([string]$Firmware) {
    if ($Firmware -eq "BIOS") { return "NOT APPLICABLE (legacy BIOS)" }
    $cmd = Get-Command Confirm-SecureBootUEFI -ErrorAction SilentlyContinue
    if (-not $cmd) { return "UNAVAILABLE" }
    try {
        if (Confirm-SecureBootUEFI) { return "ENABLED" }
        return "DISABLED"
    }
    catch {
        $message = $_.Exception.Message
        if ($message -match 'not supported|unsupported|nao.*suport|não.*suport|0xC0000002') { return "UNSUPPORTED" }
        return "UNKNOWN: $message"
    }
}

function Get-RebootPendingDetail {
    $reasons = New-Object System.Collections.Generic.List[string]

    if (Test-Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending") {
        [void]$reasons.Add("CBS RebootPending")
    }
    if (Test-Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired") {
        [void]$reasons.Add("Windows Update RebootRequired")
    }
    try {
        $p = Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager" -Name PendingFileRenameOperations -ErrorAction SilentlyContinue
        if ($p.PendingFileRenameOperations) {
            $count = @($p.PendingFileRenameOperations).Count
            [void]$reasons.Add("PendingFileRenameOperations ($count entries)")
        }
    }
    catch {}

    return [ordered]@{
        pending = ($reasons.Count -gt 0)
        reasons = @($reasons.ToArray())
    }
}

$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_ComputerSystem
$ps = $PSVersionTable.PSVersion.ToString()
$firmware = Get-FirmwareMode
$secureBoot = Get-SecureBootState $firmware
$reboot = Get-RebootPendingDetail

$com0comSetup = $null
foreach ($candidate in @(
    "C:\Ham\com0com\setupc.exe",
    "$env:ProgramFiles\com0com\setupc.exe",
    "${env:ProgramFiles(x86)}\com0com\setupc.exe"
)) {
    if ($candidate -and (Test-Path $candidate -PathType Leaf)) {
        $com0comSetup = (Resolve-Path $candidate).Path
        break
    }
}

$lockedCom0comVersion = $null
$dependencyLockPath = Join-Path $InstallerRoot "dependency-lock.json"
if (Test-Path $dependencyLockPath -PathType Leaf) {
    try {
        $dependencyLock = Get-Content -LiteralPath $dependencyLockPath -Raw | ConvertFrom-Json
        if ($dependencyLock.com0com.version) { $lockedCom0comVersion = [string]$dependencyLock.com0com.version }
    }
    catch {}
}

Write-Host ""
Write-Host "GADX Vector - D8G host compatibility inventory" -ForegroundColor Cyan
Write-Host "Install root   : $InstallRoot"
Write-Host "Computer       : $env:COMPUTERNAME"
Write-Host "Manufacturer   : $([string]$cs.Manufacturer)"
Write-Host "Model          : $([string]$cs.Model)"
Write-Host "Windows        : $([string]$os.Caption)"
Write-Host "Version        : $([string]$os.Version)"
Write-Host "Build          : $([string]$os.BuildNumber)"
Write-Host "Architecture   : $([string]$os.OSArchitecture)"
Write-Host "64-bit OS      : $([Environment]::Is64BitOperatingSystem)"
Write-Host "PowerShell     : $ps"
Write-Host "Firmware       : $firmware"
Write-Host "Secure Boot    : $secureBoot"
Write-Host "Reboot pending : $([bool]$reboot.pending)"
if ($reboot.reasons.Count -gt 0) {
    foreach ($reason in @($reboot.reasons)) { Write-Host "  reboot reason: $reason" }
}
Write-Host "com0com setup  : $(if ($com0comSetup) { $com0comSetup } else { 'NOT FOUND' })"

if ($com0comSetup) {
    $version = [string](Get-Item -LiteralPath $com0comSetup).VersionInfo.FileVersion
    if ($version) {
        Write-Host "com0com file   : $version"
    }
    elseif ($lockedCom0comVersion) {
        Write-Host "com0com file   : metadata blank; dependency lock=$lockedCom0comVersion"
    }
    else {
        Write-Host "com0com file   : metadata blank"
    }
}

$releasePath = Join-Path $InstallerRoot "release.json"
if (Test-Path $releasePath -PathType Leaf) {
    try {
        $release = Get-Content -LiteralPath $releasePath -Raw | ConvertFrom-Json
        Write-Host "Release        : $([string]$release.version) / $([string]$release.channel) / $([string]$release.phase)"
    }
    catch {
        Write-Host "Release        : INVALID release.json"
    }
}

Write-Host ""
Write-Host "D8G_HOST_COMPATIBILITY_INVENTORY_OK" -ForegroundColor Green
