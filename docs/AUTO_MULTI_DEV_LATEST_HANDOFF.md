# AUTO MULTI DEV — LATEST HANDOFF

Cập nhật: 2026-09-08

Đây là handoff ngắn cho phiên AI kế tiếp. Tài liệu chi tiết mới nhất:

`docs/AUTO_MULTI_DEV_AUTO_BUILDER_V11_HANDOFF.md`

## Trạng thái hiện tại

- Branch: `develop/multi-auto-dev`.
- Baseline trước Builder v1.1: `d6cc834341f8750a17f052f2f2334510a93c2fea`.
- Implementation v1.1 trước commit tài liệu: `34e2a5bc27477a3ad502ec6231a1f67e1b283111`.
- Feature: `TỰ TẠO AUTO v1.1`.
- Status: `SOURCE IMPLEMENTED / STATIC GATE UPDATED / WINDOWS LIVE PENDING`.
- Không gọi runtime PASS trước khi operator build + live test trên Windows.

## Những gì v1.1 vừa thêm

### 1. Function tự tạo thật sự

Không còn chỉ có block hard-code `Function 1`.

Builder có thư viện Function persistent tại:

`%APPDATA%\KVTM Multi DEV\auto-builder\functions`

Mỗi Function tự tạo có id, tên và danh sách block riêng. Plan chính có block mới:

`FUNCTION TỰ TẠO • Gọi Function đã lưu`

Block này có số vòng và có thể cấu hình gọi module bán VP Function 1 sau mỗi vòng.

Runtime hỗ trợ Function tự tạo lồng nhau và fail-close nếu graph bị gọi đệ quy vòng.

### 2. Editor nhiều tab

Cửa sổ Builder dùng `ttk.Notebook`:

- tab `QUY TRÌNH CHÍNH`;
- `＋ Function mới`;
- `📂 Load Function`;
- nhiều Function có thể mở cùng lúc để chỉnh song song;
- mỗi tab Save riêng;
- Function tab có `＋ Chèn vào plan chính`;
- mỗi tab có `▶ Chạy tab` để test riêng.

Lưu ý: nhiều tab là nhiều document đang mở cùng lúc. Runtime trên **cùng một profile** vẫn single-worker/single-capture-owner; không chạy hai Function đồng thời trên cùng ClientJS.

### 3. Swipe kéo trực tiếp trên game

Khi thêm/sửa block Swipe, operator có thể chọn:

`Kéo trực tiếp trên màn hình game`

Picker mới:

- yêu cầu chọn đúng 1 ClientJS đang Online;
- không cho dùng khi AUTO MULTI DEV đang chạy trên profile đó;
- yêu cầu đóng Live View của profile;
- chỉ đọc OpenGL shared capture;
- không HWND/PrintWindow fallback;
- mouse down/drag/up để lấy start/end;
- tự map về hệ ClientJS `0..1000`;
- vẽ overlay đường swipe;
- chỉ lưu sau khi bấm `Dùng Swipe này`;
- duration vẫn cấu hình riêng.

GDI picker đã được khai báo pointer-safe cho Python x64.

## Commit chain v1.1

- `0e274c961fee13b51e730febdb85004b85425fe5` — reusable Function library.
- `f230bf199047c56ed10fbb5cdc0428d598cd78cb` — live Swipe picker.
- `0618ecc582a203c22c0ff8df5135255e9c61dad9` — dialogs cho saved Function + visual Swipe.
- `94d257d8f2cc194442577e53e16f92f7cfacac47` — multi-tab Function editor.
- `bcef315db1f3456af948106c516c93da9db8c73b` — runtime saved Function execution.
- `51a4bf6f3da5eb3c0f376afd06d48490312fb8a1` — static contract.
- `34e2a5bc27477a3ad502ec6231a1f67e1b283111` — pointer-safe GDI.

## Transport bắt buộc giữ nguyên

- isolated `auto_multi_dev_worker.py`;
- strict Bridge V3 cho runtime AUTO;
- `CAPTURE3_WRITERMAP2`;
- `CAPTURE3_WRITERMSG1`;
- exact same-request capture;
- không stale frame;
- không HWND fallback;
- một owner/profile;
- preview nhường capture trước worker.

## Không được đụng

- Dọn quầy ổn định;
- `components/workspace/**`;
- `KVTM_WORKSPACE_CONTROL.bat`;
- profile/login/DPAPI;
- không hạ threshold hoặc thêm click mù;
- không tự phát minh route tầng chưa live-prove.

## NEXT duy nhất

Operator chạy:

`KVTM_DEV_CONTROL.bat` → `[1] Cap nhat source + build runtime DEV`

Không dùng `[9]` và không sửa `dist` thủ công.

Build phải có:

`AUTO MULTI DEV AUTO BUILDER STATIC CONTRACT VERIFIED`

và các dòng:

- `ui=multi-dev-native-style-multi-tab-function-editor`
- `functions=create-save-load-call-nested-no-recursion`
- `gesture_picker=opengl-shared-drag-to-logical-1000-no-hwnd-fallback`

Sau `[1]` PASS mới `[2]`.

## Thứ tự live test tiếp theo

1. Multi DEV mở bình thường.
2. `TỰ TẠO AUTO` → editor mở.
3. Có `＋ Function mới` và `📂 Load Function`.
4. Tạo 2 Function, giữ cùng lúc 2 tab, save và load lại một Function.
5. Chọn đúng 1 ClientJS Online, không chạy AUTO/Live View; thêm Swipe và kéo trực tiếp trên ảnh game.
6. Kiểm row Swipe nhận đúng start/end đã kéo.
7. Chèn Function tự tạo vào `QUY TRÌNH CHÍNH`.
8. Runtime plumbing đầu tiên nên dùng Function test rất nhỏ: `Wait → Kết thúc PASS` và plan `Vào game + đóng popup → gọi Function test`.
9. Chỉ khi plumbing PASS mới dùng Function tự tạo cho chuỗi sản xuất thật.

## Blocker nghiệp vụ vẫn còn

Built-in Function 1 kết thúc sau SX Vải vàng ở khu vực tầng 3. Route `tầng 3 → main` trước sale-after-loop chưa live-prove đầy đủ. Không được coi việc có Function Builder mới là đã giải quyết blocker điều hướng này.

## Read-first cho phiên AI kế tiếp

1. `AGENTS.md`
2. `AI_COORDINATION.md`
3. `docs/AUTO_MULTI_DEV_LATEST_HANDOFF.md`
4. `docs/AUTO_MULTI_DEV_AUTO_BUILDER_V11_HANDOFF.md`
5. `docs/AUTO_MULTI_DEV_AUTO_BUILDER_HANDOFF.md` chỉ để xem lịch sử v1.
