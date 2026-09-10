# AUTO MULTI DEV — FUNCTION 2

Cập nhật: 2026-09-10

## Phạm vi

Function 2 là nhánh AUTO MULTI DEV dành riêng cho ClientJS native `1000x1000`.
Nhánh `500x500` của Function 1 và bảng sale 500 hiện tại phải giữ nguyên.

Operator label:

```text
9 Táo sấy - 9 Vải vàng - 7 tinh dầu hoa hồng
```

Runtime contract đầy đủ của một vòng:

```text
Function 1 base
  9 Táo sấy
  9 Nước táo
  27 Bông
  9 Vải vàng

Function 2 extra
  35 Hoa hồng
  28 Cây tuyết
  7 Tinh dầu hoa hồng

Completion
  progress_steps=4
  total_steps=4
  exact-main trước PASS
```

## Kiến trúc

Luồng chuẩn:

```text
FunctionTwoWorkflow
  -> RecipeBook(function_2)
     -> shared RecoveryManager(function_2)
     -> DriedAppleRecipe
     -> AppleJuiceRecipe
     -> YellowFabricRecipe
     -> RoseOilRecipe
        -> FunctionTwoPlantingActions
        -> RoseOilProductionActions
```

`RecipeBook(function_2)` dùng RecoveryManager của `RoseOilRecipe` làm manager chung vì
manager này chứa route bổ sung `7 -> 5`, `main -> 5` và `5 -> main`. Sau đó cùng manager
được inject vào chuỗi Function 1 base. Vì vậy warehouse-full recovery và sale recovery
trong toàn bộ Function 2 luôn dùng metadata/sale policy của `function_2`.

Function 1 standalone vẫn tự tạo `RecipeBook(function_1)` như trước. Chỉ khi Function 2
gọi base workflow thì RecipeBook Function 2 mới được inject vào.

## Planting Function 2

Khóa native:

```text
capture phải đúng 1000x1000
khác 1000x1000 -> ScreenTimeout trước choreography Function 2
```

Material layout:

```text
Hồng tầng 1-5: 30
Hồng tầng 6:    5
Tổng Hồng:     35

Tuyết tầng 7-10: 24
Tuyết tầng 11:     4
Tổng Tuyết:       28
```

RIPE harvest dùng farm path đã khôi phục từ AUTO PRO. Seed drag bắt đầu từ tâm template
hạt đã xác minh rồi mới đi qua pot path. Không dùng template RIPE center làm điểm bắt đầu
harvest.

## TDHH production

Target machine:

```text
floor=5
item=tinh_dau_hh
target=7
```

Mỗi drag phải làm giảm số ô trống. Thiếu Hồng/Tuyết hoặc slot delta không thay đổi sau
retry đều fail-close. Sau 7 drag phải chứng minh delta đúng 7. Panel được giữ mở để bàn
giao `MachineRepairActions`, sau đó RecoveryManager đưa tầng 5 về exact-main.

## Sale Function 2

Allowed VP:

```text
tao_say
vai_vang
tinh_dau_hh
```

Sale Function 2 kiểm tra native `1000x1000` trước mọi thao tác quầy/kho. Recognition scan
nhận explicit `ITEM_ORDER`. TDHH chỉ được đặt bán khi selected-item template và exact-x10
proof đều PASS.

Bảng native 500 của Function 1 vẫn khóa:

```text
N500_EXACT_TEN_THRESHOLD = 0.78
N500_EXACT_TEN_SCALES = (0.75, 0.90, 1.00, 1.10, 1.25, 1.40, 1.55)
```

## Static gate

Verifier riêng:

```text
tools/verify_auto_function_two_contract.py
```

`tools/verify_auto_builder_contract.py` là composite wrapper:

```text
stable Builder core
-> Function 2 static contract
```

Implementation Builder verifier trước mốc này được giữ nguyên byte-for-byte tại:

```text
tools/verify_auto_builder_contract_core.py
```

Vì sale verifier/build hiện đã gọi `verify_auto_builder_contract.main()`, Function 2 trở
thành static build gate mà không cần sửa packaging PowerShell dùng chung.

## PASS discipline

Hiện chỉ được gọi là source/static-ready sau khi verifier/build thực sự PASS.
Không gọi Function 2 runtime PASS trước live evidence.

Live test tiếp theo phải theo thứ tự:

1. Control Center `[1] Cap nhat source + build runtime DEV`.
2. Xác nhận static/build PASS.
3. Chọn đúng một profile ClientJS native `1000x1000`.
4. Chạy Function 2 có kiểm soát, không chạy đồng loạt 28 profile.
5. Đối chiếu log từng boundary: base 3/4, material 35/28, TDHH 7/7, sửa máy,
   exact-main, completion 4/4, sale TDHH nếu đủ x10.
6. Chỉ sau operator-confirmed behavior + matching logs mới ghi LIVE PASS.
