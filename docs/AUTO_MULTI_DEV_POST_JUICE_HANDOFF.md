# AUTO MULTI DEV — Handoff sau SX Nước táo

## Lỗi live người dùng xác nhận

Sau khi sản xuất đủ Nước táo, route cũ có thể tạo hiệu ứng thực tế kiểu `goDown(1)` rồi ngay sau đó action trồng Bông phát `goUp(1)`. Khi camera chưa thật sự được chuẩn hóa về màn hình chính, hai nhịp này triệt tiêu nhau và làm lệch mốc trồng Bông; lỗi mốc sau đó kéo theo sai tầng khi sang SX Vải vàng.

## Quy tắc đã chốt

Exact-main check không đặt ở startup. Nó chỉ được dùng tại transition nghiệp vụ giữa các lượt trồng cây / sản xuất VP.

Riêng transition **sau SX Nước táo -> trước trồng Bông** phải làm:

1. Từ trạng thái máy Nước táo, phát `goDown(1)` lần 1.
2. Phát thêm đúng 3 lần `goDown(1)` để ép camera về đáy giống low-floor normalization.
3. Sau mỗi nhịp phải lấy fresh CAPTURE3 để ghi diagnostic.
4. Các nhịp settle cuối có thể đã chạm biên nên `frame_change` thấp/0 không được tự coi là lỗi.
5. Sau đủ `1+3`, `FunctionOneWorkflow` gọi exact `is_own_main_screen()`.
6. Chỉ khi exact-main PASS mới cho `CottonPlantingActions` chạy.
7. Lúc đó `CottonPlantingActions._open_seed_picker()` mới phát đúng **một** `goUp(1)` từ main lên mốc trồng Bông.

Không được quay lại route 2 nhịp cố định `floor2 -> floor1 -> main` rồi lập tức để Bông `goUp(1)`, vì live evidence cho thấy camera có thể chưa thật sự ở main.

## Source đã sửa

- `components/clientjs-auto/kvtm_automation/actions/function_one_pass_three_navigation.py`
  - `floor_2_to_main()` nay dùng 4 lần `goDown(1)` theo mô hình `1 probe + 3 settle`.
  - `_settle_down_one()` lấy fresh frame sau từng gesture nhưng không fail chỉ vì chạm biên làm `frame_change` thấp.
  - exact-main gate vẫn ở `FunctionOneWorkflow._require_main_transition("sau SX Nước táo → trước trồng Bông")`.

Commits:

- `6bf99ce238b46277ecbd2cee67662472e70b94db` — normalize post-juice descent before cotton.
- `d9d42e4c3f957ca24e7d4ae5049a43978d7ba41b` — allow boundary settling after juice.

## Chưa chốt live

Chưa gọi PASS cho route này cho tới khi live log chứng minh thứ tự:

`SX Nước táo hoàn tất -> post-juice goDown 1/4 -> 2/4 -> 3/4 -> 4/4 -> exact main PASS -> Bông goUp(1) -> trồng 27 Bông`

Nếu sau khi route này PASS mà tầng SX Vải vàng vẫn lệch, lúc đó mới xử lý riêng transition **sau trồng Bông -> trước SX Vải vàng**. Không sửa đồng thời hai transition khi chưa có bằng chứng live tách biệt.

## Quy trình user test

Dùng Control Center `[1] Cap nhat source + build runtime DEV`, sau đó `[2]` mở Multi DEV. Không dùng manual pull/build thay thế.
