@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title KVTM BRIDGE V3 - CONTROL CENTER

set "ROOT=%~dp0"
set "SRC=%ROOT%native"
set "PY=%ROOT%python"
set "BIN=%ROOT%bin"
set "BACKUP=%ROOT%backup"
set "DEV_BIN=%ROOT%..\dist\KVTM-ClientJS-Suite-Multi-DEV\AUTO_PRO\bin"

:menu
cls
echo ===============================================================================
echo  KVTM BRIDGE V3 - CONTROL CENTER
echo  MOT BAT DUY NHAT: build, verify, live probe, install co khoa, rollback.
echo  V3 CHI capture + input. KHONG resize, DPI, layout hay AUTO business logic.
echo ===============================================================================
echo  [1] Build V3 x86
echo  [2] Static verify source + binary
echo  [3] Live probe V3 theo PID GameClientJS DEV
echo  [4] Cai V3 vao runtime DEV ^(DANG KHOA cho den khi probe PASS^)
echo  [5] Rollback bridge runtime tu backup gan nhat
echo  [6] Mo tai lieu V3
echo  [0] Thoat
echo -------------------------------------------------------------------------------
set "CHOICE="
set /p "CHOICE=Chon: "
if "%CHOICE%"=="1" goto build
if "%CHOICE%"=="2" goto verify
if "%CHOICE%"=="3" goto probe
if "%CHOICE%"=="4" goto install
if "%CHOICE%"=="5" goto rollback
if "%CHOICE%"=="6" goto docs
if "%CHOICE%"=="0" goto end
goto menu

:find_vs
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
set "VSROOT="
if not exist "%VSWHERE%" exit /b 20
for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSROOT=%%i"
if not defined VSROOT exit /b 20
exit /b 0

:build
cls
call :find_vs
if errorlevel 1 (
  echo [FAIL] Khong tim thay Visual Studio C++ x86/x64 Build Tools.
  pause
  goto menu
)
call "%VSROOT%\VC\Auxiliary\Build\vcvarsall.bat" x86
if errorlevel 1 (
  echo [FAIL] Khong nap duoc MSVC x86 environment.
  pause
  goto menu
)
if not exist "%BIN%" mkdir "%BIN%"
del /q "%BIN%\kvtm_bridge_v3.dll" "%BIN%\kvtm_loader_v3.exe" >nul 2>&1
cl /nologo /std:c++17 /O2 /EHsc /MT /LD /Fe:"%BIN%\kvtm_bridge_v3.dll" "%SRC%\kvtm_bridge_v3.cpp" user32.lib
if errorlevel 1 goto build_fail
cl /nologo /std:c++17 /O2 /EHsc /MT /Fe:"%BIN%\kvtm_loader_v3.exe" "%SRC%\kvtm_loader_v3.cpp"
if errorlevel 1 goto build_fail
echo.
echo [PASS] BUILD V3 x86
certutil -hashfile "%BIN%\kvtm_bridge_v3.dll" SHA256
pause
goto menu
:build_fail
echo [FAIL] Build V3 that bai. Runtime chinh KHONG bi thay doi.
pause
goto menu

:verify
cls
py -3.11 "%ROOT%tools\verify_v3.py" --root "%ROOT%."
if errorlevel 1 (
  echo [FAIL] STATIC VERIFY V3
) else (
  echo [PASS] STATIC VERIFY V3
)
pause
goto menu

:probe
cls
if not exist "%BIN%\kvtm_bridge_v3.dll" (
  echo [STOP] Chua co binary. Chay [1] truoc.
  pause
  goto menu
)
set "GAME_PID="
set /p "GAME_PID=Nhap PID GameClientJS DEV: "
echo %GAME_PID%| findstr /r "^[1-9][0-9]*$" >nul
if errorlevel 1 (
  echo [STOP] PID khong hop le.
  pause
  goto menu
)
"%BIN%\kvtm_loader_v3.exe" "%GAME_PID%" "%BIN%\kvtm_bridge_v3.dll"
if errorlevel 1 (
  echo [FAIL] Inject V3 that bai. Runtime chinh KHONG bi thay doi.
  pause
  goto menu
)
set "SWIPE_ARG="
set "SWIPE_CONFIRM="
set /p "SWIPE_CONFIRM=Chay swipe nho 0.50s o tam game? Go SWIPE de dong y, Enter de bo qua: "
if "%SWIPE_CONFIRM%"=="SWIPE" set "SWIPE_ARG=--swipe-test"
py -3.11 "%ROOT%tools\probe_v3.py" --pid "%GAME_PID%" --output "%ROOT%probe-output" %SWIPE_ARG%
if errorlevel 1 (
  echo [FAIL] LIVE PROBE V3. KHONG cai runtime.
) else (
  echo [PASS] LIVE PROBE V3. Doc probe-output\LATEST.txt.
)
pause
goto menu

:install
cls
echo [LOCKED] V3 da PASS build/static/live capture/swipe timing.
echo          Chua cai runtime vi EngineDriver production van dung protocol V1.
echo          Chi mo khoa sau khi adapter V3 + package CI PASS de tranh AUTO mat capture/input.
pause
goto menu

:rollback
cls
powershell -NoProfile -ExecutionPolicy Bypass -Command "$b=Get-ChildItem -LiteralPath '%BACKUP%' -Directory -ErrorAction SilentlyContinue ^| Sort-Object Name -Descending ^| Select-Object -First 1; if(-not $b){exit 2}; Copy-Item -LiteralPath (Join-Path $b.FullName 'kvtm_bridge.dll') -Destination '%DEV_BIN%\kvtm_bridge.dll' -Force; Copy-Item -LiteralPath (Join-Path $b.FullName 'kvtm_loader.exe') -Destination '%DEV_BIN%\kvtm_loader.exe' -Force; Write-Host ('ROLLBACK='+$b.FullName)"
if errorlevel 1 (
  echo [FAIL] Khong co backup hop le. Runtime khong thay doi.
) else (
  echo [PASS] Rollback bridge runtime.
)
pause
goto menu

:docs
start "" "%ROOT%docs\BRIDGE_V3_BUILD_AND_ARCHITECTURE.md"
goto menu

:end
endlocal
exit /b 0
