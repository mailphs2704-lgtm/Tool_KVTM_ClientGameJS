KVTM CLIENTJS SUITE - MULTI DEV
===============================

Nguon DEV hien tai:
  branch: develop/multi-auto-dev

Build tai thu muc repo:
  powershell -ExecutionPolicy Bypass -File .\packaging\suite-v0.15\BUILD_FULL_PACKAGE.ps1

Thu muc fixed DEV sau build:
  dist\KVTM-ClientJS-Suite-Multi-DEV\
  dist\KVTM-ClientJS-Suite-Multi-DEV.zip

Luu y runtime AUTO PRO:
- Khong xoa *.pyc trong AUTO_PRO.
- Repo dung Git LFS cho runtime/pyc va _internal.
- BUILD_FULL_PACKAGE.ps1 tu kiem tra Git LFS pointer truoc khi dong goi.
- data-dev, profiles/settings, clear-stall va clear-stall-probe khong nam trong ZIP.
- Rebuild fixed DEV giu lai profiles/settings, carryover Dọn quầy va anh/report probe.

Thu tu chay DEV:
1. Pull branch develop/multi-auto-dev.
2. Build package bang BUILD_FULL_PACKAGE.ps1.
3. Mo dist\KVTM-ClientJS-Suite-Multi-DEV\02_START_MULTI_DEV.bat.
4. Chon mot clone trong Multi DEV.
5. Mo tab AUTO CLIENTJS > Dọn quầy.
6. Dat Ban be so va Quay dung muc tieu.
7. Bam "Kiem tra Don quay" truoc khi chay giao dich that.

Nut KIEM TRA DON QUAY:
- Tu mo clone neu clone chua chay.
- Ket noi runtime AUTO PRO va ClientJS.
- Chi dieu huong den nha ban + quay muc tieu.
- Bat buoc screenshot ClientJS dung 1000x1000.
- Quet 4 view de phu dung 20 o quay.
- KHONG goi mua VP.
- KHONG goi ban/treo VP.
- KHONG ghi carryover giao dich.
- Luu view-01.png .. view-04.png, templates va report.json.
- Sau khi worker ket thuc, clone duoc dong theo lifecycle DEV.

Du lieu probe nam trong data-dev\clear-stall-probe\<profile-id>\<timestamp>\.
Neu probe PASS, gui report.json va 4 anh view cho buoc doi chieu toa do/nhan dang cuoi cung truoc khi bat giao dich that.

Dọn quay that van chay FIFO toan cuc: mot clone xong va dong hoan toan moi den clone tiep theo.
