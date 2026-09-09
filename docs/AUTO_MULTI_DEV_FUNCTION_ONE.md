# AUTO MULTI DEV — Chức năng 1

Cập nhật: 2026-09-09

## Trạng thái

- Function 1 baseline trước refactor Recipe: **operator PASS nhiều vòng**.
- QC quầy: **LIVE PASS**.
- Recovery/Event/Error refactor: **operator PASS**.
- Recipe refactor hiện đã cập nhật source; cần build `[1]` + live smoke để chốt PASS mới.
- Sale/QC/Dọn quầy là vùng ổn định, không thay đổi trong Recipe refactor.

## Kiến trúc hiện tại

Function 1 không còn tự chứa chi tiết production/recovery cho từng VP.

Luồng lớp:

`FunctionOneWorkflow → RecipeBook → Product Recipe → Atomic Action + RecoveryManager`

Chi tiết kiến trúc Recipe xem:

`docs/AUTO_MULTI_DEV_RECIPE_ARCHITECTURE.md`

Recovery chung xem:

`docs/AUTO_MULTI_DEV_RECOVERY_ARCHITECTURE.md`

## Recipe được Function 1 dùng

### DriedAppleRecipe

Function gọi:

```python
self.recipes.dried_apple.run_from_session(count=9)
```

Recipe sở hữu:

`trồng 27 Táo → SX 9 Táo sấy → Sửa máy`

Function không gọi trực tiếp production/Sửa máy cho Táo sấy.

### AppleJuiceRecipe

Sau supply Táo tầng 1-6, Function chỉ tạo candidate tầng 2:

`floor6 → goDown(4) → candidate floor2`

Sau đó gọi:

```python
self.recipes.apple_juice.run_from_candidate_floor_2(count=9)
```

Recipe sở hữu:

1. bounded probe `nuoc_tao`;
2. candidate PASS → production;
3. candidate MISS → RecoveryManager unknown → exact-main → floor2;
4. WrongProductionMachine recovery;
5. InventoryFull recovery;
6. SX 9/9 Nước táo;
7. Sửa máy.

AppleJuiceRecipe độc lập, không phụ thuộc Vải vàng. Function khác có thể gọi:

```python
self.recipes.apple_juice.run_from_main(count=9)
```

để chỉ sản xuất Nước táo.

### YellowFabricRecipe

Function 1 đã có Nước táo và đang ở known floor 2 nên gọi:

```python
self.recipes.yellow_fabric.run_after_floor_2(count=9)
```

Recipe sở hữu:

`floor2 → exact-main → trồng 27 Bông → known floor1 → floor3 → verify vai_vang → SX 9 → Sửa máy`

Route floor1 → floor3 vẫn dùng điểm chậu tầng 4 `(257,191)`; `(257,416)` đã live chứng minh chỉ tới tầng 2.

YellowFabricRecipe cũng có entry standalone:

```python
self.recipes.yellow_fabric.run_from_main(
    count=9,
    include_apple_juice_dependency=True,
)
```

Khi flag=true, Recipe gọi AppleJuiceRecipe trước. Khi false, tuyệt đối không tự sản xuất Nước táo.

## Chuỗi Function 1 sau refactor

1. scheduler đã chuẩn hóa account;
2. sale VP + QC theo Function 1;
3. `DriedAppleRecipe`;
4. chờ Táo chín / thu / gieo lại 5 tầng;
5. lên tầng 6 và xử lý hàng Táo cuối;
6. Function tạo candidate floor2 bằng `goDown(4)`;
7. `AppleJuiceRecipe` xác minh + sản xuất + sửa máy;
8. `YellowFabricRecipe` về main + Bông + tầng 3 + Vải vàng + sửa máy;
9. Function normalize tầng 3 → exact-main qua RecoveryManager;
10. PASS 3/3.

Function-specific logic còn lại chủ yếu là supply Táo tầng 1-6 và thứ tự Recipe.

## Điều kiện PASS Function 1

Kết quả vẫn giữ contract:

- `progress_steps=3`;
- `total_steps=3`;
- 9 Táo sấy;
- 9 Nước táo;
- 27 Bông;
- 9 Vải vàng;
- cuối vòng exact-main PASS.

## Shared production contract

Táo sấy / Nước táo / Vải vàng vẫn dùng shared production transaction:

`x5 raw click → vp_collect_delay → fresh frame → panel_state(frame) → target/wrong-machine scan`

Bắt buộc:

- không sleep/capture/check giữa 5 raw click;
- target VP mới chứng minh đúng panel;
- `o_trong` chỉ diagnostic;
- panel mở thấy VP máy khác → đóng ngay + `WrongProductionMachine`;
- generic `ScreenTimeout` không bị recovery mù;
- mỗi drag sản xuất phải hậu kiểm slot giảm;
- Recipe giữ panel mở để Sửa máy rồi mới hoàn thành.

## WrongProductionMachine

Ví dụ cần `vai_vang` nhưng thấy `nuoc_tao`:

`close panel → WrongProductionMachine → RecoveryManager unknown-camera → exact-main → requested floor → retry production`

Giới hạn recovery hiện tại: 3 lần.

Không bán VP trong wrong-machine recovery.

## InventoryFull

Kho đầy là signal riêng:

`known floor → exact-main → sale VP Function-bound → requested floor → retry production`

Nếu sale không treo được listing nào, fail-close để tránh vòng vô hạn.

## Exact-main / navigation

Không dùng background farm làm exact-main gate.

- own farm: fixed HUD;
- exact-main: runtime navigation proof;
- unknown camera: bounded goDown;
- main boundary: 2 low-change liên tiếp, threshold `6.0`;
- upper floor: nhận diện nút `XUỐNG`, click `match.center`;
- không blind click `(497,978)`;
- recovery chain upper-floor tối đa 10 bước.

## Route Bông → Vải vàng

Đã live correction:

- `(257,416)` → chỉ tới tầng 2;
- `(257,191)` → click chậu tầng 4 để tới candidate tầng 3.

Recipe Vải vàng hiện gọi shared known-floor route:

`known floor1 → floor3`

và production tiếp tục chứng minh bằng `vai_vang`.

## QC quầy — LIVE PASS

Mỗi sale có checkpoint gần physical slot `1 / 10 / 20`:

- đã có QC đỏ → skip, không click;
- chưa QC → mở listing;
- nút xanh miễn phí hồi → đặt QC;
- cooldown → đóng X;
- không click QC kim cương;
- quầy full vẫn đi hết checkpoint;
- lỗi QC non-blocking.

Recipe refactor không thay đổi phần này.

## Count contract Recipe

API Recipe nhận `count`, nhưng production action hiện chỉ prove batch 9.

Do đó:

- `count=9` → hỗ trợ;
- count khác 9 → fail-close bằng `ValueError`;
- chưa giả vờ hỗ trợ count động khi action chưa được chứng minh.

## Static contracts

Các gate liên quan:

- `tools/verify_auto_main_production_contract.py`
- `tools/verify_recipe_architecture_contract.py`
- `tools/verify_recovery_architecture_contract.py`
- `tools/verify_auto_speed_config_contract.py`
- `tools/verify_multi_dev_main_boundary_contract.py`
- `tools/verify_auto_vp_advertising_contract.py`

Production gate hiện khóa:

- RecipeBook dùng shared RecoveryManager;
- AppleJuiceRecipe độc lập;
- YellowFabricRecipe dependency Nước táo là optional;
- Function 1 không gọi thẳng production Nước táo/Vải vàng;
- Function 1 không gọi thẳng Sửa máy cho các VP đã thuộc Recipe;
- Function 1 không copy production recovery loop.

## Regression bị cấm

- Function 1 quay lại tự gọi `produce_9_apple_juices()`;
- Function 1 quay lại tự gọi `produce_9_yellow_fabrics()`;
- Function 1 copy WrongProductionMachine/InventoryFull loop;
- AppleJuiceRecipe phụ thuộc YellowFabricRecipe;
- YellowFabricRecipe luôn sản xuất Nước táo dù dependency flag=false;
- giả định sau trồng Bông vẫn là main;
- dùng `(257,416)` cho route Vải vàng;
- panel sai máy vẫn x5 vô hạn;
- background làm exact-main gate;
- blind click nút XUỐNG;
- generic ScreenTimeout blind retry;
- thay đổi Sale/QC/Dọn quầy khi không có regression evidence.
