# AUTO MULTI DEV — TỰ TẠO AUTO HANDOFF

Cập nhật: 2026-09-08

## Mục tiêu đã khóa

Người vận hành phải tự xếp đúng thứ tự nghiệp vụ trên giao diện, thay vì AI suy luận thứ tự từ mô tả bằng chữ. AUTO Builder là Scheduler trực quan DEV-only, dùng lại engine click/swipe/vision và isolated Bridge V3 hiện tại.

## Ba module nghiệp vụ độc lập

### `ENTER_GAME_POPUP`

- UI: `MODULE • Vào game + đóng popup`.
- Runtime: `EnterGamePopupModule` gọi riêng `GameSessionWorkflow`.
- Không tự bán VP.
- Không tự gọi Function.
- Trong Builder không có `GameSessionWorkflow` ẩn ở đầu worker; module chỉ chạy tại đúng vị trí operator đặt.

### `SELL_FUNCTION_VP(function_id)`

- UI: `MODULE • Bán VP theo Function`.
- Runtime: `SellFunctionVpModule` tra `FunctionSpec` rồi gọi `AutoVpSaleWorkflow` với đúng danh sách VP của Function.
- Function 1 hiện khai báo `tao_say`, `vai_vang`.
- Giữ nguyên exact-x10, xác minh đúng vật phẩm sau chọn, thu vàng trước khi treo, fail-close và đóng quầy trong finally.
- Dọn quầy không được gọi từ module này.

### `FUNCTION(function_id)`

- UI: `FUNCTION • Function 1`.
- Runtime hiện hỗ trợ `function_1` qua `FunctionOneWorkflow`.
- Có `loops=1..999`.
- Có `sale_after_each_loop`.
- Nếu bật, Scheduler gọi **module SELL_FUNCTION_VP riêng** sau mỗi vòng Function; sale không được nhúng vào Function.

## Các block thao tác Builder v1

- Vào game + đóng popup.
- Bán VP theo Function.
- Function 1 + số vòng + bán sau mỗi vòng.
- Nhận diện ảnh người dùng chọn: threshold + zone, fresh frame, fail-close.
- Click tọa độ logic 0..1000.
- Swipe x1,y1 → x2,y2 + duration.
- Wait.
- Kết thúc PASS.
- Kết thúc FAIL.

Chưa làm ở v1: If/Else, Goto, counter tổng quát, crop template trực tiếp từ Live View, click vào tâm match trước đó. Các phần này sẽ bổ sung sau khi v1 live-pass.

## Giao diện

Builder được gắn thành tab `TỰ TẠO AUTO` ngay sau `AUTO MULTI DEV`, dùng cùng tab strip và style của Multi DEV:

- nền tab `#e8eef7`;
- chữ `#263653`;
- active `#dce8f8/#1768c4`;
- `Segoe UI Semibold 9`;
- editor dùng `Queue.Treeview`;
- nút chạy/lưu dùng `AutoStart.TButton`/`Action.TButton`.

Không sửa `kvtm_multi.py` để nhét Builder trực tiếp. `auto_builder_integration.py` gắn DEV-only UI vào `MultiDevApp` tại host, nên production/shared UI core giữ nguyên.

## Lưu plan và ảnh nhận diện

Builder lưu ở:

`%APPDATA%\KVTM Multi DEV\auto-builder`

Mục đích: dữ liệu người dùng không nằm trong `dist` bị xóa/rebuild bởi Control Center `[1]`. Nếu bản thử cũ từng có `data-dev/auto-builder`, store sẽ cố migrate sang vùng AppData khi vùng mới chưa tồn tại.

## Isolated worker / CAPTURE3

Builder không tạo transport mới. Nó dùng lại lifecycle AUTO MULTI DEV:

- một worker riêng/profile;
- cùng busy gate;
- cùng Stop relay;
- preview/live capture nhường ownership trước worker;
- Bridge V3 strict;
- `CAPTURE3_WRITERMAP2`;
- `CAPTURE3_WRITERMSG1`;
- không stale frame;
- không HWND fallback.

UI đặt snapshot plan vào `auto-builder-plan.json` trong work-dir **của đúng run**. Worker chỉ chuyển `main` → `builder` khi marker riêng của run tồn tại, hoặc khi được gọi trực tiếp với `--mode builder --plan-json`. Plan khác/run khác không dùng chung marker.

## Static gate

`tools/verify_auto_builder_contract.py` khóa:

- ba module độc lập;
- Function metadata sở hữu VP sale;
- Function loop gọi sale từ Scheduler;
- Builder không prepend GameSession ẩn;
- custom image/click/swipe/wait;
- style UI khớp Multi DEV;
- AppData persistence;
- isolated worker strict V3;
- không gọi Dọn quầy / legacy business pyc.

Gate này được gọi từ `verify_auto_main_sale_contract.py`, nên Control Center `[1]` sẽ chạy nó trong chuỗi build bình thường.

## Giới hạn runtime cần nhớ

**Chưa gọi AUTO Builder live PASS.** Đây mới là source/static implementation chờ Control Center + Windows live test.

Quan trọng nhất: Function 1 hiện kết thúc sau SX Vải vàng tại mốc tầng 3. Operator yêu cầu sau mỗi Function có thể quay lại module bán VP. Scheduler đã gọi đúng sale module theo cấu hình, nhưng **route tầng 3 → màn hình chính vẫn chưa được live-prove hoàn chỉnh**. `AutoVpSaleWorkflow` sẽ fail-close nếu không xác nhận được main; không được thêm route tầng giả/đoán để ép vòng lặp chạy.

## Next live test

1. Control Center `[1]`.
2. Build phải có `AUTO MULTI DEV AUTO BUILDER STATIC CONTRACT VERIFIED` trước `AUTO MULTI DEV VP SALE STATIC CONTRACT VERIFIED`.
3. `[2]` mở Multi DEV.
4. Xác nhận tab `TỰ TẠO AUTO` xuất hiện ngay sau `AUTO MULTI DEV`, đúng style.
5. Mở trình tạo và kiểm tra plan mặc định có đúng 3 bước:
   - Vào game + đóng popup;
   - Bán VP Function 1;
   - Function 1 ×1, bán VP sau mỗi vòng.
6. Test runtime đầu tiên nên tạo plan an toàn: `Vào game + đóng popup → Kết thúc PASS`. Chưa dùng Function loop để đánh giá UI/worker plumbing.
7. Khi v1 UI/worker PASS, tiếp tục block Function và sau đó xử lý riêng route sau Function 1 → main trước khi gọi sale lặp.

## Commit chain của mốc Builder

Bắt đầu từ head trước Builder: `8e77c90f44c37d9bd25d11b1cf61403e7695ac40`.

Các commit Builder được tạo tuần tự trên `develop/multi-auto-dev`; xem HEAD mới nhất để lấy toàn bộ chuỗi. Không cherry-pick từng file rời khỏi chuỗi nếu không có lý do rõ ràng.
