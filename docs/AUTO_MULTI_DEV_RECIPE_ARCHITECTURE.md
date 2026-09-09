# AUTO MULTI DEV — Recipe Architecture

Cập nhật: 2026-09-09

## Mục tiêu

Tách business sản xuất thành bốn lớp độc lập để Function mới không phải copy logic đã PASS:

`Function → Recipe → Action → Recovery`

`errors.py` chỉ phát signal; không chứa thuật toán xử lý.

## Trách nhiệm từng lớp

### Function

Chỉ quyết định:

- cần sản phẩm nào;
- thứ tự Recipe;
- supply choreography thật sự riêng của Function;
- điều kiện PASS của Function.

Function không được tự lặp lại:

- production transaction;
- Sửa máy;
- WrongProductionMachine recovery;
- InventoryFull recovery;
- unknown-camera → exact-main;
- các loop retry navigation chung.

### Recipe

Một Recipe là một bộ nghiệp vụ sản xuất reusable của một VP.

Hiện có:

- `DriedAppleRecipe`;
- `AppleJuiceRecipe`;
- `YellowFabricRecipe`.

Recipe được phép ghép Action + Recovery và gọi Recipe khác như dependency có khai báo rõ.

### Action

Action chỉ làm thao tác nguyên tử, ví dụ:

- trồng 27 cây;
- mở/xác minh một máy;
- x5 thu VP;
- kéo một sản phẩm vào slot;
- Sửa máy;
- primitive chuyển tầng.

Action không quyết định business recovery toàn Function.

### Recovery

`RecoveryManager` là facade chung cho Recipe/Function:

- exact-main;
- unknown camera;
- known floor → main;
- main → floor;
- known floor → known floor;
- WrongProductionMachine;
- InventoryFull + sale VP + quay lại đúng tầng.

Generic `ScreenTimeout` không được recover mù.

## RecipeBook

Mỗi Function tạo một `RecipeBook(function_id=...)`.

Tất cả Recipe trong cùng book chia sẻ đúng một `RecoveryManager`, vì vậy:

- sale recovery vẫn dùng đúng catalog của Function;
- event hook dùng chung;
- route injection dùng chung;
- không có nhiều recovery policy lệch nhau trong cùng một Function.

API hiện tại:

```python
self.recipes.dried_apple
self.recipes.apple_juice
self.recipes.yellow_fabric
```

## DriedAppleRecipe

Entry:

- `run_from_session(count=9)` — tương thích startup hiện tại;
- `run_from_main(count=9)` — cho Function tương lai đã có exact-main.

Nghiệp vụ:

`trồng 27 Táo → SX 9 Táo sấy → Sửa máy`

Kho đầy/sai máy đi qua RecoveryManager.

## AppleJuiceRecipe — chạy độc lập

Apple Juice không phụ thuộc Vải vàng.

Entry:

- `run_from_main(count=9)`;
- `run_current_floor_2(count=9)`;
- `run_from_candidate_floor_2(count=9)`.

`run_from_candidate_floor_2()` dùng cho route tối ưu Function 1:

`floor6 → goDown(4) → candidate floor2`

Recipe tự làm:

1. bounded probe `nuoc_tao`;
2. PASS → production;
3. MISS → RecoveryManager unknown → exact-main → floor2;
4. production 9/9;
5. Sửa máy;
6. WrongProductionMachine / InventoryFull dùng central recovery.

Do đó một Function chỉ muốn Nước táo có thể gọi trực tiếp:

```python
juice = recipes.apple_juice.run_from_main(count=9)
```

Nó không gọi Vải vàng.

## YellowFabricRecipe

Có hai kiểu dùng.

### Vải vàng khi Nước táo đã có

Function 1 dùng:

```python
fabric = recipes.yellow_fabric.run_after_floor_2(count=9)
```

Entry này biết Nước táo vừa hoàn tất và camera đang ở known floor 2.

Chuỗi:

`floor2 → exact-main → trồng 27 Bông → known floor1 → floor3 → verify vai_vang → SX 9 → Sửa máy`

### Vải vàng standalone có dependency Nước táo

Một Function tương lai có thể gọi:

```python
fabric = recipes.yellow_fabric.run_from_main(
    count=9,
    include_apple_juice_dependency=True,
)
```

Chuỗi:

`main → AppleJuiceRecipe → floor2 → main → Bông → floor3 → Vải vàng`

Dependency là explicit, không bị gọi ngầm khi flag=false.

Lưu ý: Recipe hiện điều phối production chain đã biết; nó chưa phải inventory planner tổng quát. `include_apple_juice_dependency=True` yêu cầu nguyên liệu đầu vào Nước táo phù hợp đã sẵn sàng theo business Function gọi nó.

## Tại sao có nhiều entry state

Không được ép mọi Recipe về main nếu caller đang có một state tốt và đã biết.

Ví dụ:

- sau trồng Bông camera là known floor 1, không phải main;
- sau direct goDown(4) chỉ là candidate floor 2;
- sau Nước táo là known floor 2;
- startup session có contract riêng.

Vì vậy Recipe phải khai báo entry rõ thay vì giả định camera.

## Function 1 sau refactor

Function 1 hiện chỉ còn:

1. `DriedAppleRecipe`;
2. supply Táo riêng của Function 1 qua tầng 1-6;
3. tạo candidate floor2 bằng `goDown(4)`;
4. `AppleJuiceRecipe`;
5. `YellowFabricRecipe`;
6. normalize end-loop main;
7. PASS 3/3.

Function 1 không còn trực tiếp gọi production Nước táo/Vải vàng, Sửa máy hoặc recovery production.

## Quy tắc mở rộng Function mới

Nếu Function mới chỉ cần Nước táo:

```python
recipes.apple_juice.run_from_main(count=9)
```

Nếu cần Vải vàng và Nước táo đã có:

```python
recipes.yellow_fabric.run_from_main(
    count=9,
    include_apple_juice_dependency=False,
)
```

Nếu cần full chain Vải vàng có Nước táo:

```python
recipes.yellow_fabric.run_from_main(
    count=9,
    include_apple_juice_dependency=True,
)
```

Nếu Function cần tầng mới, inject route vào `RecoveryManager`; không copy recovery loop vào Recipe.

## Count contract hiện tại

Ba production action hiện vẫn khóa machine batch `9` nên Recipe public API nhận `count` nhưng fail-close nếu khác `9`.

Đây là chủ ý: interface đã chuẩn hóa trước, nhưng chưa giả vờ hỗ trợ count động khi action bên dưới chưa chứng minh được.

## Build/static contract

- `tools/verify_auto_main_production_contract.py` khóa Recipe layer cùng production/recovery contract.
- `tools/verify_recipe_architecture_contract.py` là contract chuyên biệt cho tính độc lập/dependency của Recipe.
- `tools/verify_recovery_architecture_contract.py` khóa boundary giữa error/recovery/recipe/function.

Các regression bị cấm:

- AppleJuiceRecipe phụ thuộc YellowFabricRecipe;
- Function 1 gọi thẳng `produce_9_apple_juices` hoặc `produce_9_yellow_fabrics`;
- Function 1 gọi Sửa máy cho VP đã được Recipe sở hữu;
- Recipe copy loop unknown-camera thay vì gọi RecoveryManager;
- YellowFabricRecipe luôn ép sản xuất Nước táo dù dependency flag=false;
- giả định trạng thái sau trồng Bông vẫn là exact-main;
- generic ScreenTimeout bị retry mù.
