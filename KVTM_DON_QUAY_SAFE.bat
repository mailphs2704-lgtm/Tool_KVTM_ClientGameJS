@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title KVTM DON QUAY - SAFE COEXIST MODE

set "DIST=dist\KVTM-ClientJS-Suite-Multi-DEV"
set "STEP1=components\clientjs-auto\worker\clear_stall_step1_probe.py"
set "SAFE_ROOT=%DIST%\data-dev\ai-don-quay-stepwise"
set "LATEST_FILE=%SAFE_ROOT%\LATEST_RUN.txt"
set "RESULT_BRANCH=diagnostics/clear-stall"

:menu
cls
set "CUR_HEAD="
set "CUR_BRANCH="
for /f "delims=" %%H in ('git rev-parse --short HEAD 2^>nul') do set "CUR_HEAD=%%H"
for /f "delims=" %%B in ('git branch --show-current 2^>nul') do set "CUR_BRANCH=%%B"
echo ===============================================================================
echo  KVTM DON QUAY - SAFE COEXIST MODE
echo  Danh rieng cho phien AI Don quay - KHONG pha workspace cua phien AI khac.
echo ===============================================================================
echo  Repo   : %CD%
echo  Branch : %CUR_BRANCH%
echo  HEAD   : %CUR_HEAD%
echo -------------------------------------------------------------------------------
echo  SAFE GUARANTEE:
echo   - KHONG git pull / reset / clean / checkout / restore
echo   - KHONG build package / robocopy / sync Multi
echo   - KHONG xoa file untracked hay workspace cua phien AI khac
echo   - Chi ghi ket qua vao data-dev\ai-don-quay-stepwise
echo   - Upload GitHub bang temporary clone ngoai thu muc DEV
echo -------------------------------------------------------------------------------
echo  [1] Chay DON QUAY - BUOC HIEN TAI: STEP 1 capture bang AUTO chinh
echo      Sau test: TU GUI log + anh len GitHub cho ChatGPT doc
echo  [2] Gui lai ket qua gan nhat len GitHub
echo  [3] Mo thu muc ket qua rieng cua phien nay
echo  [0] Thoat
echo -------------------------------------------------------------------------------
set "CHOICE="
set /p "CHOICE=Chon: "
if "%CHOICE%"=="1" goto run_step1
if "%CHOICE%"=="2" goto upload_latest
if "%CHOICE%"=="3" goto open_results
if "%CHOICE%"=="0" goto done
goto menu

:preflight
if not exist "%STEP1%" (
  echo [STOP] Thieu source Step 1: %STEP1%
  exit /b 1
)
if not exist "%DIST%\AUTO_PRO\local_launcher.py" (
  echo [STOP] Thieu runtime AUTO_PRO co san trong dist.
  echo        SAFE MODE se KHONG tu build de tranh cham workspace phien AI khac.
  exit /b 1
)
if not exist "%DIST%\data-dev\profiles.json" (
  echo [STOP] Thieu profiles.json cua Multi DEV.
  exit /b 1
)
py -3.11 -c "import sys,struct; raise SystemExit(0 if sys.version_info[:2]==(3,11) and struct.calcsize('P')*8==64 else 1)" >nul 2>&1
if errorlevel 1 (
  echo [STOP] Can CPython 3.11 x64.
  exit /b 1
)
exit /b 0

:run_step1
cls
echo ===============================================================================
echo  DON QUAY - STEP 1 ONLY - SAFE COEXIST
echo  Chi capture bang DUNG luong AUTO chinh.
echo  KHONG click / swipe / mua / ban. KHONG cham client bo cu.
echo ===============================================================================
call :preflight
if errorlevel 1 (
  echo.
  pause
  goto menu
)
if not exist "%SAFE_ROOT%" mkdir "%SAFE_ROOT%" >nul 2>&1
for /f "delims=" %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "STAMP=%%T"
set "RUN_DIR=%SAFE_ROOT%\%STAMP%"
mkdir "%RUN_DIR%" >nul 2>&1
>"%LATEST_FILE%" echo %RUN_DIR%

echo [SAFE] run=%RUN_DIR%
echo [SAFE] Bat dau STEP 1...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "& { & py -3.11 '%STEP1%' --auto-root '%DIST%\AUTO_PRO' --work-dir '%RUN_DIR%' 2>&1 | Tee-Object -FilePath '%RUN_DIR%\console.log'; exit $LASTEXITCODE }"
set "STEP_RC=%ERRORLEVEL%"
>"%RUN_DIR%\result-code.txt" echo %STEP_RC%
for /f "delims=" %%H in ('git rev-parse HEAD 2^>nul') do set "SOURCE_HEAD=%%H"
for /f "delims=" %%B in ('git branch --show-current 2^>nul') do set "SOURCE_BRANCH=%%B"
(
  echo step=1
  echo timestamp=%STAMP%
  echo source_branch=%SOURCE_BRANCH%
  echo source_head=%SOURCE_HEAD%
  echo safe_mode=coexist
  echo note=No pull/build/sync/reset/clean/worktree used by this BAT.
)>"%RUN_DIR%\metadata.txt"
echo.
if "%STEP_RC%"=="0" (
  echo [PASS] STEP 1 local PASS.
) else (
  echo [FAIL] STEP 1 local FAIL. Dung tai Step 1.
)
echo [SAFE] Dang gui allowlisted diagnostics len GitHub...
call :upload_run "%RUN_DIR%"
if errorlevel 1 (
  echo [CANH BAO] Upload that bai. Khong mat ket qua local.
  echo            Chon [2] sau de gui lai.
) else (
  echo [OK] Da gui log + anh len GitHub. Chi can nhan ChatGPT: xong
)
pause
goto menu

:upload_latest
cls
if not exist "%LATEST_FILE%" (
  echo [STOP] Chua co lan test nao trong SAFE MODE.
  pause
  goto menu
)
set "RUN_DIR="
set /p "RUN_DIR="<"%LATEST_FILE%"
if not defined RUN_DIR (
  echo [STOP] LATEST_RUN.txt rong.
  pause
  goto menu
)
if not exist "%RUN_DIR%\console.log" (
  echo [STOP] Khong tim thay console.log: %RUN_DIR%
  pause
  goto menu
)
call :upload_run "%RUN_DIR%"
if errorlevel 1 (
  echo [LOI] Gui lai ket qua that bai.
) else (
  echo [OK] Da gui lai ket qua len GitHub.
)
pause
goto menu

:upload_run
set "UPLOAD_RUN=%~1"
if not exist "%UPLOAD_RUN%\console.log" exit /b 1
for %%D in ("%UPLOAD_RUN%") do set "UPLOAD_STAMP=%%~nxD"
for /f "delims=" %%R in ('git remote get-url origin 2^>nul') do set "REMOTE_URL=%%R"
if not defined REMOTE_URL (
  echo [LOI] Khong doc duoc remote origin.
  exit /b 1
)
set "TMP_CLONE=%TEMP%\KVTM_DON_QUAY_DIAG_%RANDOM%_%RANDOM%"
git clone --quiet --no-tags "%REMOTE_URL%" "%TMP_CLONE%"
if errorlevel 1 (
  echo [LOI] Khong tao duoc temporary diagnostics clone.
  exit /b 1
)
git -C "%TMP_CLONE%" fetch --quiet origin "%RESULT_BRANCH%" >nul 2>&1
git -C "%TMP_CLONE%" rev-parse --verify "refs/remotes/origin/%RESULT_BRANCH%" >nul 2>&1
if errorlevel 1 (
  git -C "%TMP_CLONE%" checkout -q -B "%RESULT_BRANCH%" "origin/develop/multi-auto-dev"
) else (
  git -C "%TMP_CLONE%" checkout -q -B "%RESULT_BRANCH%" "origin/%RESULT_BRANCH%"
)
if errorlevel 1 (
  echo [LOI] Khong checkout duoc diagnostics branch trong TEMP clone.
  rmdir /s /q "%TMP_CLONE%" >nul 2>&1
  exit /b 1
)
set "DEST=%TMP_CLONE%\diagnostics\clear-stall\runs\%UPLOAD_STAMP%"
mkdir "%DEST%" >nul 2>&1
copy /Y "%UPLOAD_RUN%\console.log" "%DEST%\console.log" >nul
if exist "%UPLOAD_RUN%\result-code.txt" copy /Y "%UPLOAD_RUN%\result-code.txt" "%DEST%\result-code.txt" >nul
if exist "%UPLOAD_RUN%\metadata.txt" copy /Y "%UPLOAD_RUN%\metadata.txt" "%DEST%\metadata.txt" >nul
for %%F in ("%UPLOAD_RUN%\step1-auto-main-capture-pid-*.png") do (
  if exist "%%~fF" copy /Y "%%~fF" "%DEST%\%%~nxF" >nul
)
if not exist "%TMP_CLONE%\diagnostics\clear-stall" mkdir "%TMP_CLONE%\diagnostics\clear-stall" >nul 2>&1
>"%TMP_CLONE%\diagnostics\clear-stall\LATEST.txt" echo diagnostics/clear-stall/runs/%UPLOAD_STAMP%
git -C "%TMP_CLONE%" config user.name "KVTM Don Quay Diagnostics" >nul
git -C "%TMP_CLONE%" config user.email "kvtm-don-quay@local" >nul
git -C "%TMP_CLONE%" add diagnostics/clear-stall
git -C "%TMP_CLONE%" commit -q -m "Add clear stall safe diagnostics %UPLOAD_STAMP%"
if errorlevel 1 (
  echo [LOI] Khong tao duoc diagnostics commit.
  rmdir /s /q "%TMP_CLONE%" >nul 2>&1
  exit /b 1
)
git -C "%TMP_CLONE%" push --quiet origin "HEAD:refs/heads/%RESULT_BRANCH%"
set "PUSH_RC=%ERRORLEVEL%"
if "%PUSH_RC%"=="0" (
  echo [GIT] branch=%RESULT_BRANCH%
  echo [GIT] latest=diagnostics/clear-stall/runs/%UPLOAD_STAMP%
)
rmdir /s /q "%TMP_CLONE%" >nul 2>&1
if not "%PUSH_RC%"=="0" exit /b 1
exit /b 0

:open_results
if not exist "%SAFE_ROOT%" mkdir "%SAFE_ROOT%" >nul 2>&1
start "" explorer "%CD%\%SAFE_ROOT%"
goto menu

:done
endlocal
exit /b 0
