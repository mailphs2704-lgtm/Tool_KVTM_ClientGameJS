@echo off
setlocal
cd /d "%~dp0"
set "KVTM_MULTI_APP_DIR=%~dp0data-dev"
set "KVTM_MULTI_INSTANCE_NAME=KVTM Multi DEV"
set "KVTM_MULTI_ISOLATED=1"
if not exist "%KVTM_MULTI_APP_DIR%" mkdir "%KVTM_MULTI_APP_DIR%"
cd /d "%~dp0Multi"
if not exist "kvtm_multi_dev_host.py" (
  echo [LOI] Thieu Multi\kvtm_multi_dev_host.py
  pause
  goto :done
)
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

set "KVTM_PYTHON="
where py >nul 2>nul
if not errorlevel 1 (
  py -3.11 -c "import struct,sys; raise SystemExit(0 if sys.version_info[:2] == (3,11) and struct.calcsize('P')*8 == 64 else 1)" >nul 2>nul
  if not errorlevel 1 set "KVTM_PYTHON=py -3.11"
)

if not defined KVTM_PYTHON (
  where python >nul 2>nul
  if not errorlevel 1 (
    python -c "import struct,sys; raise SystemExit(0 if sys.version_info[:2] == (3,11) and struct.calcsize('P')*8 == 64 else 1)" >nul 2>nul
    if not errorlevel 1 set "KVTM_PYTHON=python"
  )
)

if not defined KVTM_PYTHON (
  echo [LOI] Don quay clean can CPython 3.11 x64.
  echo [LOI] Runtime anh AUTO_PRO dung native extension cp311; Python 3.12/3.13 khong duoc phep chay Multi DEV.
  echo [GOI Y] Kiem tra cac Python da cai bang: py -0p
  pause
  goto :done
)

for /f "delims=" %%V in ('%KVTM_PYTHON% -c "import struct,sys; print(sys.version.split()[0] + ' ' + str(struct.calcsize('P')*8) + '-bit')"') do set "KVTM_PYTHON_INFO=%%V"
echo [KVTM DEV] Python=%KVTM_PYTHON_INFO%
echo [KVTM DEV] Starting ONE resident host: image runtime -^> Multi UI -^> probe thread

%KVTM_PYTHON% kvtm_multi_dev_host.py
if errorlevel 1 (
  echo [LOI] Multi DEV resident host exited with an error.
  pause
)

:done
endlocal
