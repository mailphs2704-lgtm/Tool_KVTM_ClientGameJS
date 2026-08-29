KVTM CLIENTJS SUITE v0.15.1 TEST
================================

Ban nay phai duoc dung bang BUILD_FULL_PACKAGE.ps1 tu nhanh
test/function-builder-core. Khong loai bo *.pyc: AUTO PRO phuc hoi su dung
runtime\pyc\gui_base.pyc, gui.pyc va adb_controller.pyc lam module chinh.

Lenh dung tai thu muc repo:
  powershell -ExecutionPolicy Bypass -File .\packaging\suite-v0.15\BUILD_FULL_PACKAGE.ps1

Ket qua:
  dist\KVTM-ClientJS-Suite-v0.15.1-test\
  dist\KVTM-ClientJS-Suite-v0.15.1-test.zip

Thu tu chay:
1. 01_BUILD_BRIDGE.bat
2. 02_START_MULTI.bat
3. Mo/chon client va chuyen man hinh ao neu can.
4. 03_START_AUTO.bat

Multi tu nhan lai PID sau khi Multi mo lai hoac AUTO restart ClientJS.
