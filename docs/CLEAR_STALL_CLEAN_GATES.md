# Dọn quầy ClientJS — đặc tả nghiệp vụ và gate kiểm chứng

## Phạm vi

Module clean Python độc lập, không gọi `FarmAutomation`, `ADBController`,
`automation.pyc` hoặc Function 170 cho nghiệp vụ Dọn quầy.

## Quy trình đã được người dùng xác nhận

1. Hết thời gian đếm ngược, mở đúng clone DEV và chờ vào game.
2. Đóng popup, vào nhà bạn theo thứ tự cấu hình.
3. Mở quầy nhà bạn và kéo bốn view đã xác nhận. Không suy luận số ô mở/khóa; sức chứa thay đổi theo tài khoản.
4. Mỗi ô mua tương ứng đúng 10 VP. Cấu hình mua phải là bội số 10;
   ví dụ 200 VP tương ứng 20 ô.
5. Kéo quầy theo thao tác bán VP đã kiểm chứng của AUTO PRO. Nếu chưa đủ target thì thoát/vào lại quầy, sau đó chuyển lần lượt qua nhà 1..N.
6. Chỉ tăng số đã mua sau khi game xác nhận giao dịch.
7. Quay về nhà clone, mở quầy và thu vàng ở các ô đã hết thời gian.
8. Treo lại đúng loại VP đã mua, mỗi lượt đúng 10. Không thay đổi giá.
9. Nếu một loại không đủ 10, bỏ qua loại đó và thử loại tiếp theo.
10. Khi không còn loại nào đủ 10, đóng ClientJS và bắt đầu chu kỳ đếm ngược mới.
11. Không carry-over phần lẻ sang vòng sau và không bán lẻ dưới 10.\n12. Toàn máy chỉ chạy một job Dọn quầy; tài khoản đến giờ sau xếp hàng đến khi job trước thoát.

## State machine mục tiêu

- `WAITING_TIMER`
- `OPENING_CLONE`
- `WAITING_MAIN_SCREEN`
- `NAVIGATING_FRIEND`
- `OPENING_SOURCE_STALL`
- `SCANNING_STALL_VIEWS`
- `PURCHASING_TEN_ITEM_LISTINGS`
- `RETURNING_HOME`
- `COLLECTING_STALL_GOLD`
- `OPENING_OWN_STALL`
- `RESELLING_TEN_ITEM_BATCHES`
- `NO_MORE_FULL_BATCHES`
- `CLOSING_CLIENT`
- `WAITING_TIMER`

Mỗi click mua/treo phải được xác minh trước khi manifest tăng số lượng.

## Gate triển khai

### Gate 1 — READ_ONLY_SCAN

Đã mở trong source. Worker bị khóa `probe_only=True`.

Cho phép:

- mở/nhận đúng clone DEV;
- đóng popup;
- vào đúng nhà bạn;
- mở quầy;
- kéo bốn view;
- chụp ảnh và ánh xạ 20 ô;
- lập kế hoạch `số ô x 10`.

Cấm:

- click mua;
- click bán;
- thu vàng;
- đóng ClientJS khi probe hoàn tất.

PASS live chỉ khi log thật xác nhận đúng profile, đúng nhà bạn, đủ bốn view,
không mua VP và báo kế hoạch/target chính xác.

### Gate 2 — PURCHASE_ONE_LISTING

Chỉ mở sau Gate 1 live PASS. Cho phép mua đúng một ô x10, xác minh ô/giao dịch
thay đổi và dừng ngay.

### Gate 3 — PURCHASE_TARGET

Chỉ mở sau Gate 2 live PASS. Mua nhiều ô đến target, quét lại sau mỗi giao dịch
để không dùng tọa độ stale và không mua trùng sau kéo.

### Gate 4 — COLLECT_GOLD_AND_RESELL_ONE

Chỉ mở sau Gate 3 live PASS. Thu vàng, treo đúng một loại x10, không đổi giá,
xác minh quầy thay đổi rồi dừng.

### Gate 5 — FULL_CYCLE

Mua target, về nhà, thu vàng, duyệt các nhóm đủ 10, bỏ qua nhóm thiếu 10,
đóng ClientJS và đặt lịch vòng mới.

## Bảo mật và cô lập

- Chỉ tác động profile/PID DEV đã chọn.
- Không ghi hoặc upload profile, secret, token, cookie hay launch arguments.
- Diagnostic chỉ chứa stage, số ô, số lượng, fingerprint hash và ảnh game được
  whitelist.
- Không sửa Workspace.
