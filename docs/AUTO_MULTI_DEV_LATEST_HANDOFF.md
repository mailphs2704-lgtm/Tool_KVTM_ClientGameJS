# AUTO MULTI DEV — LATEST HANDOFF

Cập nhật: 2026-09-08

Đây là handoff ngắn cho phiên AI kế tiếp. Tài liệu chi tiết mới nhất:

`docs/AUTO_MULTI_DEV_AUTO_BUILDER_V12_HANDOFF.md`

## Trạng thái hiện tại

- Branch: `develop/multi-auto-dev`.
- Baseline trước Builder v1.2: `22a676c25d274d767d494091230a9e883b37a9be`.
- Feature: `TỰ TẠO AUTO v1.2`.
- Status: `SOURCE IMPLEMENTED / STATIC CONTRACT UPDATED / WINDOWS LIVE PENDING`.
- Không gọi runtime PASS trước khi operator build + live test trên Windows.

## Những gì v1.2 vừa thêm

### 1. Swipe nhiều điểm / nhiều đoạn

Builder Swipe không còn giới hạn 2 điểm. Step lưu ordered `points=[[x,y], ...]` với tối thiểu 2 điểm.

Live picker cho phép kéo nhiều lần để thêm đoạn vào cùng đường, hiển thị toàn polyline, có `Undo đoạn cuối` và `Xóa đường`.

Runtime phải thực thi **một** `driver.swipe_points(points, duration=...)` để Bridge V3 chạy native BATCH_SWIPE; không chia thành nhiều swipe rời.

### 2. Nhận diện ảnh có đúng hai nguồn

Nguồn 1:

`1 • Thư viện Multi DEV`

Thư viện persistent:

`%APPDATA%\KVTM Multi DEV\auto-builder\image-library`

Nguồn 2:

`2 • Ảnh AUTO PRO`

AUTO PRO được resolve từ package sibling của `Multi`. Khi chọn ảnh AUTO PRO, Builder bắt buộc copy/dedupe ảnh đó sang `image-library` và step sử dụng bản copy trong thư viện Multi DEV. Nếu thư viện Multi đang trống, UI báo và chuyển sang catalog AUTO PRO.

### 3. Load được Function đã làm trước đó

Store tự seed wrapper persistent:

`builtin_function_1_existing`

Tên:

`9 Táo sấy - 9 Vải vàng`

Wrapper chỉ gọi proven built-in `function_1`; không biến/đoán lại Function 1 thành gesture JSON. `list_functions()` đặt wrapper này lên đầu để `📂 Load Function` thấy ngay.

## Những gì v1.1 vẫn giữ

- editor `ttk.Notebook` nhiều tab;
- `QUY TRÌNH CHÍNH`;
- `＋ Function mới`;
- `📂 Load Function`;
- saved Function library persistent;
- `call_saved_function` + nested Function;
- recursion guard trước khi thao tác game;
- mỗi tab Save / Run riêng;
- single-worker/single-capture-owner trên cùng profile.

## Transport bắt buộc giữ nguyên

- isolated `auto_multi_dev_worker.py`;
- strict Bridge V3;
- `CAPTURE3_WRITERMAP2`;
- `CAPTURE3_WRITERMSG1`;
- exact same-request capture;
- không stale frame;
- không HWND fallback trong AUTO runtime;
- live gesture picker cũng chỉ dùng OpenGL shared capture;
- một owner/profile.

## Không được đụng

- Dọn quầy ổn định;
- `components/workspace/**`;
- `KVTM_WORKSPACE_CONTROL.bat`;
- profile/login/DPAPI;
- không hạ threshold hoặc thêm click mù;
- không tự phát minh route tầng chưa live-prove;
- không đổi multi-point Swipe thành nhiều swipe rời;
- không để step recognition phụ thuộc trực tiếp file AUTO PRO sau import.

## NEXT duy nhất

Operator chạy:

`KVTM_DEV_CONTROL.bat` → `[1] Cap nhat source + build runtime DEV`

Không dùng `[9]` và không sửa `dist` thủ công.

Build phải có:

`AUTO MULTI DEV AUTO BUILDER STATIC CONTRACT VERIFIED`

và các dòng v1.2:

- `ui=multi-dev-native-style-multi-tab-function-editor`
- `functions=create-save-load-call-nested-no-recursion+builtin-function1-loadable`
- `gesture_picker=multi-segment-opengl-drag-to-logical-1000-no-hwnd-fallback`
- `swipe_runtime=one-native-swipe-points-batch`
- `recognition_library=multi-dev-first-auto-pro-copy-in`

Sau `[1]` PASS mới `[2]`.

## Thứ tự live test tiếp theo

1. Multi DEV mở bình thường.
2. `TỰ TẠO AUTO` → `📂 Load Function` → phải thấy `9 Táo sấy - 9 Vải vàng`.
3. Swipe live: tạo tối thiểu 3 điểm/2 đoạn, thử Undo, thêm lại đoạn, bấm `Dùng Swipe này`; row phải hiện số điểm/số đoạn.
4. Recognition: chọn nguồn 1; nếu chưa có ảnh thì chuyển nguồn 2; chọn ảnh AUTO PRO và xác nhận copy; mở lại recognition nguồn 1 để thấy ảnh vừa copy.
5. Runtime test Swipe nhỏ, an toàn; log phải có `Swipe nhiều điểm • points=... • segments=...`.
6. Chỉ khi plumbing v1.2 PASS mới dùng Function tự tạo/path nhiều đoạn cho sản xuất thật.

## Blocker nghiệp vụ vẫn còn

Built-in Function 1 kết thúc sau SX Vải vàng ở khu vực tầng 3. Route `tầng 3 → main` trước sale-after-loop chưa live-prove đầy đủ. Builder v1.2 không tự giải quyết/đoán route này.

## Read-first cho phiên AI kế tiếp

1. `AGENTS.md`
2. `AI_COORDINATION.md`
3. `docs/AUTO_MULTI_DEV_LATEST_HANDOFF.md`
4. `docs/AUTO_MULTI_DEV_AUTO_BUILDER_V12_HANDOFF.md`
5. `docs/AUTO_MULTI_DEV_AUTO_BUILDER_V11_HANDOFF.md` chỉ để xem lịch sử v1.1.
6. `docs/AUTO_MULTI_DEV_AUTO_BUILDER_HANDOFF.md` chỉ để xem lịch sử v1.
