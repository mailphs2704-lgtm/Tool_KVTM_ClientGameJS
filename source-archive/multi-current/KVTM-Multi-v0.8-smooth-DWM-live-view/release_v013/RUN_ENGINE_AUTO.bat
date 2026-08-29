@echo off
setlocal
cd /d "%~dp0"
if not exist "bin\kvtm_bridge.dll" call BUILD_X86.bat
if errorlevel 1 pause & exit /b 1
py -3.11 pc_auto_engine_launcher.py
if errorlevel 1 pause
endlocal
