@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title KVTM - SECONDARY MACHINE SETUP

echo ===============================================================================
echo  KVTM - SECONDARY MACHINE SETUP
echo ===============================================================================
echo  File nay dung tren MAY PHU.
echo  Se cai/kiem tra Git, Git LFS, Python 3.11 x64, VC++ x86/x64,
echo  clone dung branch DEV, git lfs pull va build runtime.
echo.
echo  Neu repo private yeu cau dang nhap GitHub, hay dang nhap bang cua so trinh duyet.
echo  Neu thieu ZingPlay/Sky Garden, trang chinh thuc se duoc mo.
echo ===============================================================================
echo.

if not exist "%~dp0KVTM_SECONDARY_BOOTSTRAP.ps1" (
  echo [FAIL] Thieu KVTM_SECONDARY_BOOTSTRAP.ps1 trong cung thu muc.
  pause
  exit /b 2
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0KVTM_SECONDARY_BOOTSTRAP.ps1" -BuildRuntime -OpenZingPlayPage
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo [PASS] Bootstrap may phu da chay xong.
  echo [NEXT] Mo Desktop\Tool_KVTM_Multi_DEV\KVTM_MACHINE_TRANSFER_CONTROL.bat
  echo        sau khi ZingPlay/Sky Garden da san sang, roi chon [2] Import profile.
) else (
  echo [FAIL] Bootstrap dung voi exit code %RC%.
  echo Gui NGUYEN output cua cua so nay cho ChatGPT de tiep tuc.
)
echo.
pause
exit /b %RC%
