@echo off
setlocal EnableExtensions
set "PACKAGE_DIR=%~dp0"
set "SILENT_LAUNCHER=%~dp0START_MULTI_DEV_SILENT.ps1"

if not exist "%SILENT_LAUNCHER%" (
  echo [LOI] Thieu START_MULTI_DEV_SILENT.ps1
  pause
  exit /b 1
)

rem Detach immediately so the CMD window does not remain on the taskbar while
rem Multi is running. START_MULTI_DEV_SILENT.ps1 owns validation and writes
rem host stdout/stderr under data-dev\logs.
start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%SILENT_LAUNCHER%"
endlocal
exit /b 0
