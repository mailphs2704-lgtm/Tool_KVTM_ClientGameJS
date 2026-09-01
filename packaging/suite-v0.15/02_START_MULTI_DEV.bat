@echo off
setlocal
cd /d "%~dp0"
set "KVTM_MULTI_APP_DIR=%~dp0data-dev"
set "KVTM_MULTI_INSTANCE_NAME=KVTM Multi DEV"
set "KVTM_MULTI_ISOLATED=1"
if not exist "%KVTM_MULTI_APP_DIR%" mkdir "%KVTM_MULTI_APP_DIR%"
cd /d "%~dp0Multi"
if not exist "kvtm_multi_dev_entry.py" (
  echo [LOI] Thieu Multi\kvtm_multi_dev_entry.py
  pause
  goto :done
)
if not exist "clear_stall_probe_console.py" (
  echo [LOI] Thieu Multi\clear_stall_probe_console.py
  pause
  goto :done
)
if not exist "prepare_clear_stall_runtime.py" (
  echo [LOI] Thieu Multi\prepare_clear_stall_runtime.py
  pause
  goto :done
)

set "KVTM_PYTHON="
where py >nul 2>nul
if %errorlevel%==0 (
  py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,11) else 1)" >nul 2>nul
  if %errorlevel%==0 set "KVTM_PYTHON=py -3.11"
)

if not defined KVTM_PYTHON (
  where python >nul 2>nul
  if %errorlevel%==0 (
    python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,11) else 1)" >nul 2>nul
    if %errorlevel%==0 set "KVTM_PYTHON=python"
  )
)

if not defined KVTM_PYTHON (
  echo [LOI] Dọn quầy clean cần CPython 3.11 x64.
  echo [LOI] Runtime ảnh AUTO_PRO hiện dùng native extension cp311; Python 3.12/3.13 không được phép chạy Multi DEV.
  echo [GOI Y] Kiem tra bang: py -0p
  pause
  goto :done
)

for /f "delims=" %%V in ('%KVTM_PYTHON% -c "import platform,sys; print(sys.version.split()[0] + ' ' + platform.architecture()[0])"') do set "KVTM_PYTHON_INFO=%%V"
echo [KVTM DEV] Python=%KVTM_PYTHON_INFO%

echo [KVTM DEV] Prewarming clean Don quay runtime...
%KVTM_PYTHON% prepare_clear_stall_runtime.py
if errorlevel 1 (
  echo [LOI] Clean Don quay runtime prewarm FAILED. Multi DEV will not start.
  pause
  goto :done
)

%KVTM_PYTHON% kvtm_multi_dev_entry.py

:done
endlocal
