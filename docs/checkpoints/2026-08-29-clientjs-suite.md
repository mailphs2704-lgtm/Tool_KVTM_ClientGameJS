# Checkpoint KVTM ClientGameJS Suite — 2026-08-29

## Trạng thái chốt

Dự án tạm dừng trên nhánh `test/function-builder-core`.

Bản đóng gói hiện tại:

- `dist/KVTM-ClientJS-Suite-v0.15.1-test`
- Multi đã khởi động thành công bằng `02_START_MULTI.bat`.
- Shared-memory capture và Live View đã hoạt động.
- Khung OpenGL đã được chuẩn hóa xoay 180 độ trong native bridge.
- Live View đặt mục tiêu tối đa 30 FPS và chỉ capture khi cửa sổ xem được mở.
- AUTO PRO cũ được nối với ClientGameJS qua Engine Bridge.
- Hồ sơ Multi có ID cố định; PID chỉ còn là định danh runtime.

## Mục tiêu kiến trúc hiện tại

```text
Hồ sơ tài khoản (profile_id cố định)
        │
        ├── Multi theo dõi PID ClientGameJS hiện tại
        ├── running_clients.json công bố profile_id → PID
        └── AUTO dùng PCID:<profile_id>
                    │
                    └── tự tìm lại PID mới sau khi ClientGameJS reset
```

Không dùng PID làm danh tính lâu dài của tài khoản. Khi game reset, AUTO phải giữ nguyên `PCID` và chỉ cập nhật PID runtime.

## Các phần đã thực hiện

### Multi

- Lưu và mở lại nhiều hồ sơ ClientGameJS.
- Mã hóa tham số đăng nhập bằng Windows DPAPI.
- Chia danh sách tài khoản Online và Offline.
- Checkbox chọn một hoặc nhiều tài khoản.
- Hiển thị tên hồ sơ và PID runtime.
- Live View chỉ truyền hình khi người dùng bấm xem.
- Hỗ trợ chuyển client sang màn hình ảo và về màn hình chính.
- Khóa vùng game theo mốc logic 1000×1000.
- Tự nhận lại các client đang chạy dựa trên chữ ký hồ sơ.
- Công bố ánh xạ tài khoản tại:
  `%APPDATA%\KVTM Multi\running_clients.json`.

### An toàn dữ liệu hồ sơ

- Ghi `profiles.json` qua file tạm rồi thay thế nguyên tử.
- Chặn ghi đè nếu danh sách trong bộ nhớ vô tình ít hơn dữ liệu trên ổ đĩa.
- Giữ năm thế hệ `profiles.bak1..bak5`.
- Tạo tối đa 30 snapshot có timestamp trong `profile-backups`.
- Tự phục hồi từ backup hợp lệ khi file chính hỏng.

### Native Engine Bridge

- DLL x86 giao tiếp trực tiếp với Cocos/GameClientJS.
- Named pipe cho thao tác `DOWN`, `MOVE`, `UP`, `PING`, `CAPTURE`.
- Shared memory `KCAP` cho ảnh BGRA, tránh truyền ảnh qua file trung gian.
- Seqlock/frame ID để tránh AUTO đọc khung hình đang ghi dở.
- Capture OpenGL có fallback FRONT/BACK buffer.
- Chuẩn hóa khung hình bị xoay 180 độ ngay trong DLL để Multi và AUTO dùng cùng một hướng ảnh.
- Swipe nội suy đầy đủ các điểm để tạo kéo liên tục.

### AUTO PRO ClientJS adapter

- `EngineDriver` thay lớp thao tác ADB cho thiết bị PC.
- Click/swipe được gửi vào Cocos, không chiếm chuột Windows.
- Ảnh AUTO được lấy từ shared memory; có đường fallback Windows.
- Quy đổi thao tác theo hệ tọa độ chuẩn 1000×1000.
- Có thông số chỉnh tốc độ kéo quầy.
- Quy trình mở lại game ClientJS không còn phụ thuộc icon launcher Android.
- Thiết bị mới dùng `PCID:<profile_id>` thay cho `PC:<PID>`.
- Khi PID cũ chết, driver tìm tiến trình mới theo hồ sơ đã mã hóa và nạp lại Bridge.

### Function Builder

Đã có nền móng thử nghiệm cho:

- Thêm thao tác click.
- Tạo đường swipe nhiều điểm.
- Kéo điểm trực tiếp trên ảnh.
- Lưu thao tác thành danh sách/chức năng JSON.
- Check ảnh và điều kiện chạy.
- Live View cho trang tạo chức năng.

Phần Function Builder chưa được xem là bản AUTO ổn định và sẽ tiếp tục ở giai đoạn sau.

## File chính cần biết

| Vai trò | Đường dẫn trong repo |
|---|---|
| Multi hiện tại | `source-archive/multi-current/kvtm_multi_tool/kvtm_multi.py` |
| PC capture/input adapter | `source-archive/multi-current/kvtm_multi_tool/pc_driver.py` |
| AUTO EngineDriver | `test-candidates/auto-pro-clientjs-temp/engine_driver.py` |
| AUTO launcher | `test-candidates/auto-pro-clientjs-temp/pc_auto_engine_launcher.py` |
| AUTO patch | `test-candidates/auto-pro-clientjs-temp/clientjs_auto_patch.py` |
| Native DLL source | `test-candidates/auto-pro-clientjs-temp/native/kvtm_bridge.cpp` |
| Bộ đóng gói | `packaging/suite-v0.15/BUILD_FULL_PACKAGE.ps1` |
| Function Builder | `test-candidates/function-builder-core` |

## Build sạch trên Windows

Trước khi đóng gói phải đóng Multi, AUTO, Python và GameClientJS vì DLL đã nạp sẽ bị Windows khóa.

```powershell
Get-Process GameClientJS, python, pythonw, kvtm_multi -ErrorAction SilentlyContinue |
Stop-Process -Force

Start-Sleep -Seconds 2

cd "$env:USERPROFILE\Desktop\Tool_KVTM_ClientGameJS"
git switch test/function-builder-core
git pull --ff-only origin test/function-builder-core

powershell -ExecutionPolicy Bypass -File ".\packaging\suite-v0.15\BUILD_FULL_PACKAGE.ps1"

cd ".\dist\KVTM-ClientJS-Suite-v0.15.1-test"
.\01_BUILD_BRIDGE.bat
.\04_BUILD_MULTI_EXE.bat
```

Chạy bản Python mới nhất:

```powershell
.\02_START_MULTI.bat
```

Chạy AUTO:

```powershell
.\03_START_AUTO.bat
```

## Lưu ý kiểm thử khi tiếp tục

1. Không chạy lại EXE cũ nằm ngoài thư mục `dist` mới.
2. Sau khi sửa native bridge, phải đóng toàn bộ GameClientJS và chạy lại `01_BUILD_BRIDGE.bat`.
3. Nếu AUTO từng lưu thiết bị dạng `PC:<PID>`, chọn lại tài khoản một lần để chuyển sang `PCID:<profile_id>`.
4. Cần kiểm thử riêng kịch bản:
   - AUTO đang chạy.
   - ClientGameJS reset và sinh PID mới.
   - Multi cập nhật `running_clients.json`.
   - AUTO tự bind lại đúng tài khoản và tiếp tục.
5. Kiểm tra chiều ảnh ở cả Live View và AUTO image matching sau mỗi thay đổi DLL.
6. 30 FPS là mức mục tiêu, không phải cam kết cứng nếu OpenGL/driver chậm.
7. Một khung 1000×1000 BGRA khoảng 4 MB; 30 FPS tương đương khoảng 120 MB/s dữ liệu thô cho mỗi Live View đang mở.

## Các commit cuối của checkpoint

- `d686c7f` — chuẩn hóa xoay ảnh ClientJS trong native bridge.
- `474abf1` — Multi render shared frame top-down.
- `fc82278` — AUTO dùng frame top-down đã chuẩn hóa.
- `f58cf23` — bảo vệ tra cứu hồ sơ trước khi driver khởi tạo.
- `1800013` — EngineDriver kết nối bằng profile ID cố định.
- `91016a3` — đưa cơ chế profile ID cố định vào gói AUTO.
- `f620377` — công bố thiết bị ClientJS bằng stable profile ID.

## Điểm tiếp tục dự kiến

Khi mở lại dự án, ưu tiên theo thứ tự:

1. Test end-to-end việc ClientGameJS đổi PID khi AUTO đang chạy.
2. Xác nhận Live View và AUTO nhận ảnh đúng chiều trên bản DLL vừa build.
3. Thêm trạng thái/version của DLL vào giao diện để tránh chạy nhầm binary cũ.
4. Hoàn thiện Function Builder sau khi nền AUTO PRO tạm thời ổn định.
5. Sau khi các bài test pass mới chuyển file chuẩn hóa sang thư mục sản phẩm chính.

---

Checkpoint này chỉ ghi nhận trạng thái kỹ thuật hiện tại. Dự án tạm dừng tại đây, chưa merge vào nhánh chính.
