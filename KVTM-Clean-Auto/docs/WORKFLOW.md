# Quy trình phát triển và nghiệm thu

## Thư mục cố định trên máy Windows

- Multi thử nghiệm: `C:\Users\15130\Desktop\Multi_autoKVTM`
- AUTO PRO tham chiếu/thử nghiệm: `C:\Users\15130\Desktop\AUTO_KVTM_PRO_recovered_local_FIXED2\AUTO_KVTM_PRO_recovered_local`
- Dự án chính: `C:\Users\15130\Desktop\Tool_KVTM_GaneClientJS`

## Quy tắc bắt buộc

1. Không thử nghiệm trực tiếp trong thư mục dự án chính.
2. Mọi thay đổi được tạo và chạy ở một trong hai thư mục cũ.
3. Chỉ module đã được người dùng xác nhận PASS mới được chuyển vào `KVTM-Clean-Auto/`.
4. Khi chuyển, đổi sang tên chính thức; không giữ các hậu tố như `legacy`, `fixed`, `test`, `v013`.
5. Không chuyển build cache, runtime đóng gói, VDD, máy ảo, ADB, token, session hoặc dữ liệu tài khoản.
6. Mỗi lần chuyển phải ghi vào `docs/PASS_LOG.md`: nguồn, đích, chức năng, ngày kiểm thử và kết quả.
7. Sau khi chuyển phải chạy lại kiểm thử từ thư mục chính trước khi commit.

## Tên chính thức

| Thành phần | Đường dẫn chính thức |
|---|---|
| Giao diện Multi | `app/multi_app.py` |
| Điều phối AUTO | `automation/orchestrator.py` |
| Driver GameClientJS | `engine/game_client.py` |
| Capture | `engine/capture.py` |
| Input click/swipe | `engine/input.py` |
| Nhận diện ảnh | `vision/matcher.py` |
| Bridge DLL | `bridge/native/kvtm_bridge.cpp` |
| Loader x86 | `bridge/native/kvtm_loader.cpp` |
| Cấu hình chuẩn | `config/defaults.json` |

Không chép nguyên AUTO PRO thành sản phẩm mới. Logic cần thiết được đọc, viết lại theo module sạch, kiểm thử, rồi mới promote.
