$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Execute este script como Administrador."
}

Write-Host "Reiniciando GADX Vector Bridge..." -ForegroundColor Cyan
Restart-Service -Name GADXVectorBridge -Force
Get-Service -Name GADXVectorBridge | Format-Table Status, Name, DisplayName -AutoSize
