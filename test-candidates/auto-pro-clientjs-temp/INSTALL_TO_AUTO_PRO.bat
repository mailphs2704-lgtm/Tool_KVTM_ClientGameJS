@echo off
setlocal
if "%~1"=="" (
  echo Cach dung:
  echo   INSTALL_TO_AUTO_PRO.bat "C:\duong-dan\AUTO_KVTM_PRO_recovered_local"
  pause
  exit /b 2
)
set "TARGET=%~1"
if not exist "%TARGET%\local_launcher.py" (
  echo Khong tim thay local_launcher.py trong: %TARGET%
  pause
  exit /b 3
)
if not exist "%TARGET%\engine_driver.py.before-auto-settings.bak" (
  if exist "%TARGET%\engine_driver.py" copy /Y "%TARGET%\engine_driver.py" "%TARGET%\engine_driver.py.before-auto-settings.bak" >nul
)
copy /Y "%~dp0engine_driver.py" "%TARGET%\engine_driver.py" >nul
copy /Y "%~dp0RUN_PC_AUTO_ENGINE.bat" "%TARGET%\RUN_PC_AUTO_ENGINE.bat" >nul
echo Da cai EngineDriver ton trong cai dat AUTO PRO vao:
echo %TARGET%
pause
endlocal
