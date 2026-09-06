@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-launcher.ps1" -InstallRoot "C:\Ham\GADX-Vector"
exit /b %ERRORLEVEL%
