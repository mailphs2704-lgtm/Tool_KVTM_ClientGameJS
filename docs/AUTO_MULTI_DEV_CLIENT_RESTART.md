# AUTO MULTI DEV — periodic ClientJS restart

## Trạng thái hiện tại

Cơ chế restart ClientJS là maintenance chung của AUTO Main, không thuộc riêng Function 1 hay một Recipe.

**LIVE TEST hiện tại: 60 giây/lần.** Sau khi test PASS, đổi hằng số test sang **7200 giây (2 giờ)**.

Các hằng số test đang được khóa ở:

- `AutoMainWorkflow.CLIENT_RESTART_TEST_INTERVAL_SECONDS = 60.0`
- `_CLIENT_RESTART_TEST_INTERVAL_SECONDS = 60.0` trong `auto_builder_integration.py`

## Safe boundary

Timer đến hạn **không được phép cắt ngang Function, production, planting hoặc sale**.

Luồng chuẩn:

```text
đến hạn restart
→ nếu Function đang chạy: chỉ ghi pending
→ tiếp tục cho đủ số vòng giữa hai lần bán
→ chạy lượt bán VP/QC đến khi hoàn tất và đóng quầy
→ phát ClientRestartRequested
→ worker thoát cooperative
→ Multi đóng đúng ClientJS của profile đó
→ chờ supervisor worker cũ kết thúc hoàn toàn
→ mở lại đúng profile ClientJS
→ tạo worker mới / Bridge V3 generation mới
→ vào game + đóng popup + exact-main
→ bỏ sale đầu đúng 1 lần vì sale đã hoàn tất ngay trước restart
→ tiếp tục Function loop bình thường
```

Sale đầu của lần chạy AUTO do operator bấm Start vẫn giữ nguyên. Chỉ run được tạo ra sau một periodic ClientJS restart mới có `skip_initial_sale_once=true`.

## Tại sao restart chỉ sau sale

Function có nhiều thao tác có side effect: trồng cây, thu VP, sản xuất, repair và các recovery transaction. Restart giữa một Function có thể làm mất trạng thái transaction và khiến scheduler chạy lại từ đầu không an toàn.

Vì vậy timer chỉ đặt cờ `due`; quyền restart chỉ được cấp sau nhánh:

```text
Function PASS đủ vòng cấu hình
→ AutoVpSaleWorkflow PASS
→ quầy đã đóng
→ ClientRestartRequested
```

Nếu `sale_every_loops=3`, timer hết trong vòng 1 thì AUTO vẫn hoàn thành vòng 1, 2, 3 và lượt bán sau vòng 3 rồi mới restart.

## Handoff worker → Multi

`ClientRestartRequested` kế thừa `AutomationStopped` để dùng đúng cooperative-stop channel sẵn có. Worker không tự kill ClientJS; nó trả reason có prefix:

```text
CLIENT_RESTART_REQUESTED|...
```

Multi DEV intercept đúng prefix này, không hiển thị trạng thái Stop thông thường và chỉ recycle profile đã yêu cầu restart.

Multi giữ `active_config` của profile, ghi lại marker `auto-main-config.json` cho worker mới và set:

```json
{
  "skip_initial_sale_once": true
}
```

Worker mới vẫn dùng lifecycle/Bridge V3 bình thường; không có hai worker cùng sở hữu CAPTURE3.

## Ownership/race guard

Không được launch worker mới ngay khi nhận event `worker_stopped`, vì callback GUI có thể chạy trước khi supervisor thread cũ tới `finally`.

Multi phải chờ `old_thread.is_alive() == false`, sau đó mới xóa ownership map và relaunch ClientJS/worker mới. Điều này tránh supervisor cũ pop nhầm worker mới khỏi `_clean_main_workers`.

## Operator Stop

Nếu operator bấm Dừng trong lúc đang chờ restart/relaunch, pending restart và active resume config phải bị hủy trước khi gọi lifecycle Stop cũ. AUTO không được tự mở ClientJS lại sau lệnh Stop của operator.

## Log live-test cần thấy

Khi timer 60 giây đến giữa Function:

```text
AUTO MULTI DEV • đến giờ restart ClientJS nhưng chưa ở safe boundary
... tiếp tục đủ vòng và bán VP xong mới restart
```

Sau sale boundary:

```text
AUTO MULTI DEV • restart ClientJS SAFE • đã hoàn tất Function boundary và bán VP xong
```

GUI parent:

```text
AUTO MULTI DEV • SAFE RESTART • đã bán VP xong • đang đóng ClientJS
AUTO MULTI DEV • ClientJS cũ đã đóng • đang mở lại đúng tài khoản
AUTO MULTI DEV • ClientJS đã restart • worker mới đang nhận lại AUTO
```

Worker mới:

```text
AUTO MULTI DEV • resume sau restart ClientJS • bỏ sale đầu một lần
```

Sau đó phải đi thẳng vào Function loop tiếp theo của scheduler mới.

## Điều kiện PASS test 1 phút

1. Timer đến hạn giữa Function không đóng ClientJS ngay.
2. AUTO hoàn thành đủ vòng cấu hình và lượt bán VP trước restart.
3. Chỉ đúng ClientJS/profile yêu cầu bị đóng.
4. ClientJS được mở lại tự động.
5. Worker mới kết nối Bridge V3 và vào lại game thành công.
6. Không có hai worker cùng profile chạy đồng thời.
7. Run sau restart không lặp lại sale đầu ngay lập tức.
8. Function tiếp tục chạy bình thường sau relaunch.
9. Nút Dừng trong lúc pending restart phải hủy relaunch.

Sau khi đủ các điều kiện trên, đổi `60.0` thành `7200.0` ở hai hằng số được nêu đầu tài liệu và chạy lại static contract + smoke test.