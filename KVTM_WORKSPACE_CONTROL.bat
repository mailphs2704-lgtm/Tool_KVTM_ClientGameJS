@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title KVTM WORKSPACE DEV - CONTROL CENTER

set "EXPECTED_BRANCH=develop/clientjs-workspace"
set "WORKSPACE=components\workspace\kvtm_workspace.py"
set "DRIVER_DIR=test-candidates\auto-pro-clientjs-temp"
set "LOG_DIR=data-workspace"
set "MAIN_DEV_ROOT=%USERPROFILE%\Desktop\Tool_KVTM_Multi_DEV"
set "DIST=%MAIN_DEV_ROOT%\dist\KVTM-ClientJS-Suite-Multi-DEV"

:menu
cls
set "CUR_BRANCH="
set "CUR_HEAD="
for /f "delims=" %%B in ('git branch --show-current 2^>nul') do set "CUR_BRANCH=%%B"
for /f "delims=" %%H in ('git rev-parse --short HEAD 2^>nul') do set "CUR_HEAD=%%H"
echo ===============================================================================
echo  KVTM WORKSPACE DEV - CONTROL CENTER
echo  KHONG can chay lenh CMD thu cong. Gui nguyen output nay cho ChatGPT khi loi.
echo ===============================================================================
echo  Repo   : %CD%
echo  Branch : %CUR_BRANCH%
echo  HEAD   : %CUR_HEAD%
echo -------------------------------------------------------------------------------
echo  [1] Cap nhat source WORKSPACE
echo  [2] Mo Multi DEV
echo  [3] Mo Workspace Live View
echo  [4] TEST 1 - Kiem tra Workspace thu nho, ClientJS/AUTO khong bi dong
echo  [5] Mo thu muc ket qua
echo  [0] Thoat
echo -------------------------------------------------------------------------------
set "CHOICE="
set /p "CHOICE=Chon: "
if "%CHOICE%"=="1" goto update
if "%CHOICE%"=="2" goto multi
if "%CHOICE%"=="3" goto workspace
if "%CHOICE%"=="4" goto test1
if "%CHOICE%"=="5" goto logs
if "%CHOICE%"=="0" goto end
goto menu

:guard
if /I "%CUR_BRANCH%"=="%EXPECTED_BRANCH%" exit /b 0
echo.
echo [STOP] Sai branch: %CUR_BRANCH%
echo        Can dung: %EXPECTED_BRANCH%
exit /b 1

:update
call :guard
if errorlevel 1 goto pause_menu
git -c gc.auto=0 -c maintenance.auto=false pull --ff-only origin %EXPECTED_BRANCH%
if errorlevel 1 (
  echo [FAIL] Khong cap nhat duoc. Khong co file nao bi ep ghi de.
  goto pause_menu
)
git lfs pull
if errorlevel 1 echo [FAIL] git lfs pull that bai.
if not errorlevel 1 echo [PASS] Source Workspace da cap nhat.
goto pause_menu

:multi
call :guard
if errorlevel 1 goto pause_menu
call :ensure_package
if not exist "%MAIN_DEV_ROOT%\.git" (
  echo [FAIL] Khong tim thay repo Multi DEV chinh:
  echo        %MAIN_DEV_ROOT%
  echo Hay dong bo/mở Multi chinh truoc; Workspace khong tu build Multi cu.
  exit /b 1
)
if not exist "%DIST%\START_MULTI_DEV_SILENT.ps1" (
  echo [FAIL] Runtime Multi DEV chinh chua san sang:
  echo        %DIST%
  exit /b 1
)
if not exist "%DIST%\data-dev" mkdir "%DIST%\data-dev" >nul 2>&1
echo [PASS] Da tim thay runtime Multi DEV chinh.
exit /b 0

:workspace
call :guard
if errorlevel 1 goto pause_menu
if not exist "%WORKSPACE%" (
  echo [FAIL] Thieu %WORKSPACE%
  goto pause_menu
)
py -3.11 -c "import sys; assert sys.version_info[:2]==(3,11)" >nul 2>&1
if errorlevel 1 (
  echo [FAIL] Can CPython 3.11 x64.
  py -0p
  goto pause_menu
)
set "PYTHONPATH=%CD%\%DRIVER_DIR%;%CD%\components\workspace"
start "KVTM GAME WORKSPACE" /D "%CD%" cmd /k py -3.11 "%WORKSPACE%"
echo [OK] Da mo Workspace. Multi/ClientJS/AUTO la tien trinh doc lap.
goto pause_menu

:test1
call :guard
if errorlevel 1 goto pause_menu
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$rows=@(Get-CimInstance Win32_Process -Filter \"Name='GameClientJS.exe'\" ^| Select-Object ProcessId,ExecutablePath); $rows ^| ConvertTo-Json -Depth 3 ^| Set-Content -Encoding UTF8 '%LOG_DIR%\test1-processes.json'; if($rows.Count -gt 0){exit 0}else{exit 2}"
if errorlevel 2 (
  echo [FAIL] Khong co GameClientJS.exe dang chay.
  goto pause_menu
)
echo ===============================================================================
echo  [TEST 1 READY]
echo  1. Mo Workspace bang muc [3].
echo  2. Nhan nut thu nho Workspace xuong taskbar.
echo  3. Cho AUTO chay 2-5 phut.
echo  4. Mo lai Workspace va gui ket qua/anh cho ChatGPT.
echo  Snapshot PID: %LOG_DIR%\test1-processes.json
echo ===============================================================================
goto pause_menu

:logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
start "" explorer "%CD%\%LOG_DIR%"
goto menu

:pause_menu
echo.
pause
goto menu

:end
endlocal
exit /b 0
