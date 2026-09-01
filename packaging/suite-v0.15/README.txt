KVTM CLIENTJS SUITE - MULTI DEV
===============================

Nguon DEV hien tai:
  branch: develop/multi-auto-dev

Build tai thu muc repo:
  powershell -ExecutionPolicy Bypass -File .\packaging\suite-v0.15\BUILD_FULL_PACKAGE.ps1

Thu muc fixed DEV sau build:
  dist\KVTM-ClientJS-Suite-Multi-DEV\
  dist\KVTM-ClientJS-Suite-Multi-DEV.zip

Luu y runtime:
- Dọn quầy clean KHONG thuc thi automation.pyc / adb_controller.pyc / FarmAutomation.
- AUTO_PRO legacy van duoc dong goi chi cho cac chuc nang AUTO khac va lam tai lieu/asset tham chieu.
- Repo dung Git LFS cho runtime/pyc va _internal cua AUTO_PRO legacy.
- BUILD_FULL_PACKAGE.ps1 tu kiem tra Git LFS pointer truoc khi dong goi.
- data-dev, profiles/settings, clear-stall va clear-stall-probe khong nam trong ZIP.
- Rebuild fixed DEV giu lai profiles/settings, carryover Dọn quầy va anh/report probe.

Thu tu chay DEV:
1. Pull branch develop/multi-auto-dev.
2. Build package bang BUILD_FULL_PACKAGE.ps1.
3. Mo dist\KVTM-ClientJS-Suite-Multi-DEV\02_START_MULTI_DEV.bat.
4. Chon mot clone trong Multi DEV. Neu chi co mot clone dang chay, DEV co the tu nhan clone do.
5. Mo tab AUTO CLIENTJS > Dọn quầy.
6. Dat Ban be so va Kho VP dung muc tieu.
7. Bam "Kiem tra Don quay" truoc khi chay giao dich that.

MULTI DEV ENTRYPOINT:
- 02_START_MULTI_DEV.bat chay Multi\kvtm_multi_dev_entry.py.
- DEV tam khoa tu dong kich hoat lich Dọn quầy that trong luc live-verify.
- Clone dang mo binh thuong KHONG bi xem la mot clear-stall worker dang ban.
- Nut Kiem tra chi bi khoa khi AUTO chinh, Dọn quầy that hoac mot probe khac dang chiem ClientJS.
- Production entrypoint kvtm_multi_entry.py van giu scheduler/lifecycle that rieng biet.

Nut KIEM TRA DON QUAY:
- Tu mo clone neu clone chua chay.
- Dung KVAutomation Python clean + ClientJS bridge.
- Chi dieu huong den nha ban + quay muc tieu.
- Bat buoc screenshot ClientJS dung 1000x1000.
- Quet 4 view de phu dung 20 o quay.
- KHONG goi mua VP.
- KHONG goi ban/treo VP.
- KHONG ghi carryover giao dich.
- Luu view-01.png .. view-04.png, templates, report.json va activity.log.
- Sau khi worker ket thuc, clone duoc dong theo lifecycle DEV.

CMD LOG REALTIME:
- Khi bam Kiem tra Dọn quầy, Multi DEV mo mot cua so CMD rieng.
- CMD hien stage, progress, error/PASS va JSON raw cua probe theo thoi gian thuc.
- Dong CMD khong dung worker probe.
- CMD tu dong dong sau khi probe ket thuc.
- Ban ghi day du duoc luu tai activity.log trong cung thu muc report.

Du lieu probe nam trong:
  data-dev\clear-stall-probe\<profile-id>\<timestamp>\

Neu probe loi, gui activity.log + report.json + tat ca stage-*.png/view-*.png.
Neu probe PASS, gui report.json va 4 anh view cho buoc doi chieu toa do/nhan dang cuoi cung truoc khi bat giao dich that.

Dọn quay that van chay FIFO toan cuc trong production: mot clone xong va dong hoan toan moi den clone tiep theo.
