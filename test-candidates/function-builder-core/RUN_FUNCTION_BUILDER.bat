@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" (
    echo Su dung: RUN_FUNCTION_BUILDER.bat PID
    echo Lay PID bang PowerShell: Get-Process GameClientJS ^| Select Id
    pause
    exit /b 2
)

py -3 function_builder_app.py %1 --workspace "%~dp0workspace"
if errorlevel 1 pause

