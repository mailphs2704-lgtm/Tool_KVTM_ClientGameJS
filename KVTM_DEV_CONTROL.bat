@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title KVTM MULTI DEV - CONTROL CENTER

set "EXPECTED_BRANCH=develop/multi-auto-dev"
set "DIST=dist\KVTM-ClientJS-Suite-Multi-DEV"
set "STEP1=components\clientjs-auto\worker\clear_stall_step1_probe.py"
set "STEP1_OUT=%DIST%\data-dev\clear-stall-step1"
set "RESULT_BRANCH=diagnostics/clear-stall"
set "RESULT_WT=%TEMP%\KVTM_DEV_DIAGNOSTICS_WORKTREE"

:menu
cls
set "CUR_BRANCH="
set "CUR_HEAD="
for /f "delims=" %%B in ('git branch --show-current 2^>nul') do set "CUR_BRANCH=%%B"
for /f "delims=" %%H in ('git rev-parse --short HEAD 2^>nul') do set "CUR_HEAD=%%H"
echo ===============================================================================
echo  KVTM MULTI DEV - CONTROL CENTER
echo  MOT CUA SO DUY NHAT. Khong can go lenh CMD dai nua.
echo  Client cu dang chay AUTO se KHONG bi test DEV cham vao.
echo ===============================================================================
echo  Repo   : %CD%
echo  Branch : %CUR_BRANCH%
echo  HEAD   : %CUR_HEAD%
echo -------------------------------------------------------------------------------
echo  [1] Cap nhat source DEV
echo  [2] Mo Multi DEV               ^(tu dong sync file DEV^)
echo  [3] Don quay - BUOC HIEN TAI   ^(STEP 1 - capture bang AUTO chinh^)
echo      Sau test se TU GUI log + anh len GitHub cho ChatGPT doc.
echo  [4] Gui lai ket qua gan nhat len GitHub
echo  [5] Mo thu muc ket qua
echo  [9] Full rebuild package        ^(CHI dung khi ChatGPT yeu cau^)
echo  [0] Thoat
echo -------------------------------------------------------------------------------
set "CHOICE="
set /p "CHOICE=Chon: "
if "%CHOICE%"=="1" goto update
if "%CHOICE%"=="2" goto startmulti
if "%CHOICE%"=="3" goto step1
if "%CHOICE%"=="4" goto upload_latest
if "%CHOICE%"=="5" goto openstep1
if "%CHOICE%"=="9" goto fullbuild
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

:update
call :guard_branch
if errorlevel 1 (
  pause
  goto menu
)
cls
echo [DEV] Cap nhat source %EXPECTED_BRANCH%...
echo [DEV] Da tat auto-gc/maintenance trong lenh pull de tranh prompt pack.idx.
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
echo [INFO] Tu gio [2] va [3] tu sync file can thiet vao dist.
pause
goto menu

:sync_dev
call :guard_branch
if errorlevel 1 exit /b 1
if not exist "%DIST%\AUTO_PRO\local_launcher.py" (
  echo [LOI] Package goc chua co AUTO_PRO. Can Full rebuild [9] mot lan.
  exit /b 1
)
if not exist "%DIST%\Multi" mkdir "%DIST%\Multi" >nul 2>&1
if not exist "%DIST%\components\clientjs-auto" mkdir "%DIST%\components\clientjs-auto" >nul 2>&1
echo [DEV] Sync Multi source -^> dist...
robocopy "source-archive\multi-current\kvtm_multi_tool" "%DIST%\Multi" /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 exit /b 1
echo [DEV] Sync ClientJS AUTO component -^> dist...
robocopy "components\clientjs-auto" "%DIST%\components\clientjs-auto" /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 exit /b 1
copy /Y "packaging\suite-v0.15\02_START_MULTI_DEV.bat" "%DIST%\02_START_MULTI_DEV.bat" >nul
for %%F in (adaptive_cv.py clientjs_auto_patch.py engine_driver.py pc_driver.py) do (
  if exist "test-candidates\auto-pro-clientjs-temp\%%F" copy /Y "test-candidates\auto-pro-clientjs-temp\%%F" "%DIST%\AUTO_PRO\%%F" >nul
)
if not exist "%DIST%\Multi\kvtm_multi_dev_host.py" (
  echo [LOI] Sync xong van thieu Multi\kvtm_multi_dev_host.py
  exit /b 1
)
if not exist "%DIST%\Multi\kvtm_multi_dev_entry.py" (
  echo [LOI] Sync xong van thieu Multi\kvtm_multi_dev_entry.py
  exit /b 1
)
if not exist "%STEP1%" (
  echo [LOI] Source thieu %STEP1%
  exit /b 1
)
echo [OK] DEV runtime da sync. data-dev/profile khong bi xoa.
exit /b 0

:startmulti
cls
call :sync_dev
if errorlevel 1 (
  echo.
  echo [STOP] Khong mo Multi vi sync DEV that bai.
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
call :sync_dev
if errorlevel 1 (
  echo.
  echo [STOP] Khong test STEP 1 vi sync DEV that bai.
  pause
  goto menu
)
echo ===============================================================================
echo  DON QUAY - STEP 1 ONLY
echo  Dung DUNG bootstrap AUTO chinh.
echo  Chi match GameClientJS thuoc profiles Multi DEV.
echo  KHONG click, KHONG swipe, KHONG mua/ban, KHONG dung client bo cu.
echo ===============================================================================
py -3.11 -c "import sys,struct; assert sys.version_info[:2]==(3,11) and struct.calcsize('P')*8==64" >nul 2>&1
if errorlevel 1 (
  echo [LOI] Can CPython 3.11 x64.
  py -0p
  pause
  goto menu
)
if not exist "%STEP1_OUT%" mkdir "%STEP1_OUT%" >nul 2>&1
del /q "%STEP1_OUT%\latest-console.log" >nul 2>&1
echo [DEV] Bat dau STEP 1...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Continue'; ^& py -3.11 '%STEP1%' --auto-root '%DIST%\AUTO_PRO' --work-dir '%STEP1_OUT%' 2^>^&1 ^| Tee-Object -FilePath '%STEP1_OUT%\latest-console.log'; exit $LASTEXITCODE"
set "STEP_RC=%ERRORLEVEL%"
>"%STEP1_OUT%\latest-result-code.txt" echo %STEP_RC%
echo.
if "%STEP_RC%"=="0" (
  echo ===============================================================================
  echo  [PASS] STEP 1 local PASS.
  echo ===============================================================================
) else (
  echo ===============================================================================
  echo  [FAIL] STEP 1 dung tai day. KHONG chay buoc khac.
  echo ===============================================================================
)
echo [DEV] Dang gui ket qua len GitHub branch %RESULT_BRANCH%...
call :upload_results
if errorlevel 1 (
  echo [CANH BAO] Upload that bai. Ket qua local van con; co the chon [4] de gui lai.
) else (
  echo [OK] Da gui ket qua. ChatGPT co the doc truc tiep tren GitHub.
)
pause
goto menu

:upload_latest
cls
call :upload_results
if errorlevel 1 (
  echo.
  echo [LOI] Gui ket qua that bai.
) else (
  echo.
  echo [OK] Da gui ket qua gan nhat len GitHub.
)
pause
goto menu

:upload_results
if not exist "%STEP1_OUT%\latest-console.log" (
  echo [LOI] Chua co latest-console.log. Hay chay [3] truoc.
  exit /b 1
)
for /f "delims=" %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "STAMP=%%T"
set "RUN_REL=diagnostics\clear-stall\runs\%STAMP%"
set "RUN_DIR=%RESULT_WT%\%RUN_REL%"
if exist "%RESULT_WT%" (
  git worktree remove --force "%RESULT_WT%" >nul 2>&1
  rmdir /s /q "%RESULT_WT%" >nul 2>&1
)
git worktree prune >nul 2>&1
git fetch origin "%RESULT_BRANCH%" >nul 2>&1
git rev-parse --verify "refs/remotes/origin/%RESULT_BRANCH%" >nul 2>&1
if errorlevel 1 (
  git worktree add --detach "%RESULT_WT%" HEAD >nul 2>&1
) else (
  git worktree add --detach "%RESULT_WT%" "origin/%RESULT_BRANCH%" >nul 2>&1
)
if errorlevel 1 (
  echo [LOI] Khong tao duoc diagnostics worktree.
  exit /b 1
)
mkdir "%RUN_DIR%" >nul 2>&1
copy /Y "%STEP1_OUT%\latest-console.log" "%RUN_DIR%\console.log" >nul
if exist "%STEP1_OUT%\latest-result-code.txt" copy /Y "%STEP1_OUT%\latest-result-code.txt" "%RUN_DIR%\result-code.txt" >nul
for %%F in ("%STEP1_OUT%\step1-auto-main-capture-pid-*.png") do (
  if exist "%%~fF" copy /Y "%%~fF" "%RUN_DIR%\%%~nxF" >nul
)
for /f "delims=" %%H in ('git rev-parse HEAD 2^>nul') do set "SOURCE_HEAD=%%H"
for /f "delims=" %%B in ('git branch --show-current 2^>nul') do set "SOURCE_BRANCH=%%B"
(
  echo step=1
  echo timestamp=%STAMP%
  echo source_branch=%SOURCE_BRANCH%
  echo source_head=%SOURCE_HEAD%
  echo result_branch=%RESULT_BRANCH%
  echo note=Only allowlisted diagnostics uploaded. No profiles/settings/secrets.
)>"%RUN_DIR%\metadata.txt"
if not exist "%RESULT_WT%\diagnostics\clear-stall" mkdir "%RESULT_WT%\diagnostics\clear-stall" >nul 2>&1
>"%RESULT_WT%\diagnostics\clear-stall\LATEST.txt" echo %RUN_REL:\=/%
git -C "%RESULT_WT%" config user.name "KVTM DEV Diagnostics" >nul
git -C "%RESULT_WT%" config user.email "kvtm-dev-diagnostics@local" >nul
git -C "%RESULT_WT%" add diagnostics/clear-stall
git -C "%RESULT_WT%" commit -m "Add clear stall step 1 diagnostics %STAMP%" >nul 2>&1
if errorlevel 1 (
  echo [LOI] Khong tao duoc diagnostics commit.
  git worktree remove --force "%RESULT_WT%" >nul 2>&1
  exit /b 1
)
git -C "%RESULT_WT%" push origin HEAD:refs/heads/%RESULT_BRANCH%
set "PUSH_RC=%ERRORLEVEL%"
git worktree remove --force "%RESULT_WT%" >nul 2>&1
git worktree prune >nul 2>&1
if not "%PUSH_RC%"=="0" exit /b 1
echo [GIT] branch=%RESULT_BRANCH%
echo [GIT] latest=%RUN_REL:\=/%
exit /b 0

:openstep1
if not exist "%STEP1_OUT%" mkdir "%STEP1_OUT%" >nul 2>&1
start "" explorer "%CD%\%STEP1_OUT%"
goto menu

:profile_diagnostic
cls
echo ===============================================================================
echo  PROFILE/LOGIN DIAGNOSTIC - READ ONLY
echo  Khong in secret. Khong sua profiles.json, backup hoac session.
echo ===============================================================================
if not exist "KVTM_PROFILE_DIAGNOSTIC.ps1" (
  echo [LOI] Thieu KVTM_PROFILE_DIAGNOSTIC.ps1
  pause
  goto menu
)
powershell -NoProfile -ExecutionPolicy Bypass -File ".\KVTM_PROFILE_DIAGNOSTIC.ps1"
if errorlevel 1 (
  echo [FAIL] Kiem tra profile that bai. Gui nguyen output nay cho ChatGPT.
) else (
  echo [PASS] Da tao bao cao read-only.
  start "" explorer "%CD%\data-profile-diagnostic"
)
pause
goto menu

:fullbuild
cls
echo ===============================================================================
echo  FULL REBUILD - CHI DUNG KHI CHATGPT YEU CAU
echo  Trong giai doan DEV hang ngay, [2] va [3] chi sync file, nhanh va an toan hon.
echo ===============================================================================
set "KVTM_SOURCE_HEAD="
for /f "delims=" %%H in ('git rev-parse HEAD 2^>nul') do set "KVTM_SOURCE_HEAD=%%H"
powershell -NoProfile -ExecutionPolicy Bypass -File ".\packaging\suite-v0.15\BUILD_FULL_PACKAGE.ps1"
echo.
echo [INFO] Neu builder bao loi package stamp, dung [2]/[3] de tiep tuc DEV; khong xoa data-dev.
pause
goto menu

:end
endlocal
exit /b 0
