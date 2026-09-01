@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title KVTM MULTI DEV - CONTROL CENTER

set "EXPECTED_BRANCH=develop/multi-auto-dev"
set "DIST=dist\KVTM-ClientJS-Suite-Multi-DEV"
set "STEP1=components\clientjs-auto\worker\clear_stall_step1_probe.py"
set "STEP1_OUT=%DIST%\data-dev\clear-stall-step1"
set "BUILD_SCRIPT=packaging\suite-v0.15\BUILD_FULL_PACKAGE.ps1"

:menu
cls
set "CUR_BRANCH="
set "CUR_HEAD="
for /f "delims=" %%B in ('git branch --show-current 2^>nul') do set "CUR_BRANCH=%%B"
for /f "delims=" %%H in ('git rev-parse --short HEAD 2^>nul') do set "CUR_HEAD=%%H"
echo ===============================================================================
echo  KVTM MULTI DEV - CONTROL CENTER
echo  MOT CUA SO DUY NHAT. Chi dung cho Tool_KVTM_Multi_DEV.
echo  Khong dieu khien GameClientJS cua bo cu.
echo ===============================================================================
echo  Repo   : %CD%
echo  Branch : %CUR_BRANCH%
echo  HEAD   : %CUR_HEAD%
echo -------------------------------------------------------------------------------
echo  [1] Cap nhat source DEV
echo  [2] Build package DEV thu cong
echo  [3] Mo Multi DEV  ^(tu build neu package cu/thieu^)
echo  [4] Don quay - BUOC HIEN TAI: STEP 1 capture bang luong AUTO chinh
echo      ^(tu build neu package cu/thieu^)
echo  [5] Mo thu muc ket qua STEP 1
echo  [0] Thoat
echo -------------------------------------------------------------------------------
set "CHOICE="
set /p "CHOICE=Chon: "
if "%CHOICE%"=="1" goto update
if "%CHOICE%"=="2" goto build
if "%CHOICE%"=="3" goto startmulti
if "%CHOICE%"=="4" goto step1
if "%CHOICE%"=="5" goto openstep1
if "%CHOICE%"=="0" goto end
goto menu

:guard_branch
set "CUR_BRANCH="
for /f "delims=" %%B in ('git branch --show-current 2^>nul') do set "CUR_BRANCH=%%B"
if /I "%CUR_BRANCH%"=="%EXPECTED_BRANCH%" exit /b 0
echo.
echo [STOP] Sai branch: %CUR_BRANCH%
echo        Can dung: %EXPECTED_BRANCH%
echo.
exit /b 1

:do_build
echo.
echo [DEV] Dang build/cap nhat fixed package DEV...
powershell -NoProfile -ExecutionPolicy Bypass -File ".\%BUILD_SCRIPT%"
if errorlevel 1 (
  echo.
  echo [LOI] Build package DEV that bai.
  exit /b 1
)
if not exist "%DIST%\Multi\kvtm_multi_dev_host.py" (
  echo [LOI] Build xong nhung van thieu Multi\kvtm_multi_dev_host.py
  exit /b 1
)
if not exist "%DIST%\.source-head.txt" (
  echo [LOI] Build xong nhung thieu .source-head.txt
  exit /b 1
)
echo [OK] Package DEV da dong bo voi source hien tai.
exit /b 0

:ensure_package
call :guard_branch
if errorlevel 1 exit /b 1
set "REPO_HEAD="
set "PACKAGE_HEAD="
for /f "delims=" %%H in ('git rev-parse HEAD 2^>nul') do set "REPO_HEAD=%%H"
if exist "%DIST%\.source-head.txt" set /p "PACKAGE_HEAD="<"%DIST%\.source-head.txt"
set "NEED_BUILD=0"
if not exist "%DIST%\02_START_MULTI_DEV.bat" set "NEED_BUILD=1"
if not exist "%DIST%\AUTO_PRO\local_launcher.py" set "NEED_BUILD=1"
if not exist "%DIST%\Multi\kvtm_multi.py" set "NEED_BUILD=1"
if not exist "%DIST%\Multi\kvtm_multi_dev_entry.py" set "NEED_BUILD=1"
if not exist "%DIST%\Multi\kvtm_multi_dev_host.py" set "NEED_BUILD=1"
if not exist "%DIST%\Multi\clear_stall_probe_console.py" set "NEED_BUILD=1"
if not exist "%DIST%\components\clientjs-auto\worker\clear_stall_step1_probe.py" set "NEED_BUILD=1"
if not defined PACKAGE_HEAD set "NEED_BUILD=1"
if /I not "%PACKAGE_HEAD%"=="%REPO_HEAD%" set "NEED_BUILD=1"
if "%NEED_BUILD%"=="0" (
  echo [OK] Package DEV da dung HEAD hien tai.
  exit /b 0
)
echo [DEV] Package dang cu/thieu. Control Center se tu build mot lan.
call :do_build
exit /b %ERRORLEVEL%

:update
call :guard_branch
if errorlevel 1 (
  pause
  goto menu
)
cls
echo [DEV] Cap nhat source tren branch %EXPECTED_BRANCH%...
echo [DEV] Tat auto-gc/maintenance de tranh prompt unlink pack file.
git -c gc.auto=0 -c maintenance.auto=false pull --ff-only origin %EXPECTED_BRANCH%
if errorlevel 1 (
  echo.
  echo [LOI] git pull that bai. Khong lam tiep.
  pause
  goto menu
)
git lfs pull
if errorlevel 1 (
  echo.
  echo [LOI] git lfs pull that bai.
  pause
  goto menu
)
echo.
git rev-parse --short HEAD
echo [OK] Source DEV da cap nhat.
echo [INFO] Khi chon [3] hoac [4], package se tu build neu can.
pause
goto menu

:build
call :guard_branch
if errorlevel 1 (
  pause
  goto menu
)
cls
call :do_build
pause
goto menu

:startmulti
cls
call :ensure_package
if errorlevel 1 (
  echo.
  echo [STOP] Khong mo Multi vi package chua hop le.
  pause
  goto menu
)
echo.
echo [DEV] Dang mo Multi DEV...
call "%DIST%\02_START_MULTI_DEV.bat"
echo.
echo [INFO] Multi DEV da dong hoac launcher da ket thuc.
pause
goto menu

:step1
cls
call :ensure_package
if errorlevel 1 (
  echo.
  echo [STOP] Khong test STEP 1 vi package chua hop le.
  pause
  goto menu
)
echo ===============================================================================
echo  DON QUAY - STEP 1 ONLY
echo  Muc tieu: dung dung bootstrap AUTO chinh, match CHI client Multi DEV, chup 1 anh.
echo  KHONG click, KHONG swipe, KHONG mua/ban, KHONG dung vao client bo cu.
echo ===============================================================================
if not exist "%STEP1%" (
  echo [LOI] Thieu %STEP1%
  pause
  goto menu
)
py -3.11 -c "import sys,struct; assert sys.version_info[:2]==(3,11) and struct.calcsize('P')*8==64" >nul 2>&1
if errorlevel 1 (
  echo [LOI] Can CPython 3.11 x64.
  py -0p
  pause
  goto menu
)
if not exist "%STEP1_OUT%" mkdir "%STEP1_OUT%" >nul 2>&1
echo [DEV] Bat dau STEP 1...
echo.
py -3.11 "%STEP1%" --auto-root "%DIST%\AUTO_PRO" --work-dir "%STEP1_OUT%"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo ===============================================================================
  echo  [PASS] STEP 1 hoan tat. Hay gui output CMD + anh trong:
  echo         %STEP1_OUT%
  echo ===============================================================================
) else (
  echo ===============================================================================
  echo  [FAIL] STEP 1 dung tai day. KHONG chay buoc khac.
  echo         Gui nguyen output cua cua so nay cho ChatGPT.
  echo ===============================================================================
)
pause
goto menu

:openstep1
if not exist "%STEP1_OUT%" mkdir "%STEP1_OUT%" >nul 2>&1
start "" explorer "%CD%\%STEP1_OUT%"
goto menu

:end
endlocal
exit /b 0
