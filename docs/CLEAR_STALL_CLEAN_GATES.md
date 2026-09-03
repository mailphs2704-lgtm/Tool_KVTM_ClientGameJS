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
11. Không carry-over phần lẻ sang vòng sau và không bán lẻ dưới 10.
12. Toàn máy chỉ chạy một job Dọn quầy; tài khoản đến giờ sau xếp hàng đến khi job trước thoát.

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

Đã LIVE PASS trên runtime `2e9cfc3`: đúng profile/nhà, DLL capture 1000x1000, bốn view khác nhau, quay về nhà và không có sự kiện mua/bán. Worker lịch tự động vẫn khóa `probe_only=True`.

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

LIVE PASS trên runtime `7e32160`, run `20260903-122225`: đúng profile PID 13536, transaction gate `PURCHASE_ONE_LISTING`, chỉ một DOWN/UP tại ô (290,435), listing đổi trước khi cộng, `purchased_quantity=10`, quay về nhà và exit 0. Không có click mua thứ hai, không bán lại.

### Gate 3 — PURCHASE_TARGET

LIVE PASS trên runtime trước commit bố cục, run `20260903-123215`: target 40 VP, đúng bốn click vào physical slot 1..4, bốn PNG cho thấy từng ô chuyển sang “Đã bán”, accounting 10→20→30→40, `PURCHASE_TARGET`, quay về nhà và exit 0. Phạm vi PASS là target trong một quầy đã quét.

### Gate 3B — PURCHASE_TARGET_MULTI_HOUSE

Source đã hoàn thiện, chờ LIVE PASS. Lần live `20260903-125257` FAIL an toàn trước accounting vì scanner nhận ô “Đã bán” là listing; ảnh xác nhận hàng trên đã bán và hàng dưới còn x10. Patch mới chỉ tạo observation khi vùng giá có coin marker (ngưỡng live: sold ≤72 pixel, available ≥184 pixel; cutoff 120), nên không click ô sold. Gate dùng target còn thiếu theo đơn vị x10, không suy luận sức chứa quầy. Luồng thực hiện:

1. Quét và mua tại nhà 1; mỗi giao dịch chỉ cộng sau khi listing đổi.
2. Nếu chưa đủ, đóng quầy, về nhà rồi vào lại cùng quầy; tối đa `max_scan_pages` nhưng bị chặn cứng không quá 10 lượt mỗi nhà.
3. Một lượt không mua thêm được ô nào thì chuyển ngay sang nhà tiếp theo.
4. Duyệt tuần tự nhà `1..N`, với N là “Số nhà cần duyệt”.
5. Dừng ngay khi remaining bằng 0. Nếu hết nhà/lượt mà vẫn thiếu, FAIL rõ expected/actual/remaining và quay về nhà.
6. Mỗi ô mua lưu PNG cùng `friend_ordinal`, `stall_pass`, view, physical slot và bộ đếm remaining.
7. Gate 3B vẫn cấm thu vàng, treo bán và đổi giá.

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
