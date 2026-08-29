# Tool_KVTM_Pro_coverByCry

Bản AUTO KVTM PRO phục hồi chạy local + Web Control.

## Chạy hằng ngày

Các launcher chính hiện chạy **không giữ cửa sổ CMD**:

- `RUN_LOCAL.bat` → mở AUTO Python/Tkinter bằng `pyw/pythonw` khi có thể.
- `RUN_WEB.bat` → mở Web tại `http://127.0.0.1:8080`, Node chạy nền.
- `STOP_WEB.bat` → tắt Web nền.
- `RUN_PUBLIC.bat` → mở Cloudflare Quick Tunnel nền và copy URL public vào clipboard.
- `STOP_PUBLIC.bat` → tắt gateway + tunnel public.
- `UPDATE.bat` → `git pull origin main` chạy ẩn và báo kết quả bằng hộp thoại nhỏ.

`launchers/install_shortcuts.ps1` tạo shortcut Desktop để chạy **hoàn toàn không ló CMD**. Shortcut `AUTO KVTM PRO` dùng icon lấy từ ảnh KVTM trong `assets`. Muốn ép một ảnh cụ thể, đặt PNG tại `local_data/launcher_icon.png` rồi chạy lại script tạo shortcut hoặc chạy `UPDATE.bat`.

Các shortcut được tạo:

- `AUTO KVTM PRO`
- `AUTO KVTM WEB`
- `STOP AUTO KVTM WEB`
- `AUTO KVTM PUBLIC`
- `STOP AUTO KVTM PUBLIC`
- `UPDATE AUTO KVTM`

Log nền nằm trong `local_data/` thay vì giữ cửa sổ console trên taskbar.

## Cấu trúc

- `local_launcher.py`: launcher local, không cần key/server license.
- `local_launcher_v10.py`: entrypoint hiện tại + các local bridge.
- `local_bridge.py`: bridge localhost nằm **trong cùng process launcher**, để Web đọc/điều khiển đúng `TaskManager` thật.
- `runtime/pyc/`: bytecode AUTO đã phục hồi.
- `_internal/`, `platform-tools/`: runtime/native dependencies và ADB.
- `web_control/`: Node.js Web Control.
- `launchers/`: VBS/PowerShell helper chạy nền, shortcut và updater.

## Web Control

- Trạng thái AUTO lấy trực tiếp từ TaskManager thật trong launcher.
- START/STOP gửi về đúng launcher đang chạy, không tạo engine AUTO thứ hai.
- Danh sách chức năng lấy đúng tên hiển thị của `FUNCTION_OPTIONS`.
- Live View là **view-only**, không tap/swipe emulator.
- Live View H.264 + WebCodecs; emulator có preset `1000x1000 @ 240 DPI`.
- Tùy chọn AUTO và các setting phụ được bridge trực tiếp về launcher.
- Chức năng chính là single-select, có Yêu thích và nhóm thao tác chức năng.

## Lưu ý

Sau khi cập nhật file Python bridge/launcher, cần đóng AUTO cũ và mở lại `AUTO KVTM PRO`/`RUN_LOCAL.bat` để code mới được nạp.

Dữ liệu tài khoản Web, bridge token, log và DB local không commit lên Git.
