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
py -3.11 "%ROOT%tools\verify_v3.py" --root "%ROOT%"
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
py -3.11 "%ROOT%tools\probe_v3.py" --pid "%GAME_PID%" --output "%ROOT%probe-output"
if errorlevel 1 (
  echo [FAIL] LIVE PROBE V3. KHONG cai runtime.
) else (
  echo [PASS] LIVE PROBE V3. Doc probe-output\LATEST.txt.
)
pause
goto menu

:install
cls
if not exist "%ROOT%ALLOW_RUNTIME_INSTALL.txt" (
  echo [LOCKED] Chua co ALLOW_RUNTIME_INSTALL.txt.
  echo          Can PASS build + static + live capture + swipe timing truoc.
  pause
  goto menu
)
if not exist "%BIN%\kvtm_bridge_v3.dll" goto install_missing
if not exist "%BIN%\kvtm_loader_v3.exe" goto install_missing
if not exist "%DEV_BIN%\kvtm_bridge.dll" goto install_missing
set "CONFIRM="
set /p "CONFIRM=Da dong Multi va tat ca ClientJS? Go INSTALL-V3 de tiep tuc: "
if not "%CONFIRM%"=="INSTALL-V3" goto menu
for /f "delims=" %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "STAMP=%%T"
set "SAVE=%BACKUP%\%STAMP%"
mkdir "%SAVE%" >nul 2>&1
copy /Y "%DEV_BIN%\kvtm_bridge.dll" "%SAVE%\kvtm_bridge.dll" >nul
copy /Y "%DEV_BIN%\kvtm_loader.exe" "%SAVE%\kvtm_loader.exe" >nul
copy /Y "%BIN%\kvtm_bridge_v3.dll" "%DEV_BIN%\kvtm_bridge.dll" >nul
copy /Y "%BIN%\kvtm_loader_v3.exe" "%DEV_BIN%\kvtm_loader.exe" >nul
echo [PASS] V3 installed. Backup=%SAVE%
pause
goto menu
:install_missing
echo [FAIL] Thieu binary V3 hoac runtime DEV.
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
