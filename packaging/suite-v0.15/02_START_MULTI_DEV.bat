@echo off
setlocal
cd /d "%~dp0"
set "KVTM_MULTI_APP_DIR=%~dp0data-dev"
set "KVTM_MULTI_INSTANCE_NAME=KVTM Multi DEV"
if not exist "%KVTM_MULTI_APP_DIR%" mkdir "%KVTM_MULTI_APP_DIR%"
cd /d "%~dp0Multi"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 kvtm_multi.py
  goto :done
)
where python >nul 2>nul
if %errorlevel%==0 (
  python kvtm_multi.py
  goto :done
)
echo [LOI] Khong tim thay Python 3.
pause
:done
endlocal
