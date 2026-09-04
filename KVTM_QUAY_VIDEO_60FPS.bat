@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0tools\KVTM_SCREEN_RECORDER.ps1"
if errorlevel 1 (
  echo.
  echo [FAIL] Khong mo duoc KVTM Screen Recorder.
  pause
)
endlocal
