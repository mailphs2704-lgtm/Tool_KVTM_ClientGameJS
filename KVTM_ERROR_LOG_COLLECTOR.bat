@echo off
setlocal
chcp 65001 >nul
set "SCRIPT=%~dp0tools\KVTM_ERROR_LOG_COLLECTOR.ps1"
if not exist "%SCRIPT%" (
    echo [ERROR] Missing: %SCRIPT%
    pause
    exit /b 1
)
set "MODE=%~1"
if "%MODE%"=="" set "MODE=Start"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -Mode "%MODE%"
set "RC=%ERRORLEVEL%"
if /I "%MODE%"=="Start" pause
if /I "%MODE%"=="Status" pause
exit /b %RC%
