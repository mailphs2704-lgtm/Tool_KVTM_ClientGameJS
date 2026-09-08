# AUTO MULTI DEV — LATEST HANDOFF

Cập nhật: 2026-09-08

Đây là handoff ngắn cho phiên AI kế tiếp. Tài liệu chi tiết mới nhất:

`docs/AUTO_MULTI_DEV_AUTO_BUILDER_V13_HANDOFF.md`

## Trạng thái hiện tại

- Branch: `develop/multi-auto-dev`.
- Feature hiện tại: `TỰ TẠO AUTO v1.3`.
- Status: `SOURCE IMPLEMENTED / STATIC CONTRACT UPDATED / WINDOWS LIVE PENDING`.
- Không gọi runtime PASS trước khi operator build + live test trên Windows.

## Sửa nghĩa Load Function theo yêu cầu mới nhất

`📂 Load Function` không được chỉ mở một wrapper 1 dòng.

Function đã làm trước đó:

`9 Táo sấy - 9 Vải vàng`

phải show đầy đủ ordered execution blueprint gồm:

- MODULE;
- CLICK;
- SWIPE;
- WAIT;
- NHẬN DIỆN;
- GATE / HẬU KIỂM;
- LOOP / NHÁNH.

Full manifest hiện nằm tại:

`source-archive/multi-current/kvtm_multi_tool/auto_builder_function1_manifest.py`

UI render Function built-in thành:

`FULL SOURCE VIEW • chỉ đọc • runtime vẫn gọi proven function_1`

Blueprint hiển thị không thay business runtime. Khi bundle plan, document built-in được thay `steps` bằng `runtime_steps` là wrapper proven `function_1` trước khi worker validate/run.

File AppData seed cũ chỉ có 1 row FUNCTION được tự refresh theo `manifest_version`; operator không cần xóa AppData thủ công.

## Những gì v1.2 vẫn giữ

### Swipe nhiều điểm / nhiều đoạn

- Step lưu ordered `points=[[x,y], ...]`, tối thiểu 2 điểm.
- Live picker kéo nhiều lần, có Undo/Xóa đường.
- Runtime dùng một `driver.swipe_points(points, duration=...)` / native BATCH_SWIPE.
- Không chia thành nhiều swipe rời.

### Nhận diện ảnh đúng hai nguồn

1. `1 • Thư viện Multi DEV`
2. `2 • Ảnh AUTO PRO`

Ảnh AUTO PRO được copy/dedupe vào:

`%APPDATA%\KVTM Multi DEV\auto-builder\image-library`

Step recognition sau import dùng bản copy Multi DEV, không phụ thuộc trực tiếp AUTO PRO.

## Transport bắt buộc giữ nguyên

- isolated `auto_multi_dev_worker.py`;
- strict Bridge V3;
- `CAPTURE3_WRITERMAP2`;
- `CAPTURE3_WRITERMSG1`;
- exact same-request capture;
- không stale frame;
- không HWND fallback trong AUTO runtime;
- live gesture picker chỉ dùng OpenGL shared capture;
- một owner/profile.

## Không được đụng

- Dọn quầy ổn định;
- `components/workspace/**`;
- `KVTM_WORKSPACE_CONTROL.bat`;
- profile/login/DPAPI;
- không hạ threshold hoặc thêm click mù;
- không tự phát minh route tầng chưa live-prove;
- không đổi multi-point Swipe thành nhiều swipe rời;
- không để recognition phụ thuộc trực tiếp file AUTO PRO sau import.

## NEXT duy nhất

Operator chạy:

`KVTM_DEV_CONTROL.bat` → `[1] Cap nhat source + build runtime DEV`

Không dùng `[9]` và không sửa `dist` thủ công.

Build phải có:

`AUTO MULTI DEV AUTO BUILDER STATIC CONTRACT VERIFIED`

và các dòng:

- `ui=multi-dev-native-style-multi-tab-function-editor`
- `functions=create-save-load-call-nested-no-recursion+builtin-function1-full-source-view`
- `function1_load=full-module-click-swipe-recognize-order+proven-runtime-wrapper`
- `gesture_picker=multi-segment-opengl-drag-to-logical-1000-no-hwnd-fallback`
- `swipe_runtime=one-native-swipe-points-batch`
- `recognition_library=multi-dev-first-auto-pro-copy-in`

Sau `[1]` PASS mới `[2]`.

## Thứ tự live test tiếp theo

1. Multi DEV mở bình thường.
2. `TỰ TẠO AUTO` → `📂 Load Function` → chọn `9 Táo sấy - 9 Vải vàng`.
3. Tab không còn chỉ một row FUNCTION.
4. Phải thấy nhiều row MODULE/CLICK/SWIPE/WAIT/NHẬN DIỆN/GATE/LOOP đúng thứ tự.
5. Header phải có `FULL SOURCE VIEW • chỉ đọc • runtime vẫn gọi proven function_1`.
6. Sau đó mới tiếp tục test Swipe multi-point và recognition library của v1.2.

## Blocker nghiệp vụ vẫn còn

Built-in Function 1 kết thúc sau SX Vải vàng ở khu vực tầng 3. Route `tầng 3 → main` trước sale-after-loop chưa live-prove đầy đủ. Builder không tự giải quyết/đoán route này.

## Read-first cho phiên AI kế tiếp

1. `AGENTS.md`
2. `AI_COORDINATION.md`
3. `docs/AUTO_MULTI_DEV_LATEST_HANDOFF.md`
4. `docs/AUTO_MULTI_DEV_AUTO_BUILDER_V13_HANDOFF.md`
5. `docs/AUTO_MULTI_DEV_AUTO_BUILDER_V12_HANDOFF.md` chỉ để xem lịch sử v1.2.
6. `docs/AUTO_MULTI_DEV_AUTO_BUILDER_V11_HANDOFF.md` chỉ để xem lịch sử v1.1.
