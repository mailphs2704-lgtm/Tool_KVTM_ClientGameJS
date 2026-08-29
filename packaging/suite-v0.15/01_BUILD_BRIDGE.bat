@echo off
setlocal
cd /d "%~dp0AUTO_PRO"
call BUILD_X86.bat
if errorlevel 1 (
  echo.
  echo [LOI] Build Bridge that bai. Hay dong Multi, AUTO va tat ca GameClientJS roi thu lai.
  pause
  exit /b 1
)
echo.
echo [OK] Bridge nam tai AUTO_PRO\bin va Multi se tu dong tim thay.
pause
endlocal
