# Dọn quầy — clean ClientJS workflow

Đây là implementation chính thức duy nhất của chức năng **Dọn quầy** trong Multi DEV.
Runtime của workflow này **không import** `automation.pyc`, `adb_controller.pyc`, `image_processor.pyc` hay `FarmAutomation`. AUTO PRO cũ chỉ còn là nguồn tham chiếu hành vi, asset/template và các thư viện binary đã đóng gói.

## Execution path

```text
Multi scheduler / nút chạy
  -> worker/clear_stall_worker.py
  -> KVAutomation
  -> actions/*
  -> runtime/*
  -> PCDriver / EngineDriver
  -> GameClientJS
```

Probe chỉ đọc dùng cùng `runtime/*` và `actions/*`, nhưng không gọi API mua/bán.

## State machine nghiệp vụ

```text
WAIT_TIMER
-> START_CLONE
-> WAIT_GAME_READY
-> DISMISS_POPUPS
-> MAIN_SCREEN
-> OPEN_FRIENDS
-> SELECT_FRIEND
-> FRIEND_HOME
-> OPEN_FRIEND_STALL
-> SCAN_20_SLOTS
-> PURCHASE
-> RETURN_CLONE_HOME
-> OPEN_OWN_STALL
-> RESELL_BATCHES_OF_10
-> COMPLETE
-> CLOSE_CLONE
-> RESET_PROFILE_TIMER
```

Mỗi state phải có điều kiện xác nhận bằng hình ảnh/trạng thái. Không được coi một click là thành công chỉ vì đã gửi input.

## Contract đã xác nhận

### Nhà bạn

`friend_ordinal` hiện giới hạn **1..7**. Đây là bảy card bạn bè có tọa độ đã xác nhận từ `GoFiendHome`. Chưa có bằng chứng đủ chắc về paging danh sách sau card 7 nên clean runtime cố ý từ chối thay vì đoán.

### Quầy nhà bạn

Nhà bạn có **một quầy 20 ô**. Client chỉ hiện 8 ô một lần. Workflow dùng 4 view chồng lấn:

- view 1: ô vật lý 1..8;
- view 2: bốn ô mới 9..12;
- view 3: bốn ô mới 13..16;
- view 4: bốn ô mới 17..20.

Do đó cấu hình `max_scan_pages` cũ chỉ còn để tương thích schema/CLI và luôn được chuẩn hóa thành **4 view**.

### Trường `stall_id` cũ

Tên cũ gây hiểu nhầm. Call flow đã đối chiếu cho thấy `buy_sell_friend_kho_id`/`stall_id` không chọn một quầy thứ hai ở nhà bạn; nó được chuyển sang `SellBy` khi clone bán lại hàng.

Tên nội bộ mới là `resale_storage_id` / **Kho VP**, hỗ trợ 1..5:

1. kho nông sản;
2. kho thành phẩm;
3. kho vật dụng;
4. kho khoáng sản;
5. kho event.

CLI và settings vẫn giữ key cũ ở boundary để không làm mất dữ liệu cấu hình cũ.

## Mua VP

- Scan xong view 4 thì rewind về view 1.
- Mỗi listing được kiểm tra fingerprint trước mỗi lần click.
- Có thể click lặp cùng một listing tới khi đạt `buy_quantity` hoặc listing biến mất.
- Sau click chờ theo nhịp đã tham chiếu từ AUTO PRO rồi kiểm tra dấu `x` báo kho đầy.
- Mỗi đơn vị chỉ được cộng vào manifest sau khi click đã qua bước xác nhận tương ứng.
- Kho đầy không làm mất giao dịch đã xác nhận; workflow chuyển sang giai đoạn bán lại với số đã mua được.

## Bán lại

Rule bắt buộc:

- Nhóm **theo từng loại VP**, không cộng lẫn loại.
- Chỉ treo khi một loại có đủ **10 VP**.
- Mỗi ô quầy treo đúng **10 VP**.
- `6 A + 4 B` = không có batch bán.
- `13 A` = bán 10, giữ 3.
- Lần sau `3 A carryover + 7 A mới` = bán 10.
- Nếu game không còn expose lựa chọn x10 cho loại đó, giữ lại và bỏ qua loại đó trong phiên.
- Nếu quầy clone hết ô trống, giữ toàn bộ batch chưa treo cho lần sau và vẫn kết thúc phiên an toàn.

## Carryover

State thuộc riêng từng profile:

```text
data-dev/clear-stall/<profile-id>/
  state/
    carryover.json
    templates/<perceptual-hash>.png
  <run-id>/ hoặc runs/<run-id>/
    transaction.json
    templates/
    captures/
```

`state/` là dữ liệu cần cho phiên sau; run folder là audit/diagnostics. Builder giữ `data-dev/clear-stall` khi rebuild fixed DEV nhưng tạo ZIP trước khi restore dữ liệu, nên carryover/profile data không được phát hành trong ZIP.

## Phân lớp

- `runtime/`: bridge, binary dependencies, asset lookup, OpenCV matching, wait/cancellation.
- `actions/`: thao tác tái sử dụng; popup, navigation, stall, buying, inventory, selling.
- `models.py`: fingerprint và observation thuần domain.
- `workflows/clear_stall/config.py`: input contract.
- `manifest.py`: giao dịch đã xác nhận và batch 10.
- `state.py`: carryover bền vững theo profile.
- `workflow.py`: state machine nghiệp vụ, không chứa tọa độ click chi tiết.
- `worker/clear_stall_worker.py`: process boundary/JSON events only.
- `worker/clear_stall_live_probe.py`: diagnostics chỉ đọc.

## Provenance của hằng số

Khi thêm/chỉnh tọa độ, vùng ảnh hoặc threshold phải ghi rõ nguồn trong comment/docstring bằng một trong ba nhóm:

- **AUTO_PRO_REFERENCE**: trích từ bytecode/trace AUTO PRO cũ; dùng làm hành vi tham chiếu, không chạy `.pyc` ở runtime.
- **LIVE_VERIFIED**: đã xác nhận trực tiếp trên GameClientJS thật.
- **CLIENTJS_NATIVE**: thuộc bridge/cửa sổ 1000x1000 và không phụ thuộc logic AUTO PRO.

Không được thêm magic-number mới vào `workflow.py`; geometry phải thuộc action/runtime phù hợp.

## Quy tắc phát triển

1. Không tạo `*_final`, `*_new`, `*_test2`, `.bak`, dump hoặc probe tạm trong source.
2. Không tạo implementation Dọn quầy thứ hai ngoài package này.
3. Không import ngược từ runtime/action lên workflow.
4. Probe không được gọi API giao dịch.
5. Stop phải cooperative qua `AutomationContext.ensure_running()`.
6. Mọi thay đổi nghiệp vụ batch/carryover phải có regression test CI.
7. Hai worker Dọn quầy có forbidden-token guard ở builder/CI; tái nhập legacy `.pyc` sẽ làm build fail.
8. Chỉ mở rộng bạn bè >7 sau khi có geometry/paging được xác nhận bằng trace hoặc live test.
