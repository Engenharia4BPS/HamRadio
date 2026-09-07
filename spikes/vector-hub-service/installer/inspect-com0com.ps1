param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector"
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

function Get-Sha256([string]$Path) {
    if (-not (Test-Path $Path -PathType Leaf)) { return $null }
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Get-SignatureSummary([string]$Path) {
    if (-not (Test-Path $Path -PathType Leaf)) { return $null }
    try {
        $sig = Get-AuthenticodeSignature -LiteralPath $Path
        $subject = if ($sig.SignerCertificate) { [string]$sig.SignerCertificate.Subject } else { "" }
        return [pscustomobject]@{
            status = [string]$sig.Status
            signer = $subject
        }
    }
    catch {
        return [pscustomobject]@{
            status = "ERROR"
            signer = $_.Exception.Message
        }
    }
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
    return $null
}

$setupc = Find-Com0comSetup
$installDir = if ($setupc) { Split-Path -Parent $setupc } else { $null }

$installerCandidates = New-Object System.Collections.Generic.List[string]
foreach ($candidate in @(
    (Join-Path $InstallRoot "thirdparty\Setup_com0com_v3.0.0.0_W7_x64_signed.exe"),
    (Join-Path $InstallRoot "thirdparty\com0com-installer.exe"),
    (Join-Path $InstallerRoot "thirdparty\Setup_com0com_v3.0.0.0_W7_x64_signed.exe"),
    (Join-Path $InstallerRoot "thirdparty\com0com-installer.exe")
)) {
    if ($candidate -and (Test-Path $candidate -PathType Leaf)) {
        [void]$installerCandidates.Add((Resolve-Path $candidate).Path)
    }
}

$uninstallEntries = New-Object System.Collections.Generic.List[object]
foreach ($root in @(
    'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall',
    'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall',
    'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'
)) {
    if (-not (Test-Path $root)) { continue }
    foreach ($key in @(Get-ChildItem -LiteralPath $root -ErrorAction SilentlyContinue)) {
        try {
            $p = Get-ItemProperty -LiteralPath $key.PSPath -ErrorAction SilentlyContinue
            $name = [string]$p.DisplayName
            if ($name -and $name -match '(?i)com0com') {
                $uninstallEntries.Add([pscustomobject]@{
                    display_name = $name
                    display_version = [string]$p.DisplayVersion
                    publisher = [string]$p.Publisher
                    install_location = [string]$p.InstallLocation
                    uninstall_string = [string]$p.UninstallString
                }) | Out-Null
            }
        }
        catch {}
    }
}

$drivers = New-Object System.Collections.Generic.List[object]
try {
    foreach ($d in @(Get-CimInstance Win32_PnPSignedDriver -ErrorAction SilentlyContinue)) {
        $text = (([string]$d.DeviceName) + ' ' + ([string]$d.DriverProviderName) + ' ' + ([string]$d.InfName))
        if ($text -match '(?i)(com0com|com0|cnca|cncb)') {
            $drivers.Add([pscustomobject]@{
                device_name = [string]$d.DeviceName
                provider = [string]$d.DriverProviderName
                driver_version = [string]$d.DriverVersion
                inf_name = [string]$d.InfName
                is_signed = [bool]$d.IsSigned
                signer = [string]$d.Signer
            }) | Out-Null
        }
    }
}
catch {}

$installedFiles = New-Object System.Collections.Generic.List[object]
if ($installDir -and (Test-Path $installDir -PathType Container)) {
    foreach ($file in @(Get-ChildItem -LiteralPath $installDir -File -ErrorAction SilentlyContinue | Sort-Object Name)) {
        if ($file.Extension -in @('.exe','.dll','.sys')) {
            $version = [string]$file.VersionInfo.FileVersion
            $sig = Get-SignatureSummary $file.FullName
            $installedFiles.Add([pscustomobject]@{
                name = $file.Name
                size = [int64]$file.Length
                file_version = $version
                sha256 = Get-Sha256 $file.FullName
                signature_status = if ($sig) { $sig.status } else { "" }
                signer = if ($sig) { $sig.signer } else { "" }
            }) | Out-Null
        }
    }
}

$bundledInstallers = New-Object System.Collections.Generic.List[object]
foreach ($path in $installerCandidates) {
    $file = Get-Item -LiteralPath $path
    $sig = Get-SignatureSummary $path
    $bundledInstallers.Add([pscustomobject]@{
        path = $path
        size = [int64]$file.Length
        file_version = [string]$file.VersionInfo.FileVersion
        sha256 = Get-Sha256 $path
        signature_status = if ($sig) { $sig.status } else { "" }
        signer = if ($sig) { $sig.signer } else { "" }
    }) | Out-Null
}

$result = [ordered]@{
    format = 1
    setupc = $setupc
    install_directory = $installDir
    uninstall_entries = @($uninstallEntries)
    signed_drivers = @($drivers)
    installed_binary_files = @($installedFiles)
    bundled_installer_candidates = @($bundledInstallers)
}

Write-Host ""
Write-Host "GADX Vector - com0com read-only inventory" -ForegroundColor Cyan
Write-Host "setupc        : $(if ($setupc) { $setupc } else { 'NOT FOUND' })"
Write-Host "install dir   : $(if ($installDir) { $installDir } else { 'NOT FOUND' })"
Write-Host "registry rows : $($uninstallEntries.Count)"
Write-Host "driver rows   : $($drivers.Count)"
Write-Host "binary files  : $($installedFiles.Count)"
Write-Host "installer file: $($bundledInstallers.Count) candidate(s)"
Write-Host ""

$result | ConvertTo-Json -Depth 8
Write-Host ""
Write-Host "COM0COM_INVENTORY_OK" -ForegroundColor Green
