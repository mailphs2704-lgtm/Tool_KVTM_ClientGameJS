# AUTO KVTM PRO — recovered local build

Đây là bản phục hồi local từ executable PyInstaller Python 3.11.

## Đã loại bỏ trong luồng local

- Không cần License Key / login.
- Không gọi API `https://apikvtm.giaiphapmxh.com`.
- Không kiểm tra hạn key từ server.
- Không kiểm tra/cập nhật app qua server.
- Không gửi Telegram notification.
- Các thao tác server như wallet/order/feature được chuyển sang local stub.

## Dữ liệu local

`local_data/local.db` được tự tạo bằng SQLite khi chạy lần đầu. Dữ liệu automation cũ vẫn dùng cơ chế file/AppData của chương trình gốc.

## Cách chạy

1. Cài Python **3.11 64-bit** trên Windows.
2. Chạy `RUN_LOCAL.bat`.
3. Bản local sẽ tự đăng nhập dưới tên `LOCAL USER` và mở GUI chính.

## Tình trạng phục hồi source

- Toàn bộ PYZ của PyInstaller đã được tách thành `.pyc` Python 3.11 trong `runtime/pyc`.
- Asset, platform-tools và native `.pyd/.dll` được giữ nguyên.
- `local_launcher.py` và `local_api.py` là source mới để thay thế server/login.
- Source gốc hoàn chỉnh chưa thể khôi phục byte-for-byte (comment/formatting đã mất khi đóng gói). Các module custom đã được nhận diện và lưu danh sách trong `recovery_notes/custom_modules.txt`.

Nếu một module native báo thiếu DLL, chạy từ `RUN_LOCAL.bat` thay vì mở trực tiếp `local_launcher.py`.

## Fix native extensions (2026-08-20)

Bản FIXED đã ghép các native extension của PyInstaller (`PIL/_imaging.pyd`, các module `numpy`, `lxml`, `cryptography`...) vào đúng package trong `runtime/pyc`. `local_launcher.py` cũng tự kiểm tra và tự đồng bộ lại các file này khi khởi động.

Nếu từng giải nén bản cũ, hãy giải nén bản FIXED vào **thư mục mới**, không chép đè lên thư mục cũ.


## Fix 2026-08-20: uiautomator2 resources
This build synchronizes PyInstaller package data into `runtime/pyc` before imports.
In particular, `uiautomator2/assets/u2.jar` and the bundled APK files are now
available to uiautomator2 when it initializes a connected emulator/device.
