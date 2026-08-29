@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0BUILD_CLEAN_BUNDLE.ps1"
if errorlevel 1 (
  echo.
  echo CLEAN BUNDLE BUILD FAILED.
  pause
  exit /b 1
)
echo.
echo CLEAN BUNDLE BUILD PASSED.
pause
exit /b 0
