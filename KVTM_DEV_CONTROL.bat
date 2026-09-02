@echo off
if /I "%~1"=="--stable-copy" goto stable_copy
set "KVTM_CONTROL_COPY=%TEMP%\KVTM_DEV_CONTROL_STABLE_%RANDOM%_%RANDOM%.bat"
copy /Y "%~f0" "%KVTM_CONTROL_COPY%" >nul
call "%KVTM_CONTROL_COPY%" --stable-copy "%~dp0"
set "KVTM_CONTROL_RC=%ERRORLEVEL%"
del /Q "%KVTM_CONTROL_COPY%" >nul 2>&1
exit /b %KVTM_CONTROL_RC%

:stable_copy
set "KVTM_REPO_ROOT=%~2"
setlocal EnableExtensions
chcp 65001 >nul 2>&1
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%KVTM_REPO_ROOT%"
title KVTM MULTI DEV - CONTROL CENTER

set "EXPECTED_BRANCH=develop/multi-auto-dev"
set "DIST=dist\KVTM-ClientJS-Suite-Multi-DEV"
set "STEP1=components\clientjs-auto\worker\clear_stall_step1_probe.py"
set "V3_GESTURE=components\clientjs-auto\worker\bridge_v3_gesture_probe.py"
set "SPEED_PROBE=components\clientjs-auto\worker\speed_binding_probe.py"
set "STEP1_OUT=%DIST%\data-dev\clear-stall-step1"
set "RESULT_BRANCH=diagnostics/clear-stall"
set "RESULT_WT=%TEMP%\KVTM_DEV_DIAGNOSTICS_WORKTREE"
set "GATE_LOG_ROOT=%DIST%\data-dev\clear-stall-probe"

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
echo  [1] Cap nhat source + build runtime DEV
echo  [2] Mo Multi DEV nen           ^(tu dong sync, khong hien CMD^)
echo  [3] Don quay - BUOC HIEN TAI   ^(STEP 1 - capture bang AUTO chinh^)
echo      Sau test se TU GUI log + anh len GitHub cho ChatGPT doc.
echo  [4] Gui log GATE Don quay len GitHub ^(SAFE whitelist^)
echo  [5] Mo thu muc ket qua
echo  [6] Kiem tra profile/login READ-ONLY
echo  [7] Bridge V3 - gesture production 0.50s ^(can go SWIPE-V3^)
echo  [8] Audit mapping toc do AUTO PRO READ-ONLY
echo  [9] Full rebuild package        ^(CHI dung khi ChatGPT yeu cau^)
echo  [0] Thoat
echo -------------------------------------------------------------------------------
set "CHOICE="
set /p "CHOICE=Chon: "
if "%CHOICE%"=="1" goto update
if "%CHOICE%"=="2" goto startmulti
if "%CHOICE%"=="3" goto step1
if "%CHOICE%"=="4" goto upload_gate
if "%CHOICE%"=="5" goto openstep1
if "%CHOICE%"=="6" goto profile_diagnostic
if "%CHOICE%"=="7" goto v3_gesture
if "%CHOICE%"=="8" goto speed_probe
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
echo [DEV] Dang build runtime co dinh; data-dev/profile duoc bao toan...
powershell -NoProfile -ExecutionPolicy Bypass -File ".\packaging\suite-v0.15\BUILD_FULL_PACKAGE_PS51.ps1" -OutputName "KVTM-ClientJS-Suite-Multi-DEV"
if errorlevel 1 (
  echo.
  echo [LOI] Build runtime that bai. Hay dong Multi va tat ca ClientJS roi chay lai [1].
  pause
  goto menu
)
echo.
git rev-parse --short HEAD
echo [PASS] Source va runtime DEV da cap nhat cung HEAD.
echo [INFO] Co the chon [2] de mo Multi ngay.
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
copy /Y "packaging\suite-v0.15\START_MULTI_DEV_SILENT.ps1" "%DIST%\START_MULTI_DEV_SILENT.ps1" >nul
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
echo [DEV] Dang mo Multi DEV nen, khong hien CMD...
powershell -NoProfile -ExecutionPolicy Bypass -File ".\%DIST%\START_MULTI_DEV_SILENT.ps1"
if errorlevel 1 (
  echo.
  echo [FAIL] Khong mo duoc Multi DEV nen. Gui output nay cho ChatGPT.
  pause
  goto menu
)
echo [PASS] Multi DEV da chay nen. Control Center se tu dong dong.
timeout /t 2 /nobreak >nul
goto end

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
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Continue'; & py -3.11 '%STEP1%' --auto-root '%DIST%\AUTO_PRO' --work-dir '%STEP1_OUT%' 2>&1 | Tee-Object -FilePath '%STEP1_OUT%\latest-console.log'; exit $LASTEXITCODE"
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

:upload_gate
cls
echo ===============================================================================
echo  GUI LOG GATE DON QUAY LEN GITHUB
echo  Chi gui activity.log, report.json va PNG cua lan Gate moi nhat.
echo  KHONG gui profiles/settings/.kvtm/token/cookie/password/secret.
echo ===============================================================================
set "GATE_ACTIVITY="
set "GATE_PROFILE_ROOT="
set "GATE_REPORT_DIR="
for /f "usebackq delims=" %%F in (`powershell -NoProfile -Command "$p=Get-ChildItem -LiteralPath '%GATE_LOG_ROOT%' -Recurse -Filter activity.log -File -ErrorAction SilentlyContinue ^| Where-Object Length -gt 0 ^| Sort-Object LastWriteTime -Descending ^| Select-Object -First 1 -ExpandProperty FullName; if($p){$p}"`) do set "GATE_ACTIVITY=%%F"
if not defined GATE_ACTIVITY (
  echo [FAIL] Chua co activity.log. Hay bam nut Gate trong Multi truoc.
  pause
  goto menu
)
for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "$f=Get-Item -LiteralPath '%GATE_ACTIVITY%' -ErrorAction Stop; $f.Directory.Parent.FullName"`) do set "GATE_PROFILE_ROOT=%%D"
if defined GATE_PROFILE_ROOT (
  for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "$p=Get-ChildItem -LiteralPath '%GATE_PROFILE_ROOT%' -Recurse -Filter report.json -File -ErrorAction SilentlyContinue ^| Sort-Object LastWriteTime -Descending ^| Select-Object -First 1 -ExpandProperty DirectoryName; if($p){$p}"`) do set "GATE_REPORT_DIR=%%D"
)
for /f "delims=" %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "STAMP=%%T"
set "RUN_REL=diagnostics\clear-stall\gate-runs\%STAMP%"
set "RUN_REL_GIT=diagnostics/clear-stall/gate-runs/%STAMP%"
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
  echo [FAIL] Khong tao duoc diagnostics worktree.
  pause
  goto menu
)
mkdir "%RUN_DIR%" >nul 2>&1
powershell -NoProfile -Command "Copy-Item -LiteralPath $env:GATE_ACTIVITY -Destination (Join-Path $env:RUN_DIR 'activity.log') -Force -ErrorAction Stop"
if errorlevel 1 (
  echo [FAIL] Khong sao chep duoc activity.log. Khong upload metadata rong.
  git worktree remove --force "%RESULT_WT%" >nul 2>&1
  pause
  goto menu
)
if not exist "%RUN_DIR%\activity.log" (
  echo [FAIL] activity.log khong ton tai sau khi sao chep. Khong upload.
  git worktree remove --force "%RESULT_WT%" >nul 2>&1
  pause
  goto menu
)
for %%Z in ("%RUN_DIR%\activity.log") do if %%~zZ LEQ 0 (
  echo [FAIL] activity.log rong 0 byte. Khong upload.
  git worktree remove --force "%RESULT_WT%" >nul 2>&1
  pause
  goto menu
)
if defined GATE_REPORT_DIR (
  powershell -NoProfile -Command "$src=$env:GATE_REPORT_DIR; $dst=$env:RUN_DIR; Copy-Item -LiteralPath (Join-Path $src 'report.json') -Destination (Join-Path $dst 'report.json') -Force -ErrorAction Stop; Get-ChildItem -LiteralPath $src -Filter '*.png' -File -ErrorAction SilentlyContinue | Copy-Item -Destination $dst -Force; $templates=Join-Path $src 'templates'; if(Test-Path -LiteralPath $templates){$td=Join-Path $dst 'templates'; New-Item -ItemType Directory -Path $td -Force | Out-Null; Get-ChildItem -LiteralPath $templates -Filter '*.png' -File -ErrorAction SilentlyContinue | Copy-Item -Destination $td -Force}"
  if errorlevel 1 (
    echo [FAIL] Co report Gate nhung khong sao chep duoc tron bo report/PNG.
    git worktree remove --force "%RESULT_WT%" >nul 2>&1
    pause
    goto menu
  )
)
powershell -NoProfile -Command "$files=Get-ChildItem -LiteralPath '%RUN_DIR%' -File -Include *.log,*.json -Recurse; $bad=$files | Select-String -Pattern '(?i)(authorization|password|cookie|token|profiles\.json|\.kvtm)' -ErrorAction SilentlyContinue; if($bad){$bad | ForEach-Object { Write-Host ('[BLOCK] '+$_.Path+':'+$_.LineNumber) }; exit 9}"
if errorlevel 1 (
  echo [BLOCK] Log Gate co chuoi nhay cam. Khong upload.
  git worktree remove --force "%RESULT_WT%" >nul 2>&1
  pause
  goto menu
)
for /f "delims=" %%H in ('git rev-parse HEAD 2^>nul') do set "SOURCE_HEAD=%%H"
(
  echo gate=READ_ONLY_SCAN
  echo timestamp=%STAMP%
  echo source_head=%SOURCE_HEAD%
  echo note=Allowlisted Gate diagnostics only. No profiles/settings/secrets.
)>"%RUN_DIR%\metadata.txt"
if not exist "%RESULT_WT%\diagnostics\clear-stall" mkdir "%RESULT_WT%\diagnostics\clear-stall" >nul 2>&1
>"%RESULT_WT%\diagnostics\clear-stall\LATEST_GATE.txt" echo %RUN_REL:\=/%
git -C "%RESULT_WT%" config user.name "KVTM DEV Diagnostics" >nul
git -C "%RESULT_WT%" config user.email "kvtm-dev-diagnostics@local" >nul
rem Force-add only the already allowlisted Gate run. Global ignore rules
rem intentionally exclude logs/JSON/PNG elsewhere in the repository.
git -C "%RESULT_WT%" add -f -- "%RUN_REL_GIT%" "diagnostics/clear-stall/LATEST_GATE.txt"
git -C "%RESULT_WT%" diff --cached --name-only -- "%RUN_REL_GIT%/activity.log" | findstr /L /I /X "%RUN_REL_GIT%/activity.log" >nul
if errorlevel 1 (
  echo [FAIL] activity.log chua duoc Git stage. Khong tao commit metadata rong.
  git -C "%RESULT_WT%" status --short -- "%RUN_REL_GIT%"
  git worktree remove --force "%RESULT_WT%" >nul 2>&1
  pause
  goto menu
)
echo [GIT] Allowlisted files da stage:
git -C "%RESULT_WT%" diff --cached --name-only -- "%RUN_REL_GIT%"
git -C "%RESULT_WT%" commit -m "Add clear stall Gate diagnostics %STAMP%" >nul 2>&1
if errorlevel 1 (
  echo [FAIL] Khong tao duoc Gate diagnostics commit.
  git worktree remove --force "%RESULT_WT%" >nul 2>&1
  pause
  goto menu
)
git -C "%RESULT_WT%" push origin HEAD:refs/heads/%RESULT_BRANCH%
set "PUSH_RC=%ERRORLEVEL%"
git worktree remove --force "%RESULT_WT%" >nul 2>&1
git worktree prune >nul 2>&1
if not "%PUSH_RC%"=="0" (
  echo [FAIL] Push log Gate that bai.
) else (
  echo [PASS] Da gui log Gate an toan.
  echo [GIT] branch=%RESULT_BRANCH%
  echo [GIT] latest=%RUN_REL:\=/%
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

:v3_gesture
cls
call :sync_dev
if errorlevel 1 (
  echo [STOP] Khong test gesture vi sync DEV that bai.
  pause
  goto menu
)
echo ===============================================================================
echo  BRIDGE V3 - PRODUCTION ENGINE DRIVER GESTURE PROBE
echo  Chi chay khi DUNG 1 ClientJS DEV dang trong game.
echo  Gesture: keo doc 80px o tam game trong 0.50 giay.
echo ===============================================================================
set "V3_CONFIRM="
set /p "V3_CONFIRM=Go SWIPE-V3 de dong y, Enter de huy: "
if not "%V3_CONFIRM%"=="SWIPE-V3" goto menu
if not exist "%V3_GESTURE%" (
  echo [FAIL] Thieu %V3_GESTURE%
  pause
  goto menu
)
py -3.11 "%V3_GESTURE%" --auto-root "%DIST%\AUTO_PRO" --duration 0.50
if errorlevel 1 (
  echo [FAIL] BRIDGE V3 PRODUCTION GESTURE PROBE
) else (
  echo [PASS] BRIDGE V3 PRODUCTION GESTURE PROBE
)
pause
goto menu

:speed_probe
cls
call :sync_dev
if errorlevel 1 (
  echo [STOP] Khong audit mapping toc do vi sync DEV that bai.
  pause
  goto menu
)
echo ===============================================================================
echo  AUDIT MAPPING TOC DO AUTO PRO - READ ONLY
echo  Khong mo profile, khong click/swipe, khong chay nghiep vu AUTO.
echo ===============================================================================
if not exist "%SPEED_PROBE%" (
  echo [FAIL] Thieu %SPEED_PROBE%
  pause
  goto menu
)
if not exist "%DIST%\data-dev\speed-binding" mkdir "%DIST%\data-dev\speed-binding" >nul 2>&1
py -3.11 "%SPEED_PROBE%" --auto-root "%DIST%\AUTO_PRO" --output "%DIST%\data-dev\speed-binding\LATEST.json"
if errorlevel 1 (
  echo [FAIL] SPEED BINDING PROBE
) else (
  echo [PASS] SPEED BINDING PROBE
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
