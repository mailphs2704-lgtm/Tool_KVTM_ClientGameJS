# AUTO MULTI DEV — Recovery architecture

Cập nhật: 2026-09-09

## Mục tiêu

Function/Recipe chỉ mô tả nghiệp vụ: trồng gì, sản xuất gì, thứ tự nào. Logic sai tầng, sai máy, camera không rõ, kho đầy và quay lại vị trí phải dùng chung một recovery layer; không copy lại recovery loop vào từng Function.

## Cấu trúc chuẩn

```text
kvtm_automation/
├─ errors.py
├─ recovery/
│  ├─ __init__.py
│  ├─ events.py
│  ├─ navigation.py
│  ├─ production.py
│  └─ manager.py
├─ actions/
│  ├─ planting.py
│  ├─ apple_juice_production.py
│  ├─ yellow_fabric_production.py
│  └─ ...
└─ workflows/
   ├─ auto_function_one/
   └─ ...
```

### `errors.py`

Chỉ khai báo signal/error type, không được điều hướng hoặc retry:

- `WrongProductionMachine`
- `InventoryFull`
- `ScreenTimeout`
- các signal khác.

### `recovery/events.py`

Khai báo event typed để Function/Recipe có thể gắn hook quan sát tại đúng vị trí mà không copy recovery policy:

- `UNKNOWN_CAMERA`
- `WRONG_PRODUCTION_MACHINE`
- `INVENTORY_FULL`
- `MAIN_PROVEN`
- `FLOOR_REENTERED`
- `RECOVERY_EXHAUSTED`.

Hook là non-blocking observer. Lỗi trong hook không được làm hỏng recovery chuẩn.

### `recovery/navigation.py`

`NavigationRecovery` sở hữu các nguyên tắc điều hướng phục hồi:

- unknown camera → bounded `goDown(1)` / nút `XUỐNG` / main-boundary → exact-main;
- known floor → main;
- main → requested floor;
- known floor → known floor;
- floor mới có thể inject route qua `to_main_routes`, `from_main_routes`, `between_floor_routes`.

Default hiện hỗ trợ floor 1/2/3 và route floor1→floor3 đang dùng điểm chậu tầng 4 đã live-prove.

### `recovery/production.py`

`ProductionRecovery` chỉ bắt hai signal recoverable hiện tại:

- `WrongProductionMachine`: không bán VP, không tin floor dự kiến; unknown-camera → exact-main → quay lại requested floor → retry production;
- `InventoryFull`: known floor → exact-main → bán VP của Function → quay lại cùng floor → retry production.

Không bắt generic `ScreenTimeout`. Một production gesture có thể đã tạo side effect nên generic lỗi hình ảnh phải fail-close thay vì replay mù.

### `recovery/manager.py`

`RecoveryManager` là facade duy nhất Function/Recipe mới nên gọi.

API chính:

```python
recovery.ensure_main(label)
recovery.recover_unknown_to_main(label, reason=...)
recovery.recover_unknown_to_floor(floor, label, reason=...)
recovery.to_main_from_floor(floor, label)
recovery.from_main_to_floor(floor, label)
recovery.from_floor_to_floor(source_floor, target_floor, label)
recovery.run_production(floor=..., label=..., producer=...)
```

## Chèn xử lý riêng cho Function mới

Function có thể gắn observer cho một event mà không thay thuật toán recovery:

```python
from kvtm_automation.recovery import RecoveryEventKind, RecoveryManager

recovery = RecoveryManager(
    automation,
    function_id="function_2",
    event_handlers={
        RecoveryEventKind.WRONG_PRODUCTION_MACHINE: on_wrong_machine,
        RecoveryEventKind.INVENTORY_FULL: on_inventory_full,
    },
)
```

Nếu Function dùng floor mới, inject route thay vì viết recovery loop trong Function:

```python
recovery = RecoveryManager(
    automation,
    function_id="function_2",
    from_main_routes={4: go_main_to_floor_4},
    to_main_routes={4: go_floor_4_to_main},
    between_floor_routes={(2, 4): go_floor_2_to_floor_4},
)
```

Core vẫn chịu trách nhiệm exact-main, retry bound và signal policy.

## Function 1 sau chuẩn hóa

Function 1 không còn chứa loop `go_down_one_toward_main()` để tự sửa camera. Các điểm recovery hiện chỉ gọi facade:

```text
direct Nước táo miss
→ recovery.recover_unknown_to_floor(2, ...)

SX Nước táo / Vải vàng
→ recovery.run_production(...)

sau Nước táo
→ recovery.to_main_from_floor(2, ...)

sau trồng Bông
→ recovery.from_floor_to_floor(1, 3, ...)

cuối vòng Vải vàng
→ recovery.to_main_from_floor(3, ...)
```

`ProductionWarehouseRecovery` cũ vẫn tồn tại để workflow cũ không gãy import, nhưng chỉ là compatibility facade gọi `RecoveryManager`; không còn sở hữu policy.

## Quan hệ với Actions / Recipes / Functions

Kiến trúc mục tiêu:

```text
FUNCTION
  chọn mục tiêu và thứ tự sản phẩm
       ↓
RECIPE
  mô tả dependency của một sản phẩm
       ↓
ACTION
  thao tác nguyên tử: trồng / mở máy / kéo VP
       ↓
RECOVERY
  xử lý trạng thái lỗi dùng chung
```

Recovery layer đã được tách trước để các Recipe tiếp theo có thể dùng ngay. Khi chuẩn hóa Recipe Nước táo/Vải vàng, Recipe chỉ gọi `RecoveryManager`, không được tự chép logic sai tầng/kho đầy.

## Build contract

- `tools/verify_recovery_architecture_contract.py`
- `tools/verify_auto_main_production_contract.py`

Các contract phải giữ:

- `errors.py = signals-only`;
- Function không chứa `go_down_one_toward_main()` recovery loop;
- generic `ScreenTimeout` không bị ProductionRecovery nuốt;
- wrong-machine và InventoryFull policy chỉ tồn tại trong `recovery/`;
- future Function có extension point qua event hooks và route maps;
- QC sale và Dọn quầy không bị chạm bởi refactor này.
