@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title KVTM MULTI DEV - CONTROL CENTER

set "EXPECTED_BRANCH=develop/multi-auto-dev"
set "DIST=dist\KVTM-ClientJS-Suite-Multi-DEV"
set "STEP1=components\clientjs-auto\worker\clear_stall_step1_probe.py"
set "STEP1_OUT=%DIST%\data-dev\clear-stall-step1"

:menu
cls
echo ===============================================================================
echo  KVTM MULTI DEV - CONTROL CENTER
echo  Chi dung cho Tool_KVTM_Multi_DEV. Khong dieu khien client o bo cu.
echo ===============================================================================
for /f "delims=" %%B in ('git branch --show-current 2^>nul') do set "CUR_BRANCH=%%B"
for /f "delims=" %%H in ('git rev-parse --short HEAD 2^>nul') do set "CUR_HEAD=%%H"
echo  Repo   : %CD%
echo  Branch : %CUR_BRANCH%
echo  HEAD   : %CUR_HEAD%
echo -------------------------------------------------------------------------------
echo  [1] Cap nhat source DEV
echo  [2] Build package DEV
echo  [3] Mo Multi DEV
echo  [4] Don quay - BUOC HIEN TAI: STEP 1 capture bang luong AUTO chinh
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
for /f "delims=" %%B in ('git branch --show-current 2^>nul') do set "CUR_BRANCH=%%B"
if /I not "%CUR_BRANCH%"=="%EXPECTED_BRANCH%" (
  echo.
  echo [STOP] Sai branch: %CUR_BRANCH%
  echo        Can dung: %EXPECTED_BRANCH%
  echo.
  pause
  goto menu
)
exit /b 0

:update
call :guard_branch
if errorlevel 1 goto menu
cls
echo [DEV] Cap nhat source tren branch %EXPECTED_BRANCH%...
echo [DEV] Tat auto-gc/maintenance de tranh prompt unlink pack file.
git -c gc.auto=0 -c maintenance.auto=false pull --ff-only origin %EXPECTED_BRANCH%
if errorlevel 1 (
  echo.
  echo [LOI] git pull that bai. Khong build/test tiep.
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
pause
goto menu

:build
call :guard_branch
if errorlevel 1 goto menu
cls
echo [DEV] Build fixed package...
powershell -NoProfile -ExecutionPolicy Bypass -File ".\packaging\suite-v0.15\BUILD_FULL_PACKAGE.ps1"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo [LOI] Build that bai. code=%RC%
) else (
  echo [OK] Build package DEV xong.
)
pause
goto menu

:startmulti
call :guard_branch
if errorlevel 1 goto menu
cls
if not exist "%DIST%\02_START_MULTI_DEV.bat" (
  echo [LOI] Chua co package DEV. Hay chon [2] Build package DEV truoc.
  pause
  goto menu
)
echo [DEV] Dang mo Multi DEV...
call "%DIST%\02_START_MULTI_DEV.bat"
echo.
echo [INFO] Multi DEV da dong hoac launcher da ket thuc.
pause
goto menu

:step1
call :guard_branch
if errorlevel 1 goto menu
cls
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
if not exist "%DIST%\AUTO_PRO" (
  echo [LOI] Thieu %DIST%\AUTO_PRO
  echo       Hay chon [2] Build package DEV truoc.
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
