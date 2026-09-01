@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title KVTM RECIPE 6-6-8 - READ ONLY PROBE

set "AUTO_ROOT=dist\KVTM-ClientJS-Suite-Multi-DEV\AUTO_PRO"
set "PROBE=components\clientjs-auto\worker\recipe_668_probe.py"
set "OUT=data-machine-diagnostic\recipe-668-runtime.json"

echo ===============================================================================
echo  KIEM TRA RUNTIME CONG THUC 6 TDHH + 6 VAI VANG + 8 TAO SAY
echo  READ-ONLY: khong click, khong swipe, khong mo game, khong sua profile.
echo ===============================================================================
if not exist "%PROBE%" (
  echo [FAIL] Thieu %PROBE%
  pause
  exit /b 1
)
if not exist "%AUTO_ROOT%\local_launcher.py" (
  echo [FAIL] Thieu runtime AUTO_PRO: %AUTO_ROOT%
  pause
  exit /b 1
)
py -3.11 "%PROBE%" --auto-root "%AUTO_ROOT%" --output "%OUT%"
if errorlevel 1 (
  echo.
  echo [FAIL] Probe runtime that bai. Gui output nay cho ChatGPT.
  pause
  exit /b 1
)
echo.
echo [PASS] Da tao report READ-ONLY:
echo %CD%\%OUT%
echo Gui file JSON nay cho ChatGPT. File khong chua profile/token/cookie/password.
pause
exit /b 0
