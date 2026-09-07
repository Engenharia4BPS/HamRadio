param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector"
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$PythonExe = Join-Path $InstallRoot "runtime\python.exe"
$PortManager = Join-Path $InstallRoot "tools\port_manager.py"
$ConfigPath = Join-Path $InstallRoot "config\vector.ini"

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Administrator)) {
    $args = @(
        '-NoProfile',
        '-ExecutionPolicy','Bypass',
        '-File',("`"{0}`"" -f $PSCommandPath),
        '-InstallRoot',("`"{0}`"" -f $InstallRoot)
    )
    Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList $args | Out-Null
    exit 0
}

if (-not (Test-Path $PythonExe -PathType Leaf)) {
    throw "Vector private Python runtime was not found: $PythonExe"
}
if (-not (Test-Path $PortManager -PathType Leaf)) {
    throw "Vector Port Manager was not found: $PortManager"
}
if (-not (Test-Path $ConfigPath -PathType Leaf)) {
    throw "Vector configuration was not found: $ConfigPath"
}

$oldInstallRoot = $env:GADX_VECTOR_INSTALL_ROOT
try {
    $env:GADX_VECTOR_INSTALL_ROOT = $InstallRoot
    Write-Host "GADX Vector - Port Manager launcher" -ForegroundColor Cyan
    Write-Host "Install root : $InstallRoot"
    Write-Host "Python       : $PythonExe"
    Write-Host "Port Manager : $PortManager"
    Write-Host "Config       : $ConfigPath"
    Write-Host ""
    Write-Host "Opening Port Manager. No COM/config changes occur until Apply configuration is confirmed inside the tool."

    Start-Process -FilePath $PythonExe -ArgumentList @($PortManager) -WorkingDirectory (Split-Path -Parent $PortManager) | Out-Null
    Write-Host "PORT_MANAGER_LAUNCHED" -ForegroundColor Green
}
finally {
    $env:GADX_VECTOR_INSTALL_ROOT = $oldInstallRoot
}
