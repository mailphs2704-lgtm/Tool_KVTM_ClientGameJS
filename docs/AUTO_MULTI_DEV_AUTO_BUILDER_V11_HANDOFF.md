# AUTO MULTI DEV — AUTO BUILDER v1.1 HANDOFF

Cập nhật: 2026-09-08

## Mục tiêu của mốc v1.1

Phản hồi operator sau Builder v1:

1. Builder mới chỉ có block `Function 1` có sẵn, chưa cho người dùng tự tạo Function mới.
2. Swipe mới nhập tọa độ bằng số, chưa cho kéo trực tiếp trên màn hình game.
3. Editor chỉ có một document; operator muốn mở thêm tab để xây Function khác song song hoặc load lại Function đã lưu.

Mốc v1.1 triển khai đúng ba yêu cầu này và không thay đổi Dọn quầy/Workspace/profile.

## Function tự tạo — thư viện riêng

`AutoBuilderPlanStore` hiện có thư viện:

`%APPDATA%\KVTM Multi DEV\auto-builder\functions\*.json`

Mỗi Function có:

- `function_id` ổn định dạng `custom_<id>`;
- tên do operator đặt;
- danh sách block riêng;
- lưu độc lập với `current-plan.json`;
- sống qua Control Center `[1]` vì nằm ngoài `dist`.

Các API chính:

- `new_function()`;
- `save_function()`;
- `load_function()`;
- `list_functions()`;
- `bundle_plan()`.

`bundle_plan()` đóng gói Function đã lưu vào snapshot plan gửi sang isolated worker. Worker không đọc file Function trong lúc đang chạy, nên thay đổi editor sau khi bấm Run không làm biến đổi run hiện tại.

## Editor nhiều tab

Cửa sổ `TỰ TẠO AUTO` dùng `ttk.Notebook` và có:

- tab cố định `QUY TRÌNH CHÍNH`;
- `＋ Function mới`;
- `📂 Load Function`;
- có thể mở nhiều Function cùng lúc;
- mỗi tab có Treeview block riêng, tên riêng và Save riêng;
- Function tab có `＋ Chèn vào plan chính`;
- mỗi tab có thể `▶ Chạy tab` để test độc lập.

**"Mở nhiều Function cùng lúc" ở đây là nhiều document editor cùng mở để chỉnh song song.** Runtime trên cùng một profile vẫn giữ nguyên single-worker/single-capture-owner; không cho hai Function chạy đồng thời trên cùng ClientJS.

## Block gọi Function đã lưu

Block mới:

`call_saved_function`

UI:

`FUNCTION TỰ TẠO • Gọi Function đã lưu`

Cấu hình:

- chọn Function từ thư viện;
- `loops=1..999`;
- tùy chọn gọi module Bán VP Function 1 sau mỗi vòng;
- sale vẫn là module độc lập, không nhúng vào Function.

Saved Function có thể gọi Saved Function khác. Runtime dựng graph trước khi thao tác game và fail-close nếu phát hiện vòng đệ quy.

Built-in `Function 1` cũ vẫn giữ thành block riêng `FUNCTION CÓ SẴN • Function 1`; không biến code nghiệp vụ đang có thành JSON một cách tự động.

## Swipe kéo trực tiếp trên màn hình game

File mới:

`source-archive/multi-current/kvtm_multi_tool/auto_builder_gesture_picker.py`

Khi cấu hình block Swipe, operator có thể chọn `Kéo trực tiếp trên màn hình game`.

Điều kiện:

- chọn đúng 1 tài khoản;
- ClientJS phải đang Online;
- không có AUTO MULTI DEV worker đang chạy trên profile đó;
- đóng Live View của profile trước khi mở picker.

Picker:

- chỉ đọc OpenGL shared capture;
- không dùng HWND/PrintWindow fallback;
- hiển thị ảnh game trong cửa sổ riêng;
- mouse down = điểm bắt đầu;
- drag = preview đường swipe;
- mouse up = điểm kết thúc;
- tự đổi tọa độ preview về hệ logic ClientJS `0..1000`;
- operator bấm `Dùng Swipe này` mới ghi vào block;
- sau đó vẫn cấu hình duration riêng.

GDI được khai báo pointer-safe cho Python x64 để tránh HANDLE bị truncate khi vẽ live frame/overlay.

## Runtime saved Function

`AutoBuilderRunner` hỗ trợ `call_saved_function`.

- validate toàn bộ plan trước khi thao tác;
- Function graph được kiểm tra cycle;
- block trong Function chạy đúng thứ tự đã lưu;
- Function nested được phép nếu không tạo cycle;
- `Kết thúc PASS` bên trong Function kết thúc Function cục bộ và trả về caller;
- `Kết thúc FAIL` vẫn fail toàn run;
- Stop checkpoint vẫn chạy trước mỗi block;
- Function loop và sale callback được ghi log/accounting riêng.

Builder worker vẫn không prepend `GameSessionWorkflow`; nếu muốn vào game/đóng popup, operator phải đặt block đó ở vị trí mong muốn.

## Static contract

`tools/verify_auto_builder_contract.py` đã mở rộng để khóa:

- Function library save/load/list/bundle;
- multi-tab editor `ttk.Notebook`;
- nút tạo/load Function;
- block `call_saved_function`;
- nested Function + recursion guard;
- live Swipe picker mouse bindings;
- mapping logic 0..1000;
- OpenGL shared capture only, cấm HWND fallback trong picker;
- style Multi DEV giữ nguyên;
- isolated worker V3 strict vẫn giữ.

Build mong đợi có:

`AUTO MULTI DEV AUTO BUILDER STATIC CONTRACT VERIFIED`

với các dòng mới:

- `ui=multi-dev-native-style-multi-tab-function-editor`
- `functions=create-save-load-call-nested-no-recursion`
- `gesture_picker=opengl-shared-drag-to-logical-1000-no-hwnd-fallback`

## Commit chain v1.1

Baseline trước thay đổi: `d6cc834341f8750a17f052f2f2334510a93c2fea`.

Các commit implementation:

- `0e274c961fee13b51e730febdb85004b85425fe5` — reusable Function library;
- `f230bf199047c56ed10fbb5cdc0428d598cd78cb` — live swipe picker;
- `0618ecc582a203c22c0ff8df5135255e9c61dad9` — saved Function + visual Swipe dialogs;
- `94d257d8f2cc194442577e53e16f92f7cfacac47` — multi-tab Function editor;
- `bcef315db1f3456af948106c516c93da9db8c73b` — runtime saved Function execution;
- `51a4bf6f3da5eb3c0f376afd06d48490312fb8a1` — static contract;
- `34e2a5bc27477a3ad502ec6231a1f67e1b283111` — pointer-safe GDI picker.

## Trạng thái

`SOURCE IMPLEMENTED / STATIC GATE UPDATED / WINDOWS LIVE PENDING`

Không gọi runtime PASS trước Windows test.

## NEXT test — theo thứ tự

1. Root `KVTM_DEV_CONTROL.bat` → `[1] Cap nhat source + build runtime DEV`.
2. Build phải qua `AUTO MULTI DEV AUTO BUILDER STATIC CONTRACT VERIFIED`.
3. `[2]` mở Multi DEV.
4. Vào `TỰ TẠO AUTO` → mở editor.
5. Xác nhận có `＋ Function mới`, `📂 Load Function` và `QUY TRÌNH CHÍNH`.
6. Tạo hai Function mới, giữ cả hai tab mở; lưu, đóng một tab, dùng `Load Function` mở lại.
7. Chọn đúng một ClientJS Online, không chạy AUTO/Live View; thêm Swipe → chọn kéo trực tiếp trên game; kéo một đường và kiểm tọa độ được ghi vào row Swipe.
8. Chèn một Function vào plan chính; kiểm row hiện `FUNCTION TỰ TẠO` + đúng tên + số vòng.
9. Runtime test đầu tiên nên dùng Function rất nhỏ và không phá nghiệp vụ, ví dụ plan có `Vào game + đóng popup → gọi Function test` với Function test chỉ `Wait → Kết thúc PASS`.
10. Chỉ sau plumbing này PASS mới dùng Function tự tạo để thay các chuỗi sản xuất thật.

## DO NOT TOUCH

- Dọn quầy ổn định;
- `components/workspace/**`;
- profile/login/DPAPI;
- Bridge V3 worker strict `WRITERMAP2 + WRITERMSG1`;
- route tầng chưa live-prove;
- không thêm click/swipe mù để ép Function chạy.
