@echo off
setlocal
cd /d "%~dp0"
py -3.11 pc_auto_engine_launcher.py
if errorlevel 1 pause
endlocal
