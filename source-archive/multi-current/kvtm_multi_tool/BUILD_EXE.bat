@echo off
setlocal
cd /d "%~dp0"
py -3 -m pip install --upgrade pyinstaller
py -3 -m PyInstaller --noconfirm --clean --onedir --windowed --name "KVTM-Multi" kvtm_multi.py
echo.
echo Thu muc chay: dist\KVTM-Multi\
echo File EXE: dist\KVTM-Multi\KVTM-Multi.exe
pause
endlocal
