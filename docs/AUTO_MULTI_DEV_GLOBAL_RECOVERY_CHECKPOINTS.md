# AUTO MULTI DEV — Global module recovery checkpoints

Cập nhật: 2026-09-11
Trạng thái: SOURCE READY FOR LIVE TEST + TARGET DESIGN IN PROGRESS

> Tài liệu chuẩn hóa tổng thể mới nhất: `docs/AUTO_MULTI_DEV_STANDARDIZATION_LATEST.md`.
> Nếu tài liệu cũ xung đột với target mới, ưu tiên trạng thái `CHỐT/CẦN CHỐT` trong tài liệu chuẩn hóa mới nhất.

## Mục tiêu

Kho đầy, sai máy hoặc các lỗi recoverable khác là **sự kiện tạm ngắt module**, không phải tín hiệu kết thúc Function loop.

Luồng bắt buộc:

```text
AutoMain
  -> Function loop N
    -> Recipe
      -> Module đang chạy
        -> lỗi recoverable
        -> giữ checkpoint module
        -> RecoveryManager xử lý
        -> quay lại đúng trạng thái/tầng
        -> chạy tiếp CÙNG module
      -> module PASS
    -> Function PASS
  -> chỉ lúc này AutoMain mới được tăng loop
```

Không được dùng recovery để trả control sớm về `AutoMain`, vì như vậy vòng N chưa xong nhưng scheduler có thể hiểu nhầm và mở vòng N+1.

## Thành phần source hiện tại

### `recovery/module_execution.py`

`ModuleRecoveryExecutor` là lớp checkpoint chung.

Mỗi lần chạy module tạo `ModuleCheckpoint` gồm:

- `function_id`;
- `module_id`;
- `label`;
- `floor` nếu biết;
- số lần bị ngắt;
- loại lỗi gần nhất.

Executor chỉ bắt **error type được module/policy đăng ký**. Lỗi không đăng ký phải fail-close; đặc biệt không blind retry `ScreenTimeout`.

Lifecycle event:

- `MODULE_STARTED`;
- `MODULE_INTERRUPTED`;
- `MODULE_RESUMED`;
- `MODULE_COMPLETED`.

Sau `MODULE_INTERRUPTED`, executor giữ quyền điều khiển. Handler phục hồi xong thì executor gọi lại đúng `runner` của module. Chỉ `MODULE_COMPLETED` mới return cho Recipe/Function.

## Production recovery hiện tại

`ProductionRecovery` chạy production qua `ModuleRecoveryExecutor`.

Các handler hiện tại:

- `WrongProductionMachine`: về exact-main, quay lại đúng tầng máy, retry cùng production module;
- `InventoryFull`: xuống main, bán VP đúng Function, quay lại đúng tầng máy, retry cùng production module.

Nếu kho vẫn đầy sau khi quay lại, module phát `InventoryFull` lần nữa và **cùng checkpoint** lại xuống bán. Không tạo Function loop mới.

Một lượt sale recovery được xem là có tiến triển nếu:

- treo được ít nhất một listing; **hoặc**
- thu được ít nhất một ô vàng, vì việc thu vàng có thể giải phóng quầy để lượt recovery kế tiếp treo VP.

Chỉ khi cả `sold_listings == 0` và `collected_gold_slots == 0` mới fail-close để tránh lặp vô hạn không tiến triển.

Commit source hiện tại liên quan: `b52befd4dbfab5c3a17175f1ddd43948244dcf32`.

**Không được gọi runtime PASS cho checkpoint mới cho tới khi operator live-test và xác nhận.**

## Contract với Function

Function không tự viết vòng bắt lỗi. Function chỉ compose Recipe/Module.

`AutoMain` chỉ được tăng `function_loops` sau khi `FunctionModule.run(...)` trả PASS. Vì checkpoint recovery không return khi module còn dang dở, scheduler không được hợp lệ bắt đầu vòng mới trong lúc recovery.

## ActiveCheckpoint trong RAM — CHỐT

Checkpoint RAM phải nhẹ và theo từng profile.

### Một profile = một active checkpoint

```text
profile_id
  -> ActiveCheckpoint duy nhất
```

Checkpoint được cập nhật tại chỗ theo tiến độ, không append lịch sử vô hạn.

Ví dụ:

```text
production 3/9 -> completed=3
production 4/9 -> update completed=4
```

### Chỉ lưu metadata/state nhỏ

Có thể gồm:

- `profile_id`;
- `function_id`;
- `function_loop`;
- `module_id`;
- `recipe_id`;
- `task_id`;
- `floor`;
- `step`;
- `completed_count`;
- `target_count`;
- `retry_count`;
- `recovery_reason`.

Không lưu object nặng:

- screenshot/frame OpenCV;
- numpy image array;
- template image;
- automation/driver object;
- toàn bộ log history.

Mục tiêu: checkpoint chỉ vài KB/profile, không tạo áp lực RAM đáng kể so với ClientJS/OpenCV/capture runtime.

## Friend Refresh escalation — TARGET ĐÃ THỐNG NHẤT MỤC TIÊU

Friend Refresh có hai vai trò độc lập:

1. maintenance định kỳ sau N vòng;
2. recovery escalation khi local recovery/retry không giải quyết được lỗi.

Recovery path mục tiêu:

```text
module lỗi
→ local retry có giới hạn
→ Friend Refresh
→ về exact-main
→ resume cùng checkpoint
→ thử lại module
```

Periodic counter và recovery counter không dùng chung.

Số retry cụ thể theo từng loại lỗi vẫn phải được chốt theo policy; không dùng random 3/4/5.

## ClientJS restart escalation — TARGET

Restart định kỳ mới được yêu cầu đổi từ 2 giờ sang **3 giờ**, và chỉ tại Function safe boundary.

User cũng yêu cầu nếu cùng lỗi đã trải qua **2 lượt Friend Refresh** mà vẫn không giải quyết được thì nâng cấp lên restart ClientJS.

Có một điểm kiến trúc còn cần chốt rõ:

- scheduled restart: chỉ sau Function PASS;
- recovery/emergency restart: nếu xảy ra giữa Function thì cần durable checkpoint để không mất công việc đang dở.

Không được restart vô hạn cùng một checkpoint.

## Durable checkpoint — CẦN CHỐT CHI TIẾT

Nếu worker/process vẫn sống, ActiveCheckpoint RAM là đủ cho retry/navigation/Friend Refresh.

Nếu recovery restart làm mất process state, đề xuất dùng một JSON checkpoint nhỏ trên disk:

```text
Runtime ActiveCheckpoint (RAM)
        +
DurableCheckpoint (disk, chỉ khi cần sống qua restart)
```

Sau startup/rebind:

```text
login verified
→ wait 60s
→ popup cleanup
→ exact-main
→ load durable checkpoint
→ resume đúng Function/Module đang dở
```

Sau khi module/Function hoàn tất phải clear durable checkpoint.

## Mở rộng module

Các module mới có thể dùng:

```python
recovery.run_module(
    module_id="...",
    label="...",
    floor=...,
    runner=...,
    handlers=((TypedRecoverableError, handler),),
)
```

Policy phải nằm trong recovery/module tương ứng, không copy vào từng Function.

## Recovery ladder mục tiêu

```text
Typed/Specialized Recovery
        ↓
Local retry có giới hạn
        ↓
Friend Refresh #1
        ↓
resume checkpoint + retry
        ↓
Friend Refresh #2 nếu vẫn lỗi
        ↓
resume checkpoint + retry
        ↓
Recovery Restart nếu policy được chốt
        ↓
resume checkpoint
        ↓
Fail-close khi vượt giới hạn
```

Không được:

- retry vô hạn;
- Friend Refresh vô hạn;
- restart vô hạn;
- reset Function loop chỉ vì recovery;
- tăng `function_loops` trước Function PASS.

## Test live bắt buộc cho checkpoint source hiện tại

1. Bắt đầu một Function loop.
2. Làm kho đầy tại một production module.
3. Xác nhận log có `MODULE_INTERRUPTED` và cùng `checkpoint=...`.
4. AUTO xuống bán.
5. AUTO quay lại đúng tầng/module.
6. Xác nhận log có `MODULE_RESUMED` với cùng checkpoint.
7. Nếu kho vẫn đầy, lặp lại bước bán/resume trên cùng checkpoint.
8. Chỉ sau `MODULE_COMPLETED` và Function PASS mới được thấy `vòng N PASS` / `vòng N+1 START`.

Build/static PASS chưa phải runtime PASS.
