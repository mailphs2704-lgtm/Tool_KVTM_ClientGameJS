# AUTO MULTI DEV — Global module recovery checkpoints

Cập nhật: 2026-09-11

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

## Thành phần

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

### Production

`ProductionRecovery` chạy production qua `ModuleRecoveryExecutor`.

Các handler hiện tại:

- `WrongProductionMachine`: về exact-main, quay lại đúng tầng máy, retry cùng production module;
- `InventoryFull`: xuống main, bán VP đúng Function, quay lại đúng tầng máy, retry cùng production module.

Nếu kho vẫn đầy sau khi quay lại, module phát `InventoryFull` lần nữa và **cùng checkpoint** lại xuống bán. Không tạo Function loop mới.

Một lượt sale recovery được xem là có tiến triển nếu:

- treo được ít nhất một listing; **hoặc**
- thu được ít nhất một ô vàng, vì việc thu vàng có thể giải phóng quầy để lượt recovery kế tiếp treo VP.

Chỉ khi cả `sold_listings == 0` và `collected_gold_slots == 0` mới fail-close để tránh lặp vô hạn không tiến triển.

## Contract với Function

Function không tự viết vòng bắt lỗi. Function chỉ compose Recipe/Module.

`AutoMain` vẫn tăng `function_loops` sau khi `FunctionModule.run(...)` trả PASS. Vì checkpoint recovery không return khi module còn dang dở, scheduler không thể hợp lệ bắt đầu vòng mới trong lúc recovery.

## Mở rộng

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

## Test live bắt buộc

1. Bắt đầu một Function loop.
2. Làm kho đầy tại một production module.
3. Xác nhận log có `MODULE_INTERRUPTED` và cùng `checkpoint=...`.
4. AUTO xuống bán.
5. AUTO quay lại đúng tầng/module.
6. Xác nhận log có `MODULE_RESUMED` với cùng checkpoint.
7. Nếu kho vẫn đầy, lặp lại bước bán/resume trên cùng checkpoint.
8. Chỉ sau `MODULE_COMPLETED` và Function PASS mới được thấy `vòng N PASS` / `vòng N+1 START`.

Build/static PASS chưa phải runtime PASS.
