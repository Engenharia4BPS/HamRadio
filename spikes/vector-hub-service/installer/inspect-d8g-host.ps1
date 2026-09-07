param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector"
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

function Get-SecureBootState {
    $cmd = Get-Command Confirm-SecureBootUEFI -ErrorAction SilentlyContinue
    if (-not $cmd) { return "UNAVAILABLE" }
    try {
        if (Confirm-SecureBootUEFI) { return "ENABLED" }
        return "DISABLED"
    }
    catch {
        $message = $_.Exception.Message
        if ($message -match 'not supported|unsupported|nao.*suport|não.*suport') { return "UNSUPPORTED" }
        return "UNKNOWN: $message"
    }
}

function Get-FirmwareMode {
    try {
        $value = (Get-ItemProperty -LiteralPath "HKLM:\SYSTEM\CurrentControlSet\Control" -Name PEFirmwareType -ErrorAction Stop).PEFirmwareType
        switch ([int]$value) {
            1 { return "BIOS" }
            2 { return "UEFI" }
            default { return "UNKNOWN($value)" }
        }
    }
    catch { return "UNKNOWN" }
}

function Test-RebootPending {
    if (Test-Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending") { return $true }
    if (Test-Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired") { return $true }
    try {
        $p = Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager" -Name PendingFileRenameOperations -ErrorAction SilentlyContinue
        if ($p.PendingFileRenameOperations) { return $true }
    }
    catch {}
    return $false
}

$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_ComputerSystem
$ps = $PSVersionTable.PSVersion.ToString()
$secureBoot = Get-SecureBootState
$firmware = Get-FirmwareMode
$reboot = Test-RebootPending

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
Write-Host "Reboot pending : $reboot"
Write-Host "com0com setup  : $(if ($com0comSetup) { $com0comSetup } else { 'NOT FOUND' })"

if ($com0comSetup) {
    $version = (Get-Item -LiteralPath $com0comSetup).VersionInfo.FileVersion
    Write-Host "com0com file   : $version"
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
