# AUTO MULTI DEV — Chuẩn hóa vị trí khởi điểm

Tài liệu này là handoff bắt buộc cho chuỗi sửa camera/transition của AUTO MULTI DEV. Luôn ưu tiên **quy tắc mới nhất** bên dưới nếu mâu thuẫn với ghi chú cũ.

## QUY TẮC MỚI NHẤT — 2026-09-08

Người dùng xác nhận lỗi `STEP 2 đã gửi 1+3 goDown(1) nhưng chưa xác nhận được màn hình chính` là do **đặt exact-main gate sai chỗ**.

Quy tắc hiện hành:

- Startup được phép **phân loại/chuẩn hóa camera**, nhưng không được dừng AUTO chỉ vì exact `is_own_main_screen()` không PASS sau chuỗi startup.
- Exact-main fail-close chỉ đặt ở **transition nghiệp vụ giữa một lượt trồng cây và một lượt sản xuất VP, hoặc giữa sản xuất VP và lượt trồng kế tiếp**.
- `frame_change` vẫn chỉ là diagnostic, không phải detector tầng/main.
- Không hạ threshold, không click mù, không chấp nhận stale CAPTURE3.

Hai exact-main gate hiện được đặt đúng tại Function 1:

1. Sau khi hoàn tất lượt trồng Táo tầng 6 và route `floor_6_to_main()`, trước khi đi lên tầng 2 để SX Nước táo.
2. Sau khi SX đủ 9 Nước táo và route `floor_2_to_main()`, trước khi bắt đầu trồng 27 Bông.

Các transition còn lại được hậu kiểm bằng gate nghiệp vụ của action đích (cây/máy/panel/vật phẩm), không ép exact-main ở startup.

## STEP 1 — Bắt đầu tại màn hình chính

Trạng thái: **Đã xong, giữ làm routing hint chứ không làm fatal gate.**

- `GameSessionWorkflow` vẫn probe `is_own_main_screen()` một lần để tránh kéo xuống nếu clone vốn đã ở main.
- Nếu probe PASS: giữ nguyên camera, không `goDown`.
- Probe này không tự quyết định toàn workflow PASS/FAIL.
- `goUp(1)` trước lượt gieo vẫn do planting action sở hữu; session không phát thêm.

Commit lịch sử STEP 1:

`f33406931990ea50144a871c2a1878fcc67bc110` — `fix(auto-multi): lock main-screen startup anchor`

## STEP 2 — Bắt đầu tầng 1 hoặc tầng 2

Trạng thái: **Đã sửa theo quy tắc mới.**

Chuỗi startup tầng thấp vẫn giữ:

1. Nếu startup không thấy main, cho portal/popup route hiện có một cửa sổ ngắn để vào game/đóng blocker.
2. Nếu vẫn chưa về main trong cửa sổ đó, phát `goDown(1)` bằng geometry `(514,314) -> (514,214)`.
3. Lấy fresh CAPTURE3 sau gesture và ghi `frame_change` diagnostic.
4. Phát thêm đúng **3 x `goDown(1)`**.
5. Sau `1 + 3`, **không còn raise ScreenTimeout chỉ vì exact-main classifier FAIL**.
6. Bàn giao sang lượt nghiệp vụ đầu tiên; gate exact state được kiểm ở transition nghiệp vụ sau đó.

Runtime mới:

`37ff439806735d73724f10b1ca328a4fcdfb9a97` — `fix(auto-multi): defer main gate to stage transitions`

AppleDryer không còn gọi `ensure_main_screen()` lần hai ở đầu pass:

`a51d50fcfb9e9f18ad85663efa5739d20f2beefb` — `fix(auto-multi): remove duplicate startup main gate`

Exact-main gate chuyển sang Function 1 transitions:

`cf600a243ec7673f65e9e5dbb41d36b655b0c2b4` — `fix(auto-multi): gate main only between business stages`

Worker log cũng đã đổi để không báo sai `xác nhận màn hình chính` ngay sau session:

`7c1e12ac0fbaf64a50f876f58ccb9b2221f5e5a4` — `fix(auto-multi): align session pass log with deferred gate`

Static contract khóa quy tắc mới:

`48a3d9f467a6afca693803830cfd0768a944a4ff` — `test(auto-multi): lock transition-only main gates`

## STEP 3 — Startup tầng 3 đến tầng 10

Trạng thái: **Chưa làm detector/click nút xuống tầng.**

Yêu cầu đã xác nhận:

1. Sau một `goDown(1)` ở tầng cao, nút xuống tầng xuất hiện trong thời gian ngắn.
2. Chỉ click khi nhận diện đúng template nút trên fresh frame.
3. Chờ animation chuyển tầng xong.
4. Thực hiện thêm 3 x `goDown(1)` để thoát trạng thái camera/mây trung gian.
5. Theo quy tắc mới, startup không fatal-gate exact main; chỉ ghi diagnostic và bàn giao nghiệp vụ.
6. Exact-main fail-close chỉ dùng khi route này xuất hiện **giữa hai stage nghiệp vụ**.

Không được dùng `quay_hang`, `cua_hang` hoặc tọa độ đoán làm nút xuống tầng. Phải có asset/reference/live evidence đúng trước khi triển khai.

## STEP 4 — Timing nút xuống tầng

Trạng thái: **Chưa làm.**

- Nút chỉ xuất hiện sau thao tác kéo tầng.
- Chỉ tồn tại vài giây rồi biến mất.
- Detection bắt đầu ngay sau fresh frame hậu `goDown(1)`.
- Search window phải bounded, không loop vô hạn.
- Không hạ threshold để ép nhận diện.

## FIX Bông 27/27 false-negative

Trạng thái: **Đã sửa source.**

- Gesture/path 27 chậu là business action.
- `changed_waypoint_regions` chỉ là diagnostic.
- `0/27` hoặc thiếu hàng thứ 5 trong viewport không còn làm fail.
- Asset/seed/transport/stop thật vẫn fail-close.

Runtime:

`32cfd192325172b2b3fb63a777adb37c2e4211c0` — `fix(auto-multi): make cotton visibility check advisory`

Static contract:

`d93551c5ac4374befe8d79628f928661ce5341d7` — `test(auto-multi): align cotton postcheck contract`

## FIX CAPTURE3 moving expected frame

Trạng thái: **Source đã sửa; live checkpoint mới đã đi qua lỗi cũ.**

Adapter same-request:

- Một screenshot phát đúng một `CAPTURE`.
- Giữ `expected_frame` cố định và poll cùng mapping.
- Không nhận stale frame.
- Không HWND fallback.

Commits:

`d2db0b4f63678307869456554ecf9bbaeecdd134` — `fix(auto-multi): wait on one capture response`

`cc13e2a89921b006d9f58e1efdcb0ddbac041be8` — `fix(auto-multi): install same-request capture wait`

Live 12:01 đã có log `CAPTURE3 same-request wait ENABLED`, exact PING hiện hành và không tái hiện capture exception trước khi workflow dừng ở startup exact-main gate cũ. Chưa gọi transport FULL PASS cho tới khi chạy dài hơn qua pipeline.

## Invariant an toàn

- Không nới CAPTURE3.
- Không chấp nhận stale frame.
- Không HWND fallback trong AUTO MULTI DEV.
- Mỗi gesture navigation vẫn lấy fresh frame diagnostic.
- Không dùng `frame_change` để gắn nhãn tầng/main.
- Exact-main fail-close chỉ nằm ở transition nghiệp vụ đã định nghĩa, không ở startup.
- Không đụng Dọn quầy/sale/profile cho task này.
- AUTO PRO chỉ là reference.

## Điểm tiếp tục cửa sổ kế tiếp

Không khôi phục lại startup exact-main ScreenTimeout.

Live retest trước:

1. Control Center `[1]`.
2. `[2]` mở Multi DEV.
3. Chạy một tài khoản liên tục.

Kỳ vọng log startup nếu đi nhánh tầng thấp:

- `AUTO khởi điểm STEP 2 • 1+3 goDown(1) hoàn tất • không gate main tại startup...`
- Sau đó phải đi tiếp vào `AUTO Táo sấy` thay vì popup lỗi STEP 2.

Hai checkpoint exact-main đúng chỗ cần theo dõi:

- `AUTO transition check • sau trồng Táo tầng 6 → trước SX Nước táo • exact main PASS`
- `AUTO transition check • sau SX Nước táo → trước trồng Bông • exact main PASS`

Nếu một gate này fail, sửa **route chuyển tầng tương ứng**, không đưa check quay lại GameSession startup.

Sau khi route hiện tại chạy ổn, tiếp tục STEP 3/4: thu hồi đúng asset/timing của nút xuống tầng cho startup tầng 3-10.
