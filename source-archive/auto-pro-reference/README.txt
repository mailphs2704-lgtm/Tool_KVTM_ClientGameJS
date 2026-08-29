KVTM ENGINE BRIDGE - BAN THU NGHIEM
===================================

Muc dich
- Python giu nhan dien anh, kich ban va toa do 1000x1000.
- DLL x86 gui DOWN/MOVE/UP truc tiep vao GLView cua Cocos.
- Khong di chuyen hay chiem chuot that.

Chuan bi mot lan
1. Cai Visual Studio Build Tools, chon workload Desktop development with C++.
2. Giai nen toan bo goi nay vao thu muc AUTO co san, cung cap local_launcher.py.
3. Chay BUILD_X86.bat. Can thay dong BUILD OK.

Chay
1. Mo client bang KVTM Multi; de client hien thi, khong minimize.
2. Chay RUN_ENGINE_AUTO.bat.
3. Tai danh sach thiet bi va chon client PC.

Kiem tra an toan
- Chi ho tro GameClientJS.exe va libcocos2d.dll 32-bit cua goi da cung cap.
- DLL giai quyet ham bang ten export, khong ghi de code engine.
- Moi client co pipe rieng: \\.\pipe\KVTM-Cocos-PID.
- Touch duoc thuc thi tren thread cua so game, sau do goi handleTouchesBegin,
  handleTouchesMove va handleTouchesEnd.

Neu BUILD_X86 bao thieu Visual Studio
- Mo Visual Studio Installer > Modify > Desktop development with C++.
- Dam bao MSVC x86/x64 build tools va Windows SDK da duoc chon.

Khoa ti le 1:1 v0.7
- Khi keo canh/goc, vung client luon giu hinh vuong nen khong co vien den.
- Nut phong to tao cua so vuong lon nhat vua vung lam viec cua man hinh.
- Dong tat ca client truoc khi BUILD_X86.bat, sau do mo lai client de nap DLL moi.
KVTM ENGINE BRIDGE v0.9 - AUTO SAFE RESIZE
==========================================

Thay doi v0.9
- Vung client luon vuong va khong the thu nho duoi 1000x1000.
- Van keo phong lon tuy y; chieu rong va chieu cao thay doi cung nhau.
- Ngan anh chup bi mat chi tiet khi thu nho, tranh AUTO nhan sai roi keo ban do.
- He toa do logic tiep tuc la 1000x1000, moc AUTO 240 DPI.

Cai dat
1. Dong tat ca GameClientJS.exe va tool AUTO.
2. Chay BUILD_X86.bat.
3. Kiem tra bin\kvtm_bridge.dll va bin\kvtm_loader.exe vua duoc tao.
4. Trong KVTM Multi, bam Bridge DLL va chon thu muc bin nay.
5. Mo lai game bang Multi.
