KVTM ENGINE BRIDGE v0.13 - GIU VI TRI MAN HINH AO
====================================================

Da sua
- Khi AUTO restart client/PID, cua so moi duoc dua ve dung toa do man hinh ao
  cua cua so cu sau khi dat lai client 1000x1000.
- Named pipe duoc giu ton tai lien tuc, khong dong/mo lai sau moi diem touch.
- Python tu thu lai khi pipe dang ban hoac vua ket noi, tranh mat lenh UP.
- Khong con tinh trang con tro Cocos bi ket o trang thai dang nhan roi keo map.
- Khung game co gian tu do tu 200px, luon giu ti le vuong va khong co dai den.
- AUTO khong tu phong client ve 1000x1000.
- Anh man hinh va anh mau duoc so khop o dung ti le client dang thu nho, sau do
  ket qua duoc quy doi nguoc ve he 1000x1000.
- Khoi phuc swipe_points lien tuc, toc do swipe tuy chinh va restart dung profile.
- He toa do logic giu nguyen 1000x1000 / 240 DPI.

Cai dat
1. Dong KVTM Multi, AUTO va tat ca GameClientJS.exe.
2. Giai nen, chep de cac file trong goi vao thu muc AUTO co local_launcher.py.
3. Chay BUILD_X86.bat va doi dong BUILD OK.
4. Trong Multi, bam Bridge DLL va chon thu muc AUTO\bin.
5. Mo lai client bang Multi, sau do chay RUN_ENGINE_AUTO.bat.

Luu y
- Co the thu nho va giu nguyen kich thuoc do trong luc AUTO dang chay.
- Khong nen thu nho duoi 300x300 vi qua it pixel de nhan cac anh mau rat nho.
