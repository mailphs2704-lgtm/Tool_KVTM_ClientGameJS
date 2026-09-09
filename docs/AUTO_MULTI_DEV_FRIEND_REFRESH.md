# AUTO MULTI DEV — Friend Refresh chống item treo

Cập nhật: 2026-09-09

## Mục tiêu

Game đôi khi để lại item/layer treo trên màn hình khiến các thao tác AUTO phía sau bị kẹt. Cơ chế Friend Refresh là maintenance chung của AUTO Main, không thuộc riêng Function 1 hay Recipe nào.

Khi operator bật công tắc trên GUI, sau mỗi đúng 3 vòng Function đã PASS (`3 / 6 / 9 / ...`) scheduler sẽ:

1. hoàn tất lượt bán VP/QC nếu đúng lúc tới lịch bán;
2. đảm bảo camera đang ở exact-main;
3. mở danh sách bạn bè bằng navigation clean đã dùng trong Dọn quầy;
4. chọn **nhà bạn mặc định đầu tiên** (`friend #1`);
5. xác minh đã sang nhà bạn bằng `icon_home`;
6. chờ scene ổn định ngắn;
7. bấm `icon_home` quay về nhà;
8. xác minh own-farm HUD và ghi lại exact-main bằng bằng chứng route deterministic;
9. tiếp tục vòng Function kế tiếp.

Startup sale #1 không được tính là một vòng Function. Trigger maintenance tính theo số vòng Function hoàn tất.

## GUI

Trong tab AUTO MULTI DEV có khối:

`LÀM MỚI ITEM TREO`

Công tắc:

`Qua bạn #1 / 3 vòng`

- TẮT: scheduler giữ hành vi cũ, không sang nhà bạn định kỳ.
- BẬT: chạy Friend Refresh sau vòng 3/6/9/...

Giá trị được lưu persistent trong `%APPDATA%\KVTM Multi DEV\settings.json` bằng key:

`auto_multi_dev_friend_refresh_enabled`

Mỗi run vẫn đóng băng giá trị hiện tại vào `auto-main-config.json` để worker isolated dùng đúng cấu hình lúc bấm Start.

## Vị trí trong kiến trúc

```text
AUTO Main Scheduler
  ├─ Sale/QC
  ├─ Function hiện tại
  ├─ Sale nếu tới lịch
  ├─ FriendRefreshWorkflow nếu loop % 3 == 0 và toggle=BẬT
  └─ vòng Function kế tiếp
```

Cơ chế nằm ở scheduler vì phải áp dụng cho **mọi Function**, không được copy vào từng Function/Recipe.

Source:

- `components/clientjs-auto/kvtm_automation/workflows/auto_main/friend_refresh.py`
- `components/clientjs-auto/kvtm_automation/workflows/auto_main/workflow.py`
- `source-archive/multi-current/kvtm_multi_tool/auto_builder_integration.py`
- `components/clientjs-auto/worker/auto_multi_dev_worker.py`

## Tái sử dụng navigation Dọn quầy

Không thêm template hoặc tọa độ friend mới. Friend Refresh dùng trực tiếp:

- `NavigationActions.go_to_friend(1)`
- `NavigationActions.return_home()`

Đây là cùng primitive Dọn quầy đã dùng để sang nhà 1..N rồi quay về clone.

Các ảnh dùng chung từ thư viện AUTO MULTI DEV:

- `friend`
- `list_friend`
- `add_friend`
- `icon_home`
- `cua_hang`

Friend #1 là card đầu tiên trong danh sách visible đã prove. Maintenance không mở quầy nhà bạn, không scan quầy, không mua VP và không chạy workflow Dọn quầy.

## Exact-main

Không dùng background/farm artwork để chứng minh exact-main.

Trước khi rời nhà:

- nếu exact-main proof hiện tại không còn hợp lệ, dùng `RecoveryManager.recover_unknown_to_main()`.

Khi bắt đầu chuyển nhà:

- invalidate exact-main proof cũ.

Sau `friend #1 → icon_home → nhà mình`:

- route chuyển world được coi là deterministic return-home route;
- runtime ghi `mark_camera_exact_main(...)`;
- sau đó vẫn bắt buộc own-farm HUD PASS trước khi maintenance hoàn tất.

## Chính sách lỗi

Friend Refresh là maintenance chống lỗi, không được tạo thêm vòng kẹt mới.

Nếu sang nhà/quay về lỗi:

1. thử `ensure_main_screen()` để đóng popup hoặc quay về từ nhà bạn nếu vẫn còn ở đó;
2. dùng central `RecoveryManager` để normalize unknown camera → exact-main;
3. nếu recovery exact-main PASS: log `RECOVERED`, bỏ maintenance lần đó và tiếp tục AUTO;
4. nếu không chứng minh được exact-main: fail-close bằng `ScreenTimeout`, để worker runtime-error policy xử lý.

`AutomationStopped` luôn được truyền ra ngay, không bị maintenance nuốt.

## Thứ tự với Sale

Nếu vòng thứ 3 đồng thời tới lịch bán, thứ tự là:

`Function 3 PASS → Sale/QC tới hạn → Friend Refresh → Function 4`

Như vậy không làm thay đổi sale/QC đã live-pass.

Nếu `sale_every_loops` khác 1, Friend Refresh vẫn chạy theo **3 vòng Function**, không theo số lần sale. Đây là cơ chế scheduler độc lập và áp dụng chung cho mọi Function.

## Build contract

`tools/verify_auto_main_sale_contract.py` khóa:

- GUI có toggle Friend Refresh;
- default worker = OFF;
- config truyền GUI → marker → worker → scheduler;
- trigger chính xác mỗi 3 Function loops;
- friend ordinal cố định = 1;
- tái sử dụng `go_to_friend` / `return_home`;
- không được mở friend stall, mua VP hoặc gọi Dọn quầy runtime;
- exact-main proof phải invalidate khi rời nhà và được phục hồi an toàn khi quay về.

Build kỳ vọng thêm marker:

```text
friend_refresh=gui-toggle+every3-function-loops+friend1-return-home
friend_refresh_navigation=reuse-clean-navigation-assets-no-friend-stall
```

## Live test cần xác nhận

### Toggle OFF

Chạy quá 3 vòng Function và xác nhận không có log `maintenance chống item treo` / không sang nhà bạn.

### Toggle ON

Sau vòng 3:

```text
AUTO MULTI DEV • maintenance chống item treo đến hạn • vòng Function=3 • qua nhà bạn #1 rồi quay về
AUTO refresh item treo • đã sang nhà bạn #1
AUTO refresh item treo • PASS • nhà bạn #1 → nhà mình → exact-main • scene đã được làm mới
```

Sau đó Function 4 phải START bình thường từ nhà mình.

Tiếp tục quan sát vòng 6 để xác nhận trigger lặp đúng chu kỳ.
