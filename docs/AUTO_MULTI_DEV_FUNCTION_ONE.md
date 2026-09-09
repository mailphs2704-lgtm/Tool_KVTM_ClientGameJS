# AUTO MULTI DEV — Chức năng 1

Cập nhật: 2026-09-09

## Trạng thái

**Function 1 baseline đã được operator chạy nhiều vòng và chốt PASS thực tế.**

Hai regression mới nhất đã được sửa source nhưng vẫn cần live-test lại sau build:

- Bông → Vải vàng: điểm `(257,416)` chỉ lên tầng 2; runtime mới click chậu tầng 4 `(257,191)` để tới candidate tầng 3.
- Production mở nhầm máy/tầng: nếu panel hiện VP khác target thì đóng panel ngay, phát `WrongProductionMachine`, recovery exact-main rồi quay lại đúng tầng.

QC quầy đã được operator chốt PASS. Sale/QC/Dọn quầy đang là vùng ổn định và không được thay đổi khi sửa navigation/production nếu không có bằng chứng regression.

HEAD source trước lần cập nhật tài liệu này:

`ffa9336565d00c5bf18b36ddc0c64e1246db8a2f`

Commit `ffa93365` chỉ sửa static speed verifier để khớp fresh-frame panel scan mới; không thay đổi runtime Function 1.

## Điều kiện hoàn thành

Một vòng Function 1 chỉ PASS khi chuỗi đã hoàn tất đầy đủ và trả hợp đồng `progress_steps=3`, `total_steps=3`, có đủ **9 Táo sấy**, **9 Vải vàng** và **27 Bông đã trồng** theo gate scheduler hiện tại.

Nước táo là thành phẩm trung gian bắt buộc để sản xuất Vải vàng, không phải điểm kết thúc Function.

## Chuỗi runtime hiện tại

1. Worker chuẩn hóa về exact-main trước scheduler.
2. AUTO bán VP đúng catalog của Function 1; QC quầy chạy 3 checkpoint đầu/giữa/cuối.
3. Từ main lên tầng 1 và trồng 27 Táo.
4. Sản xuất đủ 9 Táo sấy tại tầng 1.
5. Chờ/thu hoạch/gieo lại Táo theo gate cây chín.
6. Từ tầng 1 lên tầng 6 bằng route đã prove của Function.
7. Xử lý hàng Táo ở tầng 6.
8. **Đường nhanh:** `goDown(4)` thẳng từ tầng 6 tới candidate tầng 2.
9. Probe máy Nước táo có giới hạn; chỉ khi thấy đúng anchor `nuoc_tao` trong vùng thư viện panel mới chấp nhận tầng 2.
10. Nếu probe miss/lệch tầng: đóng panel, dùng recovery goDown/XUỐNG/main-boundary không phụ thuộc background để về exact-main, sau đó `goUp(1) x2` về tầng 2 và mới retry production.
11. Sản xuất đủ 9 Nước táo và Sửa máy.
12. Recovery tầng 2 → exact-main.
13. Trồng 27 Bông.
14. Từ mốc tầng 1 lên tầng 3 bằng **click chậu tầng 4 tại `(257,191)`**. Điểm cũ `(257,416)` đã live-test và chỉ đưa camera lên tầng 2 nên không được dùng cho bước Vải vàng.
15. Production Vải vàng phải xác minh đúng `vai_vang`. Nếu panel mở ra là `nuoc_tao` hoặc `tao_say`, đóng panel và chạy wrong-machine recovery.
16. Sản xuất đủ 9 Vải vàng và Sửa máy.
17. Recovery tầng 3/upper-floor → exact-main bằng navigation proof.
18. PASS 3/3 và trả kết quả cho scheduler.
19. Scheduler bán lại theo số vòng đã cấu hình rồi tiếp tục vòng Function kế tiếp.

## Tối ưu route Táo tầng 6 → Nước táo tầng 2

Mục tiêu là bỏ vòng đi dư trước đây:

`floor 6 → goDown(4) → floor 2 → floor 1 → main → floor 1 → floor 2`

Đường bình thường mới:

`floor 6 → goDown(4) → candidate floor 2 → nuoc_tao PASS → production`

`goDown(4)` chỉ là **movement evidence**, tuyệt đối không tự chứng minh đã tới đúng tầng. Gate thật là ảnh `nuoc_tao` trong panel máy.

Probe direct có các ràng buộc:

- tối đa `2` burst x5;
- mỗi burst có tối đa `3` recheck ngắn;
- dùng chung true x5 raw-click helper đã PASS;
- gặp `full_kho` không dùng popup đó làm bằng chứng tầng;
- không thấy `nuoc_tao` thì đóng panel và fallback, không lặp click vô hạn trên tầng sai.

Fallback direct-floor miss:

1. invalidate mọi exact-main proof cũ;
2. dùng `go_down_one_toward_main()` và nút `XUỐNG`/main-boundary đã xây;
3. bắt buộc exact-main PASS;
4. `main → goUp(1) → floor1 → goUp(1) → floor2`;
5. production Nước táo chạy lại qua transaction chuẩn;
6. `InventoryFull` vẫn do warehouse recovery chuẩn xử lý, không bị probe nuốt.

## Bông → Vải vàng: click đúng chậu tầng 4

Forensic bytecode `adb_controller.goUp` từng cho thấy các điểm:

- mode 1: swipe `(514,214) → (514,314)`;
- mode 2: click `(257,416)`;
- mode 3: click `(257,191)`;
- mode 4: swipe `(387,69) → (387,918)`.

**Live correction 2026-09-09:** trong trạng thái Function 1 sau gieo Bông, click `(257,416)` chỉ đưa camera tới tầng 2. Để camera tới máy Vải vàng tầng 3, runtime phải click điểm chậu cao hơn ở tầng 4, dùng tọa độ recovered `(257,191)`.

Chuỗi hiện tại:

1. click common side-close `(975,316)`;
2. click chậu tầng 4 `(257,191)`;
3. chờ `0.70s` + post wait `0.15s`;
4. hậu kiểm fresh-frame change;
5. production Vải vàng xác minh `vai_vang` trước khi xếp hàng;
6. nếu panel mở ra là máy khác thì kích hoạt wrong-machine recovery.

Không được regression về `(257,416)` hoặc hai lần `goUp(1)` cho route này.

## Hợp đồng production

### Thu VP bằng burst x5

Táo sấy, Nước táo và Vải vàng dùng chung nguyên tắc:

- mỗi burst gửi đúng 5 click tức thì tại cùng tọa độ máy;
- không có sleep/capture/check xen giữa 5 click;
- sau burst mới nghỉ theo `vp_collect_delay`;
- sau settle lấy **một fresh frame**;
- `full_kho`, target VP và wrong-machine VP đều được quét trên fresh frame đó;
- panel đúng chỉ được coi là mở khi **ảnh sản phẩm yêu cầu** xuất hiện trong `PRODUCT_SEARCH_ZONE`;
- `o_trong` chỉ được dùng làm diagnostic, không được phép tự chứng minh đúng máy;
- product-image miss tạm thời khi panel đã xác minh đúng là non-blocking và tiếp tục recheck.

Thứ tự bắt buộc:

`x5 raw click → vp_collect_delay → fresh frame → panel_state(frame) → target/wrong-machine scan`

### Sai máy / sai tầng

Khi panel production đã mở nhưng vùng thư viện hiện **một VP production khác** trong bộ:

- `tao_say`;
- `nuoc_tao`;
- `vai_vang`;

runtime phải coi đây là bằng chứng `WrongProductionMachine`, không được tiếp tục click thu VP.

Ví dụ đang cần `vai_vang` nhưng panel hiện `nuoc_tao`:

1. đóng panel SX ngay;
2. phát `WrongProductionMachine`;
3. không tin tầng dự kiến hiện tại;
4. invalidate camera exact-main cũ;
5. dùng unknown-floor `goDown(1)` + nút `XUỐNG` + main-boundary để chứng minh exact-main;
6. từ exact-main đi lại đúng tầng 3;
7. retry production Vải vàng;
8. lần retry vẫn phải xác minh `vai_vang` trước khi xếp hàng.

Wrong-machine recovery giới hạn tối đa `3` lần để không tạo vòng điều hướng vô hạn.

Wrong-machine recovery **không bán VP**. Nó khác hoàn toàn với `InventoryFull` recovery.

### Kho đầy

`InventoryFull` là business signal riêng:

1. quay về exact-main từ tầng đã biết;
2. chạy sale VP thuộc Function hiện tại;
3. quay lại đúng tầng sản xuất;
4. retry đúng production call đang dở.

Không nuốt generic `ScreenTimeout` vào recovery.

### Kéo sản xuất

- Mỗi gesture phải làm giảm số ô trống theo hậu kiểm.
- Với render chậm, runtime recheck nhiều frame và retry gesture có giới hạn trước khi báo lỗi.
- Không retry mù vô hạn destructive gesture.

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

### Quảng cáo quầy — LIVE PASS

Mỗi lượt sale có 3 checkpoint QC gần physical slot `1 / 10 / 20`:

- nếu ô đã có dấu QC đỏ → bỏ qua, không click;
- nếu chưa QC → click listing và kiểm tra popup;
- nếu nút xanh `Đặt quảng cáo` đã hồi → click đúng nút miễn phí;
- nếu còn cooldown → đóng X và tiếp tục;
- không click nút kim cương/quảng cáo trả phí;
- lỗi QC là non-blocking;
- quầy full hoặc kho hết VP vẫn tiếp tục đi hết ba checkpoint QC và thu vàng.

Operator đã chốt QC PASS sau live test.

## Cấu hình tốc độ

Các speed path độc lập:

- `floor_swipe_duration`;
- `plant_harvest_duration`;
- `vp_collect_delay`;
- `vp_production_delay`;
- `crop_check_interval`.

Persistent settings trong `%APPDATA%\KVTM Multi DEV` là authoritative; rebuild `dist` không được overwrite giá trị operator đã lưu.

## Build verifier sau wrong-machine fix

Sau khi thêm fresh-frame shared scan cho wrong-machine, `verify_auto_speed_config_contract.py` cũ bị stale vì vẫn tìm literal:

`warehouse_full, empty_ready = self._panel_state()`

Runtime đúng đã đổi sang:

`frame = self.vision.frame()`

`warehouse_full, empty_ready = self._panel_state(frame=frame)`

Commit `ffa9336565d00c5bf18b36ddc0c64e1246db8a2f` đã sửa **verifier**, không sửa runtime, và khóa thứ tự:

`x5 → settle → fresh frame → panel check → wrong-machine scan`

Build speed gate sau fix phải PASS với marker:

`AUTO MULTI DEV SPEED CONFIG STATIC CONTRACT VERIFIED`

Verifier phải tiếp tục cấm:

- sleep giữa 5 raw click;
- capture/check giữa 5 raw click;
- panel check trước `vp_collect_delay`;
- bỏ `_find_wrong_product_match()` khỏi shared collect path.

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
- `tools/verify_auto_speed_config_contract.py`
- `tools/verify_auto_floor_navigation_contract.py`
- `tools/verify_multi_dev_main_boundary_contract.py`
- `tools/verify_auto_vp_advertising_contract.py`

Production/speed contracts hiện khóa thêm:

- direct `floor6 → goDown(4) → floor2 candidate`;
- bounded `nuoc_tao` proof;
- exact-main fallback + `goUp(1)x2`;
- Bông → tầng 3 phải click chậu tầng 4 `(257,191)`;
- cấm runtime dùng điểm cũ `(257,416)` cho route Vải vàng;
- panel mở nhưng VP sai máy phải đóng và phát `WrongProductionMachine`;
- wrong-machine phải recovery unknown-floor → exact-main → đúng tầng rồi retry;
- collect order phải là x5 → settle → fresh-frame → shared panel scan.

## Quy tắc regression

Không được đưa trở lại các hành vi sau:

- vòng `floor6 → main → floor2` trong đường bình thường khi direct `nuoc_tao` đã PASS;
- direct goDown(4) tự được coi là tầng 2 mà không có anchor `nuoc_tao`;
- probe sai tầng click x5 vô hạn;
- route Bông → Vải vàng dùng `(257,416)` hoặc hai `goUp(1)`;
- panel đã mở sai máy nhưng AUTO vẫn click thu VP vô hạn;
- quét target và wrong-machine trên các frame rời nhau sau cùng một burst;
- sleep/capture/check xen giữa 5 raw click;
- `o_trong` tự chứng minh panel production đúng máy;
- click mù nút xuống tầng;
- background farm làm exact-main gate;
- popup error blocking toàn Multi;
- retry destructive transaction 3–10 lần tại cùng trạng thái mà không recover;
- sale bỏ qua exact-x10/post-verify;
- quảng cáo click ô đã có QC;
- quảng cáo click nút trả phí;
- quầy full làm sale workflow kết thúc trước khi hoàn tất ba checkpoint QC.
