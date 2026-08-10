param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector"
)

$ErrorActionPreference = "Stop"
$Python = Join-Path $InstallRoot "runtime\python.exe"
$ServiceScript = Join-Path $InstallRoot "service\vector_service.py"

if (-not (Test-Path $Python)) { throw "Python privado nao encontrado: $Python" }
if (-not (Test-Path $ServiceScript)) { throw "Service script nao encontrado: $ServiceScript" }

try { Stop-Service GADXVectorHub -Force -ErrorAction SilentlyContinue } catch {}
Start-Sleep -Milliseconds 500

& $Python $ServiceScript remove

Write-Host "GADXVectorHub removido. O servico legado GADXVectorBridge nao foi alterado."
