@echo off
setlocal
set "SCRIPT=%~dp0setup-repair-simulation.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -InstallRoot "C:\Ham\GADX-Vector"
if errorlevel 1 (
  echo.
  echo D8C Repair Simulation failed. Review the error above.
  pause
)
endlocal
