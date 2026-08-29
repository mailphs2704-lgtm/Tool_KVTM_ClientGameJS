@echo off
setlocal
cd /d "%~dp0"
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" goto :no_vs
for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSROOT=%%i"
if not defined VSROOT goto :no_vs
call "%VSROOT%\VC\Auxiliary\Build\vcvarsall.bat" x86
if errorlevel 1 exit /b 10
if not exist bin mkdir bin
cl /nologo /std:c++17 /O2 /EHsc /MT /LD /Fe:bin\kvtm_bridge.dll native\kvtm_bridge.cpp user32.lib
if errorlevel 1 exit /b 11
cl /nologo /std:c++17 /O2 /EHsc /MT /Fe:bin\kvtm_loader.exe native\kvtm_loader.cpp
if errorlevel 1 exit /b 12
echo BUILD OK: bin\kvtm_bridge.dll + bin\kvtm_loader.exe
exit /b 0
:no_vs
echo Khong tim thay Visual Studio Build Tools C++ x86/x64.
echo Cai workload "Desktop development with C++", sau do chay lai file nay.
exit /b 20
