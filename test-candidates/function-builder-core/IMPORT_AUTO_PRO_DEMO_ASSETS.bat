@echo off
setlocal
if "%~1"=="" (
  echo Keo thu muc AUTO_KVTM_PRO_recovered_local vao file BAT nay.
  echo Hoac chay: IMPORT_AUTO_PRO_DEMO_ASSETS.bat "C:\duong-dan\AUTO_KVTM_PRO_recovered_local"
  pause
  exit /b 2
)
set "SOURCE=%~1\assets\items"
set "DEST=%~dp0workspace\assets"
if not exist "%SOURCE%" (
  echo Khong tim thay: %SOURCE%
  pause
  exit /b 3
)
if not exist "%DEST%" mkdir "%DEST%"
for %%F in (check_log_game.png x.png dong_y.png tao_say.png kho_tao_say.png vai_vang.png kho_vai_vang.png tinh_dau_hh.png kho_tinh_dau_hh.png thu_hoach.png) do (
  if exist "%SOURCE%\%%F" copy /Y "%SOURCE%\%%F" "%DEST%\%%F" >nul
)
echo Da dua asset demo vao: %DEST%
pause
