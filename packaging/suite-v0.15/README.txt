KVTM CLIENTJS SUITE v0.15 TEST
==============================

Muc dich
- Gom tat ca file runtime Multi va AUTO PRO vao mot thu muc duy nhat.
- Multi tu tim Bridge trong AUTO_PRO\bin, khong can chon lai thu muc bin.
- Multi tu nhan lai client dang chay sau khi Multi mo lai hoac AUTO restart PID.
- Cua so dieu khien Multi luon duoc dua ve giua man hinh chinh khi khoi dong.

Cau truc
- Multi\       : bang dieu khien, luu/mo profile, chuyen man hinh ao/chinh.
- AUTO_PRO\    : runtime AUTO PRO cu, adapter ClientJS va Engine Bridge.
- 01_BUILD_BRIDGE.bat
- 02_START_MULTI.bat
- 03_START_AUTO.bat
- 04_BUILD_MULTI_EXE.bat

Chay lan dau
1. Tat AUTO, Multi va tat ca GameClientJS.
2. Chay 01_BUILD_BRIDGE.bat, doi den BUILD OK.
3. Chay 02_START_MULTI.bat.
4. Mo cac profile game. Neu client da chay tu phien cu, cho toi da 2-4 giay de
   Multi nhan lai PID; trang thai se doi thanh "Dang chay".
5. Chon profile, bam "Sang man hinh ao" hoac "Ve man hinh chinh".
6. Chay 03_START_AUTO.bat.

Multi EXE
- Ban test nen chay 02_START_MULTI.bat de neu co loi se thay thong bao Python.
- 04_BUILD_MULTI_EXE.bat tao dang onedir on dinh tai:
  Multi\dist\KVTM-Multi\KVTM-Multi.exe
- Khong di chuyen rieng file EXE ra ngoai thu muc onedir.

Luu y
- Profile va tham so dang nhap van duoc ma hoa DPAPI tai
  %APPDATA%\KVTM Multi\profiles.json; khong dong goi du lieu tai khoan vao ZIP.
- Man hinh ao phai o che do Extend desktop.
- Khi test dat, moi dua bo nay sang thu muc chinh Tool_KVTM_GaneClientJS.
