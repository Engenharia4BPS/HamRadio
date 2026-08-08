param([Parameter(Mandatory=$true)][string]$InstallRoot)

$ErrorActionPreference = "SilentlyContinue"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$PythonExe = Join-Path $InstallRoot "runtime\python.exe"
$ServiceScript = Join-Path $InstallRoot "service\vector_bridge_service.py"

if ((Test-Path $PythonExe) -and (Test-Path $ServiceScript)) {
    & $PythonExe $ServiceScript stop | Out-Null
    & $PythonExe $ServiceScript remove | Out-Null
}

# COM pairs are intentionally preserved on uninstall for v0.1.
# Removing a serial driver/COM allocation automatically is riskier than leaving
# two inert pairs behind. A future installer can own pair IDs explicitly and
# safely remove only the pairs it created.

exit 0
