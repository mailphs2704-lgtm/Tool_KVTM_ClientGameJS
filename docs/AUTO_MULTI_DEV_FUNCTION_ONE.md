# AUTO MULTI DEV — Chức năng 1

Cập nhật: 2026-09-09

## Trạng thái

**Function 1 đã được operator chạy nhiều vòng và chốt PASS thực tế.**

Từ mốc này, Function 1 được xem là baseline ổn định. Nếu phát sinh lỗi mới thì xử lý như regression cụ thể; không thay đổi hàng loạt các bước đang PASS nếu không có bằng chứng runtime.

## Điều kiện hoàn thành

Một vòng Function 1 chỉ PASS khi chuỗi đã hoàn tất đầy đủ và trả hợp đồng `progress_steps=3`, `total_steps=3`, có đủ **9 Táo sấy**, **9 Vải vàng** và **27 Bông đã trồng** theo gate scheduler hiện tại.

Nước táo là thành phẩm trung gian bắt buộc để sản xuất Vải vàng, không phải điểm kết thúc Function.

## Chuỗi runtime hiện tại

1. Worker chuẩn hóa về exact-main trước scheduler.
2. AUTO bán VP đúng catalog của Function 1.
3. Từ main lên tầng 1 và trồng 27 Táo.
4. Sản xuất đủ 9 Táo sấy tại tầng 1.
5. Chờ/thu hoạch/gieo lại Táo theo gate cây chín.
6. Từ tầng 1 lên tầng 6 bằng route đã prove của Function.
7. Xử lý hàng Táo ở tầng 6.
8. Recovery tầng 6 → main.
9. Main → tầng 2.
10. Sản xuất đủ 9 Nước táo.
11. Recovery tầng 2 → main.
12. Trồng 27 Bông.
13. Điều hướng tới tầng 3.
14. Sản xuất đủ 9 Vải vàng.
15. Recovery tầng 3/upper-floor → exact-main bằng navigation proof.
16. PASS 3/3 và trả kết quả cho scheduler.
17. Scheduler bán lại theo số vòng đã cấu hình rồi tiếp tục vòng Function kế tiếp.

## Hợp đồng production đã PASS

### Thu VP bằng burst x5

Táo sấy, Nước táo và Vải vàng dùng chung nguyên tắc:

- mỗi burst gửi đúng 5 click tức thì tại cùng tọa độ máy;
- nghỉ theo `vp_collect_delay` sau burst;
- tiếp tục burst cho tới khi panel được xác minh mở;
- panel chỉ được coi là mở khi **ảnh sản phẩm đúng** xuất hiện trong `PRODUCT_SEARCH_ZONE`;
- `o_trong` chỉ được dùng làm diagnostic, không được phép kết thúc vòng collect;
- product-image miss tạm thời khi panel đang chờ là non-blocking và tiếp tục recheck.

### Kéo sản xuất

- Mỗi gesture phải làm giảm số ô trống theo hậu kiểm.
- Với render chậm, runtime recheck nhiều frame và retry gesture có giới hạn trước khi báo lỗi.
- Không retry mù vô hạn destructive gesture.

### Kho đầy

`InventoryFull` là business signal riêng:

1. quay về exact-main;
2. chạy sale VP thuộc Function hiện tại;
3. quay lại đúng tầng sản xuất;
4. retry đúng production call đang dở.

Không nuốt generic `ScreenTimeout` vào warehouse recovery.

## Exact-main và điều hướng đa background

Không dùng background/quầy của account làm exact-main gate.

Hợp đồng:

- own farm nhận bằng HUD cố định;
- exact-main nhận bằng bằng chứng navigation runtime;
- unknown camera dùng goDown có giới hạn;
- fallback main boundary: 2 lần liên tiếp `frame_change <= 6.0`;
- nếu sau `goDown(1)` xuất hiện nút `XUỐNG` ở mép dưới thì nhận diện nút và click đúng `match.center`;
- không click mù tọa độ `(497,978)`;
- tầng 1 không có nút XUỐNG là trạng thái bình thường;
- upper-floor recovery chain tối đa 10 bước.

Điều này bắt buộc vì mỗi account có farm/background khác nhau.

## AUTO bán VP của Function 1

Function 1 mặc định bán:

- `tao_say`;
- `vai_vang`.

Mỗi listing phải qua exact-x10 gate và hậu kiểm screen-change trước khi được ghi nhận SOLD.

### Quảng cáo quầy

Mỗi lượt sale có 3 checkpoint QC gần physical slot `1 / 10 / 20`:

- nếu ô đã có dấu QC đỏ → bỏ qua, không click;
- nếu chưa QC → click listing và kiểm tra popup;
- nếu nút xanh `Đặt quảng cáo` đã hồi → click đúng nút miễn phí;
- nếu còn cooldown → đóng X và tiếp tục;
- không click nút kim cương/quảng cáo trả phí;
- lỗi QC là non-blocking;
- quầy full hoặc kho hết VP vẫn tiếp tục đi hết ba checkpoint QC và thu vàng.

## Cấu hình tốc độ baseline

Multi DEV persistent baseline hiện khóa:

- kéo tầng: `0.350s`;
- trồng/thu: `0.035s`;
- sản xuất VP: `0.070s`;
- kiểm tra cây: `0.100s`.

Settings operator đã lưu trong `%APPDATA%\KVTM Multi DEV` vẫn là authoritative và không bị rebuild `dist` xóa.

## Biên thực thi

- Mỗi profile chạy một isolated worker riêng.
- Runtime ảnh + input dùng Bridge V3.
- Không HWND fallback trong AUTO runtime.
- Không chạy automation business logic trong GUI thread Multi.
- Runtime error policy: recover exact-main rồi restart pipeline; không popup blocking.

## Build gates liên quan

Các verifier chính bảo vệ Function 1:

- `tools/verify_auto_main_sale_contract.py`
- `tools/verify_auto_main_planting_contract.py`
- `tools/verify_auto_main_production_contract.py`
- `tools/verify_auto_floor_navigation_contract.py`
- `tools/verify_multi_dev_main_boundary_contract.py`
- `tools/verify_auto_vp_advertising_contract.py`

## Quy tắc regression

Không được đưa trở lại các hành vi sau:

- `o_trong` tự chứng minh panel production đã mở;
- click mù nút xuống tầng;
- background farm làm exact-main gate;
- popup error blocking toàn Multi;
- retry destructive transaction 3–10 lần tại cùng trạng thái mà không recover;
- sale bỏ qua exact-x10/post-verify;
- quảng cáo click ô đã có QC;
- quảng cáo click nút trả phí;
- quầy full làm sale workflow kết thúc trước khi hoàn tất ba checkpoint QC.
