@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title Kvtm_tool_Cry - STABLE RELEASE BUILDER

set "EXPECTED_BRANCH=develop/multi-auto-dev"
set "CUR_BRANCH="
for /f "delims=" %%B in ('git branch --show-current 2^>nul') do set "CUR_BRANCH=%%B"
if /I not "%CUR_BRANCH%"=="%EXPECTED_BRANCH%" (
  echo [STOP] Sai branch: %CUR_BRANCH%
  echo        Can dung: %EXPECTED_BRANCH%
  pause
  exit /b 1
)

set "VERSION_ARG="
if not "%~1"=="" set "VERSION_ARG=-Version "%~1""

echo ===============================================================================
echo  Kvtm_tool_Cry - BUILD/PUBLISH STABLE LOCAL CHANNEL
echo  DEV va Stable la 2 runtime doc lap.
echo  Lenh nay KHONG dong Kvtm_tool_Cry dang chay.
echo  Stable se nhan version moi vao LAN MO TIEP THEO.
echo ===============================================================================
echo.

if "%~1"=="" (
  powershell -NoProfile -ExecutionPolicy Bypass -File ".\packaging\kvtm-tool-cry\BUILD_KVTM_TOOL_CRY_RELEASE.ps1"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File ".\packaging\kvtm-tool-cry\BUILD_KVTM_TOOL_CRY_RELEASE.ps1" -Version "%~1"
)
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo [FAIL] Kvtm_tool_Cry release build that bai. rc=%RC%
  pause
  exit /b %RC%
)

echo [PASS] Kvtm_tool_Cry installer + local auto-update channel da san sang.
echo [INFO] Installer: dist\Kvtm_tool_Cry_Setup_*.exe
echo [INFO] Channel  : dist\Kvtm_tool_Cry-channel\stable-manifest.json
echo.
pause
exit /b 0
