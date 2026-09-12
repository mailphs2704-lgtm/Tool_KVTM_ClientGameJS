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

set "DIRTY_COUNT=0"
for /f "usebackq delims=" %%L in (`git status --porcelain --untracked-files=no 2^>nul`) do set /a DIRTY_COUNT+=1
if not "%DIRTY_COUNT%"=="0" (
  echo ===============================================================================
  echo  [STOP] WORKING TREE CO TRACKED FILE DANG THAY DOI
  echo  Stable chi duoc dong tu committed HEAD sach.
  echo  Script KHONG tu reset/stash de tranh lam mat code DEV cua ban.
  echo -------------------------------------------------------------------------------
  git status --short --untracked-files=no
  echo -------------------------------------------------------------------------------
  echo  Hay kiem tra cac file tren bang:
  echo    git diff --name-status
  echo    git diff --cached --name-status
  echo.
  echo  Neu la thay doi can giu: commit/push truoc khi release.
  echo  Neu la thay doi khong can giu: restore DUNG file do, khong dung reset --hard.
  echo ===============================================================================
  pause
  exit /b 2
)

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

if not "%RC%"=="0" (
  echo.
  echo [WARN] Primary Setup packager that bai. rc=%RC%
  echo [INFO] Dang thu self-extract Setup builder doc lap IExpress...
  powershell -NoProfile -ExecutionPolicy Bypass -File ".\packaging\kvtm-tool-cry\BUILD_KVTM_TOOL_CRY_SETUP_FALLBACK.ps1"
  set "FALLBACK_RC=%ERRORLEVEL%"
  if not "%FALLBACK_RC%"=="0" (
    echo.
    echo [FAIL] Kvtm_tool_Cry release build that bai. primary=%RC% fallback=%FALLBACK_RC%
    pause
    exit /b %FALLBACK_RC%
  )
  echo [PASS] Primary IExpress bo qua; self-extract Setup VERIFIED.
)

echo.
echo [PASS] Kvtm_tool_Cry installer + local auto-update channel da san sang.
echo [INFO] Installer: dist\Kvtm_tool_Cry_Setup_*.exe
echo [INFO] Channel  : dist\Kvtm_tool_Cry-channel\stable-manifest.json
echo.
pause
exit /b 0
