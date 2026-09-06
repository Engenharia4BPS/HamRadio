@echo off
setlocal
set "SCRIPT=%~dp0setup-launcher.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -InstallRoot "C:\Ham\GADX-Vector" -Simulation Repair
endlocal
