@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title KVTM WORKSPACE - ONE CLICK SETUP

set "BRANCH=develop/clientjs-workspace"
set "TARGET=%USERPROFILE%\Desktop\Tool_KVTM_Workspace_DEV"

echo ===============================================================================
echo  KVTM WORKSPACE - ONE CLICK SETUP
echo  Tao workspace Git rieng, khong thay doi thu muc DEV dang duoc AI khac su dung.
echo ===============================================================================

if not exist ".git" (
  echo [FAIL] Hay dat file BAT nay vao thu muc Tool_KVTM_Multi_DEV roi nhap dup.
  goto done
)

git fetch origin "%BRANCH%"
if errorlevel 1 (
  echo [FAIL] Khong fetch duoc %BRANCH%.
  goto done
)

if exist "%TARGET%\.git" (
  echo [INFO] Workspace da ton tai: %TARGET%
  git -C "%TARGET%" pull --ff-only origin "%BRANCH%"
  if errorlevel 1 goto pull_fail
) else (
  if exist "%TARGET%" (
    echo [FAIL] Thu muc dich da ton tai nhung khong phai Git workspace:
    echo        %TARGET%
    echo Khong xoa hoac ghi de thu muc nay.
    goto done
  )
  git worktree add "%TARGET%" "%BRANCH%"
  if errorlevel 1 (
    echo [FAIL] Khong tao duoc Git worktree.
    goto done
  )
)

git -C "%TARGET%" lfs pull
if errorlevel 1 (
  echo [FAIL] git lfs pull that bai.
  goto done
)

echo.
echo [PASS] Workspace da san sang:
echo        %TARGET%
echo [OPEN] Dang mo Control Center...
start "" "%TARGET%\KVTM_WORKSPACE_CONTROL.bat"
goto done

:pull_fail
echo [FAIL] Workspace co thay doi chua commit hoac khong fast-forward duoc.
echo Khong co file nao bi ep ghi de.

:done
echo.
pause
endlocal
exit /b 0
