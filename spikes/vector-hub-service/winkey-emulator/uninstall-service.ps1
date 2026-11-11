param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector"
)

$ErrorActionPreference = "Stop"
$Python = Join-Path ([System.IO.Path]::GetFullPath($InstallRoot)) "runtime\python.exe"
$ServiceScript = Join-Path ([System.IO.Path]::GetFullPath($InstallRoot)) "winkey-emulator\winkey_service.py"
if (-not (Test-Path $Python)) { throw "Python privado nao encontrado: $Python" }
if (-not (Test-Path $ServiceScript)) { throw "Service script nao encontrado: $ServiceScript" }
try { Stop-Service GADXWinKeyEmulator -Force -ErrorAction SilentlyContinue } catch {}
Start-Sleep -Milliseconds 500
& $Python $ServiceScript remove
Write-Host "GADXWinKeyEmulator removido."
