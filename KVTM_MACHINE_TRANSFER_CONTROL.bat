@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title KVTM - MACHINE TRANSFER CONTROL

:menu
cls
echo ===============================================================================
echo  KVTM - MACHINE TRANSFER CONTROL
echo ===============================================================================
echo  [1] Xuat profile DEV de chuyen may   ^(ma hoa, mac dinh ra Desktop^)
echo  [2] Nhap profile .kvtm vao may nay   ^(merge ID + backup + DPAPI^)
echo  [3] Chan doan moi truong may          ^(READ-ONLY^)
echo  [4] Cai PM may phu con thieu          ^(gom C++ Build Tools^)
echo  [5] Mo trang Sky Garden/ZingPlay chinh thuc
echo  [6] Bootstrap may phu + build runtime ^(dung tren may phu^)
echo  [7] Xac minh profile/DPAPI READ-ONLY
echo  [8] Gui report may phu len GitHub     ^(SAFE TXT ONLY^)
echo  [9] Nhan cap nhat DEV tu GitHub       ^(pull + deps + LFS + build^)
echo  [0] Thoat
echo -------------------------------------------------------------------------------
set "CHOICE="
set /p "CHOICE=Chon: "
if "%CHOICE%"=="1" goto export_profile
if "%CHOICE%"=="2" goto import_profile
if "%CHOICE%"=="3" goto diagnose
if "%CHOICE%"=="4" goto install
if "%CHOICE%"=="5" goto zingplay
if "%CHOICE%"=="6" goto bootstrap
if "%CHOICE%"=="7" goto verify_profile
if "%CHOICE%"=="8" goto github_send
if "%CHOICE%"=="9" goto github_update
if "%CHOICE%"=="0" goto end
goto menu

:export_profile
cls
echo [EXPORT] Dang kiem tra va giai ma DPAPI cua profile tren Windows user hien tai.
echo          Secret plaintext KHONG duoc ghi ra dia; file .kvtm se duoc ma hoa bang mat khau.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\KVTM_PROFILE_TRANSFER.ps1" -Mode Export
if errorlevel 1 (
  echo.
  echo [FAIL] Export that bai. Khong co profile active nao bi sua.
) else (
  echo.
  echo [PASS] Export xong. Copy file .kvtm tren Desktop sang may phu.
)
pause
goto menu

:import_profile
cls
echo [IMPORT] Nhap file .kvtm moi; profile trung ID duoc cap nhat, profile khac duoc giu.
echo          Vi du: D:\KVTM-PROFILES-TRANSFER-20260901-203000.kvtm
echo.
set "TRANSFER="
set /p "TRANSFER=File .kvtm: "
set "TRANSFER=%TRANSFER:"=%"
if not exist "%TRANSFER%" (
  echo [FAIL] Khong tim thay file: %TRANSFER%
  pause
  goto menu
)
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\KVTM_PROFILE_TRANSFER.ps1" -Mode Import -TransferFile "%TRANSFER%"
if errorlevel 1 (
  echo.
  echo [FAIL] Import that bai. Profile cu duoc giu nguyen neu chua qua buoc ghi an toan.
  pause
  goto menu
)
echo.
echo [VERIFY] Kiem tra DPAPI va duong dan sau import...
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\KVTM_PROFILE_VERIFY.ps1"
set "VERIFY_RC=%ERRORLEVEL%"
echo.
if "%VERIFY_RC%"=="0" (
  echo [PASS] Import + DPAPI + launch paths READY.
) else if "%VERIFY_RC%"=="3" (
  echo [PARTIAL PASS] DPAPI READY, nhung ZingPlay/game path chua san sang.
) else (
  echo [FAIL] Profile sau import chua dat DPAPI verify.
)
pause
goto menu

:diagnose
cls
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\KVTM_MACHINE_SETUP.ps1"
echo.
if exist ".\data-machine-diagnostic" start "" explorer ".\data-machine-diagnostic"
pause
goto menu

:install
cls
echo ===============================================================================
echo  CAI PM THIEU QUA WINGET
echo  Co the cai: Git, Git LFS, Python 3.11 x64, VC++ Runtime va C++ Build Tools.
echo  ZingPlay/Sky Garden chi mo nguon chinh thuc neu thieu.
echo ===============================================================================
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\KVTM_MACHINE_SETUP.ps1" -InstallMissing -OpenZingPlayPage
if exist ".\data-machine-diagnostic" start "" explorer ".\data-machine-diagnostic"
pause
goto menu

:zingplay
start "" "https://zingplay.com/games/sky-garden.html"
goto menu

:bootstrap
cls
echo ===============================================================================
echo  BOOTSTRAP MAY PHU
echo  Se dam bao dependencies, pull dung branch, git lfs pull va build DEV runtime.
echo  Repo private co the mo cua so dang nhap GitHub khi clone/pull.
echo ===============================================================================
powershell -NoProfile -ExecutionPolicy Bypass -File ".\KVTM_SECONDARY_BOOTSTRAP.ps1" -TargetDirectory "%CD%" -BuildRuntime -OpenZingPlayPage
if errorlevel 1 (
  echo.
  echo [FAIL] Bootstrap chua hoan tat. Doc diagnostic de biet thanh phan con thieu.
) else (
  echo.
  echo [PASS] Bootstrap hoan tat.
)
pause
goto menu

:verify_profile
cls
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\KVTM_PROFILE_VERIFY.ps1"
echo.
pause
goto menu

:github_send
cls
echo ===============================================================================
echo  GUI REPORT MAY PHU LEN GITHUB
echo  Chi upload diagnostic TXT da whitelist len branch machine-sync rieng.
echo  KHONG upload .kvtm, profiles.json, password, token, cookie hay secret.
echo ===============================================================================
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\KVTM_GITHUB_BRIDGE.ps1" -Mode SendReport
if errorlevel 1 (
  echo.
  echo [FAIL] Chua gui duoc report. Khong co profile/transfer file nao bi upload.
) else (
  echo.
  echo [PASS] Report an toan da len GitHub. Chi can nhan ChatGPT: da gui report may phu.
)
pause
goto menu

:github_update
cls
echo ===============================================================================
echo  NHAN CAP NHAT DEV TU GITHUB
echo  Pull develop/multi-auto-dev + cai dependency + Git LFS + build runtime.
echo  Neu da co data-dev/profile, builder hien tai se bao toan data DEV.
echo ===============================================================================
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\KVTM_GITHUB_BRIDGE.ps1" -Mode UpdateDev
if errorlevel 1 (
  echo.
  echo [FAIL] Update DEV chua hoan tat. Chon [8] de gui report moi cho ChatGPT.
) else (
  echo.
  echo [PASS] DEV da cap nhat va build xong.
)
pause
goto menu

:end
endlocal
exit /b 0
