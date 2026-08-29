KVTM MULTI 0.4 - TU NAP BRIDGE VA KHOA KHUNG VUONG
================================

Muc dich
- Dang nhap moi tai khoan bang ZingPlay chinh thuc mot lan.
- Luu client dang chay thanh ho so.
- Lan sau mo nhieu ho so truc tiep, khong can mo launcher.

Cach dung
1. Giai nen tool tren may da cai ZingPlay va KVTM.
2. Chay RUN_KVTM_MULTI.bat.
3. Muon them tai khoan:
   - Chi de mot client KVTM dang chay.
   - Bam "+ Luu client dang chay".
   - Dat ten ho so.
4. Dong ZingPlay va game de thu.
5. Chon ho so, bam "Mo da chon" hoac "Mo tat ca".

Do phan giai
- Khi mo, tool dat vung game ban dau thanh 1000 x 1000 pixel.
- Sau do van co the keo co gian. Bridge khoa ti le vung game 1:1, nen chieu
  rong va chieu cao doi cung nhau, vien bam sat game va khong co 4 dai den.
- He toa do auto luon la 1000 x 1000; moc quy doi la 240 DPI.
- Nut "Do phan giai" cho phep thay doi ba gia tri nay.
- DPI tren day la moc quy doi cua auto; Windows khong cho ep DPI man hinh that
  rieng cho mot cua so giong nhu Android/LDPlayer.

Bridge DLL - Multi tu quan ly
1. Neu thu muc bin nam ngay canh tool, Multi tu tim thay.
2. Neu bin dang nam trong thu muc AUTO cu, bam "Bridge DLL" va chon dung
   thu muc bin co hai file kvtm_loader.exe va kvtm_bridge.dll. Chi chon 1 lan.
3. Multi tu nap DLL vao tat ca GameClientJS dang chay, client vua mo va PID moi
   sau khi game khoi dong lai. Tool AUTO chi con gui click/swipe.
4. Neu bam mo ho so khi chua cau hinh Bridge, Multi se yeu cau chon thu muc bin
   truoc, tranh mo game ma khong co khoa khung vuong.

Preview thu nho (v0.5)
- Chon mot client dang chay va bam "Preview thu nho".
- Multi giu client that render 1000x1000 o ngoai man hinh, sau do hien thi mot
  cua so DWM Preview co the thu nho tuy y.
- v0.5.1 giu mot dai 32px cua client that sat mep phai va dat xuong duoi cac
  cua so khac, ngan Cocos/DWM dung render khi client nam hoan toan ngoai desktop.
- AUTO chup client that nen chat luong nhan dien va toa do khong thay doi.
- Dong Preview de dua cua so game that tro lai vi tri cu.
- Khong minimize client that trong Taskbar khi dang dung Preview.

Man hinh ao (v0.6 - khuyen dung)
- Windows phai co it nhat 2 display va dang o che do Extend desktop.
- Chon mot hoac nhieu ho so dang chay, bam "Sang man hinh ao".
- Multi chon man hinh phu co dien tich lon nhat, dat moi client ve 1000x1000
  va tu xep client tren man hinh do.
- Bam "Ve man hinh chinh" de dua client da chon tro lai.
- 4 client nen dat man hinh ao toi thieu 2200x2200 de tinh ca vien/title bar.
- Khong minimize GameClientJS va khong Disconnect man hinh ao khi AUTO chay.

Live View (v0.7)
- Moi dong co o "Bam de xem". Chi khi bam vao o nay, Multi moi bat dau chup
  Live View 112x112 cua tai khoan do; bam lai de dung va giai phong tai nguyen.
- Anh cap nhat khoang moi 1 giay, ke ca client nam tren man hinh ao.
- Thumbnail chi dung de quan sat; AUTO van chup/nhan dien client 1000x1000.
- Nhieu client se duoc chup lan luot de han che CPU va GDI.
- Chuyen man hinh thuc hien hai giai do: cho WM_DPICHANGED 400ms, sau do moi
  dat lai client 1000x1000. Khong con phai bam nut chuyen hai lan.
- v0.7.1 dat hai thanh dieu khien phia tren danh sach, nen Treeview khong the
  chiem het chieu cao va lam mat cac nut khi cua so bi thap/doi DPI.
- v0.8 thay chup PrintWindow 1 FPS bang DWM Thumbnail truc tiep. Hinh duoc
  Windows compositor cap nhat muot gan nhu xem cua so game, khong copy anh bang
  CPU. Chi dang ky DWM khi bam vao o Live View; bam lai se huy thumbnail.

Bao mat
- Tool khong luu mat khau ZingPlay.
- Tham so phien duoc ma hoa bang Windows DPAPI.
- Ho so chi giai ma duoc bang dung tai khoan Windows da tao no.
- Khong gui du lieu qua Internet.

Gioi han ban thu
- May chu ZingPlay/KVTM co the lam het han phien. Khi do dang nhap lai bang
  launcher va luu trung ten ho so de cap nhat.
- Neu nhieu client tranh chap du lieu cuc bo, ban sau se tach thu muc du lieu
  rieng cho tung ho so sau khi co ket qua thu nghiem.
- Phan auto PC se duoc gan sau khi xac nhan co the mo on dinh nhieu client.

Chup kiem tra cho adapter auto PC
- Mo mot ho so bang tool, chon ho so do va bam "Chup kiem tra".
- Anh duoc luu trong %APPDATA%\KVTM Multi\diagnostics.
- Anh BMP khong can cai them Pillow/PIL.
- Anh nay dung de can chinh toa do va bo nhan dien cua auto LDPlayer sang PC.

Xem truoc swipe 4 tang
- Chon mot client dang chay, bam "Xem swipe 4 tang".
- Huong swipe that da hieu chinh la (387,918) -> (387,69).
- Cham xanh la diem bat dau; duong/mui ten do la huong keo.
- Nut nay chi ve xem truoc, chua gui swipe that vao game.
- Nut "Thu swipe that" gui dung thao tac nay vao client sau khi hoi xac nhan.
- Anh nhan dien luon duoc chuan hoa ve 1000x1000; click/swipe duoc quy doi
  nguoc ve kich thuoc hien tai, nen resize cua so khong lam lech toa do.

Thu nghiem GUI AUTO cu voi client PC
1. Chep 3 file pc_auto_launcher.py, pc_driver.py, RUN_PC_AUTO.bat vao thu muc
   AUTO_KVTM_PRO_recovered_local, cung cap voi local_launcher.py.
2. Mo cac client can auto bang KVTM Multi.
3. Chay RUN_PC_AUTO.bat.
4. Bam tai danh sach thiet bi. Client PC se hien dang "PC - ... [PID]".
5. Ban dau chi nen chay mot client va mot nhiem vu ngan de kiem tra.

Luu y ban cau noi dau tien
- Khong cai FloatingButton.apk va khong doc logcat cho client PC.
- Reset app Android chua duoc ap dung cho PC; driver giu client dang chay.
- Neu cua so duoc resize, anh/toa do van theo he logic 1000x1000.
- Minimize xuong taskbar co the lam Cocos tam dung ve; nen resize/xep gon cua so.

Fix click Cocos v0.3.1
- Swipe co the chay bang Windows message, nhung GameClientJS bo qua click cung loai.
- Click PC nay kich hoat dung client, gui chuot trai that, sau do tra con tro ve
  vi tri cu. Cac click duoc khoa lan luot de nhieu client khong tranh con tro.
- Resize van an toan vi toa do logic duoc doi sang client va screen ngay truoc click.

Dong goi EXE
- Chay BUILD_EXE.bat tren Windows co Python.
- File tao ra nam tai dist\KVTM-Multi.exe.
