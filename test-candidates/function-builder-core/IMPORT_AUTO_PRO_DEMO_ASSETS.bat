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
for %%F in (x.png close_game.png icon_home.png quay_hang.png check_xuong.png harvestBasket.png next_gieo.png next_gieo_trai.png o_trong.png o_sx.png fullkho.png cay_hong.png cay_tuyet.png cay_tao.png cay_bong.png tao_say.png nuoc_tao.png vai_vang.png tinh_dau_hh.png kho_tao_say.png kho_nuoc_tao.png kho_vai_vang.png kho_tinh_dau_hh.png) do (
  if exist "%SOURCE%\%%F" copy /Y "%SOURCE%\%%F" "%DEST%\%%F" >nul
)
echo Da dua asset demo vao: %DEST%
pause
