$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Execute este script como Administrador."
}

$serviceScript = Join-Path $env:ProgramFiles "GADX Vector\service\vector_bridge_service.py"
if (-not (Test-Path $serviceScript)) {
    throw "Nao encontrei $serviceScript"
}

& python $serviceScript stop 2>$null | Out-Null
& python $serviceScript remove
Write-Host "Servico GADX Vector Bridge removido. As portas COM virtuais e arquivos de configuracao foram preservados." -ForegroundColor Green
