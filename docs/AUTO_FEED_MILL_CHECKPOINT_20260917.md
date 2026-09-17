# AUTO MULTI DEV — SẢN XUẤT CÁM

Date: 2026-09-17  
Branch: `develop/multi-auto-dev`  
Status: **SOURCE/STATIC PASS — WINDOWS BUILD/LIVE PENDING**

## Operator contract

- Thêm toggle `Sx cám` ngay sau `Thăm bạn`, mặc định OFF và lưu riêng từng profile.
- Chỉ xét chạy sau khi một Function đã PASS và lần bán VP tại safe boundary đã hoàn tất.
- Lần đầu chạy ở boundary hợp lệ đầu tiên; lần kế tiếp sau 2100 giây (35 phút),
  vẫn chờ boundary Function + sale gần nhất.
- Không tạo thread/poll UI mới; lịch dùng `time.monotonic()` bên trong worker riêng.

## Chuỗi thao tác logical 1000x1000

1. Từ exact-main, click NPC sói `(706, 704)` để vào map sự kiện.
2. Chờ map 4 giây; click máy xay `(316, 749)` hai lần, cách nhau 1.5 giây.
3. Chờ panel ổn định và xác nhận header/overlay.
4. Một native `swipe_points`: bông lúa `(412, 380)` → máng `(245, 558)`.
5. Chỉ khi thấy vùng timer xanh mới click X `(834, 359)`.
6. Click Nhà `(37, 963)`, chờ map 5 giây và chứng minh lại own exact-main.

Nếu không chứng minh được panel, timer hoặc exact-main, lượt Sx cám SAFE_ABORT,
recovery về main và chỉ retry sau một lần bán VP sau đó.

## Verification

- Python compile: PASS.
- `verify_multi_dev_persistent_settings_contract.py`: PASS.
- `verify_multi_dev_main_boundary_contract.py`: PASS.
- `verify_auto_main_production_contract.py`: PASS.
- Windows build/live: PENDING.

## Live gate

Control Center `[1]`, sau đó `[2]`. Chọn một tài khoản, bật `Sx cám`, chạy AUTO
với sale mỗi 1 vòng. Bằng chứng PASS cần có Function PASS → bán VP hoàn tất →
Sx cám PASS → về exact-main. Xác nhận không chạy lại trước 35 phút.
