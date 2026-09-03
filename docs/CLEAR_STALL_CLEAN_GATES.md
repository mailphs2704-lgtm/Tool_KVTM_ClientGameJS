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

Source đã hoàn thiện, chờ LIVE PASS. Lần live `20260903-125257` FAIL an toàn trước accounting vì scanner nhận ô “Đã bán” là listing; ảnh xác nhận hàng trên đã bán và hàng dưới còn x10. Patch mới chỉ tạo observation khi vùng giá có coin marker (vùng giá đúng: hàng trên y=495..530, hàng dưới y=685..720; ảnh live mới cho empty/sold=0 và available=130..199 pixel; cutoff 120), nên không click ô sold. Gate dùng target còn thiếu theo đơn vị x10, không suy luận sức chứa quầy. Luồng thực hiện:

1. Mở quầy nhà 1, quét và mua ngay các ô đang nhìn thấy; mỗi giao dịch chỉ cộng sau khi listing đổi.
2. Sau khi xử lý xong view hiện tại mới vuốt đúng hai nhịp, rồi quét lại cả 8 ô của hai hàng và mua các ô có thể mua; lặp tới cuối quầy.
3. Nếu chưa đủ, đóng quầy rồi mở lại ngay tại cùng nhà, không về nhà giữa các lượt; tối đa `max_scan_pages` nhưng bị chặn cứng không quá 10 lượt mỗi nhà.
4. Một lượt không mua thêm được ô nào thì chuyển ngay sang nhà tiếp theo.
5. Duyệt tuần tự nhà `1..N`, với N là “Số nhà cần duyệt”.
6. Dừng ngay khi remaining bằng 0. Nếu hết nhà/lượt mà vẫn thiếu, FAIL rõ expected/actual/remaining và quay về nhà.
7. Mỗi ô mua lưu PNG cùng `friend_ordinal`, `stall_pass`, view, physical slot và bộ đếm remaining.
8. VP hiện còn hàng nhưng click không đổi (ví dụ clone chưa đủ level) bị bỏ qua, không cộng 10 VP và tiếp tục ô kế tiếp.
9. Gate 3B vẫn cấm thu vàng, treo bán và đổi giá.

**LIVE PASS Gate 3B:** run `20260903-132654`, target `130 VP`, mua xác minh đủ `130/130`, remaining `0`, transaction `PURCHASE_TARGET_MULTI_HOUSE`, purchase order `SCAN_BUY_THEN_SWIPE`. Nhà 1 mua 60 VP qua các lượt 1 và 3; sau đủ bốn lượt mới chuyển nhà 2. Nhà 2 mua 70 VP và dừng ngay khi đủ target. Report `ok=true`, exit code 0; chưa thu vàng/treo bán.

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


## GATE 4 — Thu vàng và treo đúng vật phẩm vừa mua (SOURCE READY)

Phạm vi kiểm thử có chủ đích:

1. Chạy nguyên quy trình GATE 3B cho đến khi mua đủ target.
2. Mỗi giao dịch chỉ được cộng sau khi ô quầy biến mất; icon của chính giao dịch đó được đóng băng thành fingerprint riêng trong thư mục run.
3. Đóng quầy nhà bạn, về nhà, mở quầy nhà và thu vàng trước.
4. Bấm một ô quầy trống rồi mới quét kho đã cấu hình.
5. Chỉ chấp nhận một fingerprint thuộc danh sách giao dịch mua đã xác minh trong cùng lượt.
6. Treo đúng một lô x10, không chạm điều khiển giá.
7. Chỉ ghi sold_quantity=10 sau khi màn hình xác nhận thay đổi; không tìm thấy đúng VP thì dừng trước khi treo.

Giới hạn an toàn:

- Không dùng carryover hoặc fingerprint của lượt cũ.
- Không thay một vật phẩm gần giống khi đối chiếu thất bại.
- Không tự động chạy theo lịch trong DEV; phải bấm GATE 4 và xác nhận.
- Trạng thái hiện tại là SOURCE READY, chưa được gọi LIVE PASS cho đến khi có report chạy thật.


## GATE 4 — Hiệu chỉnh fingerprint liên màn hình (2026-09-03)

Live run `20260903-184154` xác nhận mua đủ 130/130 VP và mở đúng kho 2,
nhưng fingerprint 84x84 cũ chứa nền quầy và nhãn `x10`, trong khi cùng VP ở kho
có nền khác và nhãn `x150`. Vì vậy khớp nguyên ô bị loại dù vật phẩm tồn tại.

Bản sửa chuẩn hóa mỗi giao dịch đã xác minh thành lõi biểu tượng phía trên-trái,
loại nền quầy/giá/số lượng trước khi lập fingerprint. Luồng bán mở ô trống trước,
quét kho sau, ghi score của từng ứng viên, chỉ nhận score >= 0.62 và vẫn chỉ xét
fingerprint được tạo trong chính lượt mua. Giá bán không bị tác động.

Đây là SOURCE/STATIC READY; chỉ nâng thành LIVE PASS sau một run GATE 4 mới.


## GATE 4 — LIVE PASS (2026-09-03 18:52:55)

Evidence run: `20260903-185255`.

- requested/purchased: `20/20 VP`
- normalized inventory fingerprint score: `0.763` (threshold `0.62`)
- gold collection actions before resale: `20`
- resale: exactly one `x10` batch
- fingerprint source: `VERIFIED_PURCHASE_THIS_RUN`
- price changed: `false`
- final state: `ok=true`, `last_stage=completed`, `returncode=0`
- visual evidence: `gate4-resale-one-pass.png` shows the x10 item on the own stall

Conclusion: cross-screen fingerprint normalization (friend stall -> inventory) and the
bounded one-batch resale transaction are LIVE VERIFIED. This gate does not yet authorize
unbounded/full-cycle resale; later expansion must retain per-purchase provenance,
x10 accounting, unchanged price, and stop-before-wrong-item behavior.


## GATE 5 — SOURCE READY (2026-09-03)

Purpose: expand the LIVE-verified Gate 4 transaction from one x10 batch to every
verified purchase token in the current run.

Safety/accounting contract:

- maximum one cycle is 20 batches / 200 VP;
- purchase target must be reached before returning home;
- collect own-stall gold before opening resale inventory;
- one verified purchase fingerprint is consumed for each successful x10 sale;
- each batch saves a separate post-sale screenshot and cumulative sold quantity;
- final success requires `sold_quantity == resale_batch_limit * 10`;
- price controls remain untouched;
- missing exact VP, insufficient x10 quantity, or no empty stall slot stops the run
  before substituting another item;
- Gate 5 remains DEV/manual-consent only until live evidence passes.

Status: AST/static source ready; LIVE NOT YET VERIFIED.


## GATE 5 — OWN-STALL FOUR-VIEW EXPANSION

The full action now uses the same proven overlapping stall geometry on the clone's
own stall:

1. collect visible gold;
2. drag exactly two pulses to the next view;
3. repeat through views 1..4;
4. rewind to view 1;
5. place x10 batches into visible empty slots;
6. when the current view has no empty slot, drag exactly two pulses and continue;
7. stop after the verified target is sold or after view 4 has no empty slot.

The transaction never scrolls in response to a missing item or insufficient x10
quantity; those conditions remain hard stops. Scrolling is allowed only after
`NoEmptyStallSlot`, preventing a recognition failure from being mistaken for a
full view.

GUI contract: passed Gate 1–4 buttons are removed. The clear-stall panel exposes
one full-action button and one Stop button. Legacy handlers remain internal only
for compatibility and are not user-visible.

Status: AST and static source checks PASS; multi-view resale still requires live evidence.
