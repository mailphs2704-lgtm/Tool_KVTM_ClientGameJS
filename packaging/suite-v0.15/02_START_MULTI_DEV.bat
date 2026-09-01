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

where py >nul 2>nul
if %errorlevel%==0 (
  echo [KVTM DEV] Prewarming clean Don quay runtime...
  py -3 prepare_clear_stall_runtime.py
  if errorlevel 1 (
    echo [LOI] Clean Don quay runtime prewarm FAILED. Multi DEV will not start.
    pause
    goto :done
  )
  py -3 kvtm_multi_dev_entry.py
  goto :done
)

where python >nul 2>nul
if %errorlevel%==0 (
  echo [KVTM DEV] Prewarming clean Don quay runtime...
  python prepare_clear_stall_runtime.py
  if errorlevel 1 (
    echo [LOI] Clean Don quay runtime prewarm FAILED. Multi DEV will not start.
    pause
    goto :done
  )
  python kvtm_multi_dev_entry.py
  goto :done
)

echo [LOI] Khong tim thay Python 3.
pause
:done
endlocal
