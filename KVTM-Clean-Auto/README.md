# KVTM Clean Auto

Mã nguồn mới cho Multi + AUTO chạy trực tiếp với GameClientJS.

## Nguyên tắc

- `source-archive/` chỉ là bản tham chiếu, không sửa trực tiếp.
- `KVTM-Clean-Auto/` là mã nguồn chính.
- Không sử dụng LDPlayer hoặc ADB trong runtime mới.
- Capture, click và swipe đi qua GameClientJS/Engine Bridge.
- Tọa độ logic luôn chuẩn hóa ở 1000 x 1000.
- Không lưu tài khoản, session, token hay key trong Git.

## Cấu trúc

- `app/`: giao diện Multi và điều phối tài khoản.
- `automation/`: tác vụ AUTO và state machine.
- `vision/`: nhận diện ảnh.
- `engine/`: capture, click, swipe và quy đổi tọa độ.
- `bridge/`: DLL C++ x86 và loader.
- `assets/`: ảnh mẫu cần cho nhận diện.
- `config/`: schema và cấu hình mặc định, không chứa dữ liệu đăng nhập.
- `tests/`: kiểm thử offline.
- `docs/`: tài liệu kiến trúc và nhật ký chuyển đổi.
- `legacy-reference/`: bản sao chọn lọc từ AUTO PRO để đối chiếu, không chạy trực tiếp.

Chạy `scripts/IMPORT_REQUIRED_FILES.ps1` một lần sau khi checkout nhánh này để tạo cấu trúc và chép các file nền cần thiết từ `source-archive/`.
