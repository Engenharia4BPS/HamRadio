[CmdletBinding()]
param(
    [string]$Config = (Join-Path $PSScriptRoot "winkey.ini"),
    [switch]$Check
)

$ErrorActionPreference = "Stop"

# Reuse the Vector private runtime, but do not install a service, change
# vector.ini, create COM pairs, or start/stop GADXVectorHub.
$vectorRoot = "C:\Ham\GADX-Vector"
$python = Join-Path $vectorRoot "runtime\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "GADX Vector private runtime was not found: $python"
}
if (-not (Test-Path -LiteralPath $Config -PathType Leaf)) {
    throw "WinKey configuration was not found: $Config. Copy winkey.ini.example to winkey.ini first."
}

$arguments = @((Join-Path $PSScriptRoot "winkey_emulator.py"), "--config", $Config)
if ($Check) { $arguments += "--check" }
& $python @arguments
exit $LASTEXITCODE
