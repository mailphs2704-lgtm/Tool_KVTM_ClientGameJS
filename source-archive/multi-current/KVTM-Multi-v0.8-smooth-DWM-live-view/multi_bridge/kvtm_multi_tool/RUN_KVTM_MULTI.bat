@echo off
setlocal
cd /d "%~dp0"

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

echo [LOI] Khong tim thay Python.
echo Cai Python 3 bang lenh: winget install -e --id Python.Python.3.11
:done
pause
endlocal
