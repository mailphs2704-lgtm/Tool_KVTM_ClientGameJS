# AUTO MULTI DEV — AUTO BUILDER v1.2 HANDOFF

Cập nhật: 2026-09-08

## Mục tiêu v1.2

Phản hồi operator sau v1.1:

1. Swipe chỉ giữ 2 điểm/1 đoạn; cần một Swipe có nhiều đoạn liên tiếp.
2. Nhận diện ảnh phải có đúng 2 nguồn: thư viện Multi DEV trước, nếu chưa có thì chọn mục ảnh AUTO PRO; ảnh chọn từ AUTO PRO phải tự copy sang thư viện Multi DEV.
3. `Load Function` phải thấy Function `9 Táo sấy - 9 Vải vàng` đã làm trước đó.

Mốc này triển khai đúng ba yêu cầu trên, không thay Dọn quầy/Workspace/profile và không đổi Bridge V3.

## Swipe nhiều điểm / nhiều đoạn

Builder `Swipe` v1.2 lưu một đường có dạng:

```text
points = [[x1,y1], [x2,y2], [x3,y3], ...]
```

- tối thiểu 2 điểm;
- mỗi điểm trong hệ logic ClientJS `0..1000`;
- một Swipe có thể có N điểm / N-1 đoạn;
- duration là thời gian của toàn bộ đường;
- x1/y1/x2/y2 cũ vẫn được đọc để tương thích plan v1.1.

Live picker:

- operator kéo nhiều lần để thêm các đoạn vào cùng một đường;
- overlay hiển thị toàn bộ polyline đã giữ;
- có `↶ Undo đoạn cuối`;
- có `✕ Xóa đường`;
- `Dùng Swipe này` trả toàn bộ danh sách điểm;
- OpenGL shared capture only, không HWND/PrintWindow fallback.

Runtime **không** chạy N swipe rời. `AutoBuilderRunner` gọi đúng một:

```text
self.auto.driver.swipe_points(points, duration=duration)
```

nên Bridge V3 thực thi một native multi-point/BATCH_SWIPE gesture. Đây là contract bắt buộc để không phát sinh mouse-up/mouse-down giữa các đoạn.

## Thư viện ảnh nhận diện Multi DEV

Thư viện ảnh Builder persistent:

```text
%APPDATA%\KVTM Multi DEV\auto-builder\image-library
```

Khi cấu hình `NHẬN DIỆN`, UI có đúng hai lựa chọn:

1. `1 • Thư viện Multi DEV`
2. `2 • Ảnh AUTO PRO`

### Lựa chọn 1 — Multi DEV

- mở danh sách ảnh đang có trong `image-library`;
- có ô tìm kiếm;
- step dùng trực tiếp đường dẫn ảnh trong thư viện Multi DEV.

Nếu thư viện Multi DEV đang trống, UI báo rõ và chuyển sang catalog AUTO PRO.

### Lựa chọn 2 — AUTO PRO

Runtime Multi và AUTO_PRO nằm cùng package; Builder resolve thư mục AUTO PRO ở sibling của thư mục `Multi`.

- quét recursive các file PNG/JPG/JPEG/BMP/WEBP trong AUTO PRO;
- hiển thị catalog có tìm kiếm;
- khi operator chọn ảnh, Builder kiểm tra ảnh thực sự nằm dưới AUTO PRO;
- copy vào `image-library` Multi DEV;
- tên đích có prefix SHA-256 rút gọn để dedupe;
- step sau đó lưu **đường dẫn bản copy trong thư viện Multi DEV**, không phụ thuộc trực tiếp asset AUTO PRO;
- lần sau ảnh đó xuất hiện ở lựa chọn 1.

Thư mục `assets` cũ của Builder được migrate dần vào `image-library` để không làm mất ảnh đã chọn ở v1/v1.1.

## Load Function — Function đã làm trước đó

`AutoBuilderPlanStore` seed một wrapper persistent có id:

```text
builtin_function_1_existing
```

Tên hiển thị:

```text
9 Táo sấy - 9 Vải vàng
```

Wrapper chứa một block gọi `function_1` proven hiện có. Mục đích là để `📂 Load Function` thấy ngay Function đã làm trước đó mà **không** decompile/đoán lại hàng loạt click/swipe từ implementation đã proven.

Khi store khởi tạo, nếu file wrapper chưa tồn tại thì nó tự tạo trong:

```text
%APPDATA%\KVTM Multi DEV\auto-builder\functions\builtin_function_1_existing.json
```

`list_functions()` sắp wrapper này lên đầu danh sách Load Function.

## Function library / multi-tab vẫn giữ nguyên

- `QUY TRÌNH CHÍNH` là tab cố định.
- `＋ Function mới` tạo Function custom mới.
- `📂 Load Function` mở Function đã lưu, bao gồm `9 Táo sấy - 9 Vải vàng`.
- Có thể mở nhiều document Function cùng lúc để chỉnh.
- Runtime trên cùng profile vẫn single-worker/single-capture-owner; không chạy hai Function song song trên cùng ClientJS.
- Saved Function nested vẫn được phép nếu graph không có recursion.

## Static contract v1.2

`tools/verify_auto_builder_contract.py` khóa thêm:

- prior Function 1 phải seed/load được với đúng tên `9 Táo sấy - 9 Vải vàng`;
- persistent `image-library`;
- nguồn nhận diện 1 = Multi DEV, 2 = AUTO PRO;
- AUTO PRO selection bắt buộc copy vào Multi DEV library;
- Swipe lưu ordered `points`;
- live picker giữ nhiều điểm + Undo/Clear;
- runtime phải dùng một `driver.swipe_points(...)` call;
- picker vẫn cấm HWND fallback;
- các contract v1.1 về multi-tab, Function graph, isolated worker, strict Bridge V3 vẫn giữ.

Build mong đợi có:

```text
AUTO MULTI DEV AUTO BUILDER STATIC CONTRACT VERIFIED
ui=multi-dev-native-style-multi-tab-function-editor
functions=create-save-load-call-nested-no-recursion+builtin-function1-loadable
gesture_picker=multi-segment-opengl-drag-to-logical-1000-no-hwnd-fallback
swipe_runtime=one-native-swipe-points-batch
recognition_library=multi-dev-first-auto-pro-copy-in
```

## Trạng thái

`SOURCE IMPLEMENTED / STATIC CONTRACT UPDATED / WINDOWS LIVE PENDING`

Không gọi live PASS trước khi operator test trên Windows.

## NEXT live test

1. Root `KVTM_DEV_CONTROL.bat` → `[1] Cap nhat source + build runtime DEV`.
2. Build phải qua `AUTO MULTI DEV AUTO BUILDER STATIC CONTRACT VERIFIED` và các dòng v1.2 ở trên.
3. `[2]` mở Multi DEV.
4. `TỰ TẠO AUTO` → `📂 Load Function` → xác nhận dòng đầu có `9 Táo sấy - 9 Vải vàng`.
5. Tạo/sửa Swipe → chọn kéo trực tiếp trên game → tạo ít nhất 3 điểm / 2 đoạn → thử `Undo đoạn cuối`, kéo thêm đoạn, rồi `Dùng Swipe này`; row phải hiện `N điểm / N-1 đoạn`.
6. Tạo block Nhận diện → chọn `1 • Thư viện Multi DEV`.
   - nếu thư viện chưa có ảnh, Builder phải chuyển sang AUTO PRO;
   - chọn một ảnh từ `2 • Ảnh AUTO PRO`;
   - xác nhận thông báo copy;
   - mở lại block Nhận diện và chọn nguồn 1, ảnh vừa copy phải xuất hiện.
7. Runtime test Swipe chỉ nên dùng thao tác không phá nghiệp vụ trước; kiểm log có `Swipe nhiều điểm • points=... • segments=...`.
8. Chỉ sau plumbing này PASS mới dùng path nhiều đoạn cho Function sản xuất thật.

## DO NOT TOUCH

- Dọn quầy ổn định;
- `components/workspace/**`;
- profile/login/DPAPI;
- Bridge V3 `WRITERMAP2 + WRITERMSG1`;
- không thay multi-point Swipe bằng nhiều swipe rời;
- không dùng trực tiếp ảnh AUTO PRO sau khi operator đã import; step phải dùng bản copy ở Multi DEV library;
- không bịa lại Function 1 thành gesture JSON;
- route tầng chưa live-prove vẫn fail-close.
