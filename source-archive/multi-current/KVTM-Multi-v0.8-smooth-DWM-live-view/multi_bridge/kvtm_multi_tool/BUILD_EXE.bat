@echo off
setlocal
cd /d "%~dp0"
py -3 -m pip install --upgrade pyinstaller
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name "KVTM-Multi" kvtm_multi.py
echo.
echo File EXE: dist\KVTM-Multi.exe
pause
endlocal
