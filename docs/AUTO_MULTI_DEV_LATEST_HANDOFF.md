# AUTO MULTI DEV — LATEST HANDOFF

Cập nhật: 2026-09-09

Tài liệu này là mốc đọc đầu tiên cho branch `develop/multi-auto-dev`.

## Trạng thái

- Function 1 baseline: operator đã PASS nhiều vòng trước Recipe refactor.
- QC quầy: LIVE PASS.
- Recovery/Event/Error refactor: operator PASS.
- Recipe refactor: source đã hoàn tất, cần `[1]` + live smoke để chốt PASS.
- Runtime: isolated worker + Bridge V3.
- Dọn quầy / Sale / QC là vùng ổn định, không thay đổi trong refactor Recipe.
- Settings chính ở `%APPDATA%\KVTM Multi DEV`; rebuild không overwrite saved operator values.

## Kiến trúc chuẩn mới

Luồng source:

`Function → RecipeBook → Product Recipe → Atomic Action + RecoveryManager`

`errors.py` chỉ chứa typed signal.

### Recovery

Package:

`components/clientjs-auto/kvtm_automation/recovery/`

Chứa:

- `events.py` — typed recovery event;
- `navigation.py` — unknown/main/floor routes;
- `production.py` — WrongProductionMachine + InventoryFull;
- `manager.py` — facade dùng chung.

Generic `ScreenTimeout` không được retry mù.

### Recipes

Package:

`components/clientjs-auto/kvtm_automation/recipes/`

Chứa:

- `dried_apple.py`;
- `apple_juice.py`;
- `yellow_fabric.py`;
- `book.py`.

Mỗi `RecipeBook(function_id=...)` dùng một shared `RecoveryManager` cho toàn Function.

Chi tiết:

`docs/AUTO_MULTI_DEV_RECIPE_ARCHITECTURE.md`

## Function 1 sau Recipe refactor

Function 1 hiện chỉ ghép nghiệp vụ:

1. `DriedAppleRecipe.run_from_session(count=9)`;
2. supply Táo riêng của Function 1 qua 5 tầng + tầng 6;
3. tạo candidate floor2 bằng `goDown(4)`;
4. `AppleJuiceRecipe.run_from_candidate_floor_2(count=9)`;
5. `YellowFabricRecipe.run_after_floor_2(count=9)`;
6. RecoveryManager normalize tầng 3 → exact-main;
7. PASS 3/3.

Function 1 không còn gọi trực tiếp:

- `produce_9_apple_juices()`;
- `produce_9_yellow_fabrics()`;
- Sửa máy cho Nước táo/Vải vàng;
- WrongProductionMachine loop;
- InventoryFull loop.

## AppleJuiceRecipe độc lập

Có thể gọi riêng từ main:

```python
recipes.apple_juice.run_from_main(count=9)
```

Nó không phụ thuộc Vải vàng.

Entry khác:

- `run_current_floor_2(count=9)`;
- `run_from_candidate_floor_2(count=9)`.

Candidate floor2 không được tin từ movement; Recipe vẫn bounded probe `nuoc_tao`. MISS → RecoveryManager unknown → exact-main → floor2.

## YellowFabricRecipe

Khi Nước táo đã có và đang known floor2:

```python
recipes.yellow_fabric.run_after_floor_2(count=9)
```

Chuỗi:

`floor2 → main → trồng 27 Bông → known floor1 → floor3 → vai_vang proof → SX9 → Sửa máy`

Standalone có dependency Nước táo:

```python
recipes.yellow_fabric.run_from_main(
    count=9,
    include_apple_juice_dependency=True,
)
```

Dependency là explicit. `False` không được tự sản xuất Nước táo.

## Route Vải vàng đã live correction

- `(257,416)` chỉ tới tầng 2.
- route floor1 → floor3 dùng click chậu tầng 4 `(257,191)`.
- production vẫn phải thấy `vai_vang`; movement không tự chứng minh đúng tầng.

## Wrong-machine recovery

Shared production quét known anchors:

- `tao_say`;
- `nuoc_tao`;
- `vai_vang`.

Ví dụ cần `vai_vang` nhưng thấy `nuoc_tao`:

`close panel → WrongProductionMachine → unknown-camera recovery → exact-main → floor3 → retry`

Tối đa 3 wrong-machine recovery.

Wrong-machine không sale VP.

## InventoryFull recovery

`known floor → exact-main → Function-bound VP sale → same requested floor → retry production`

Nếu sale không treo được listing nào thì fail-close.

## Shared production order

Bắt buộc:

`x5 raw click → vp_collect_delay → fresh frame → panel_state(frame) → target/wrong-machine scan`

Không được:

- sleep/capture/check giữa x5;
- dùng `o_trong` để chứng minh đúng machine;
- click vô hạn khi panel mở sai machine.

## Exact-main

Không phụ thuộc background account.

- fixed own-farm HUD;
- runtime navigation proof;
- unknown camera → bounded goDown;
- boundary fallback = 2 low-change frame liên tiếp, threshold 6.0;
- upper floor dùng visual `XUỐNG` detector và click `match.center`;
- không blind click `(497,978)`;
- chain upper-floor tối đa 10 bước.

## QC quầy — LIVE PASS

Ba checkpoint gần physical slot `1 / 10 / 20`:

- đã QC đỏ → skip không click;
- chưa QC → mở listing;
- nút xanh miễn phí hồi → đặt QC;
- cooldown → đóng X;
- không click nút kim cương;
- quầy full vẫn đi hết checkpoint;
- QC error non-blocking.

## Count contract Recipe

Public Recipe API có `count`, nhưng action hiện prove batch 9.

- `count=9`: hỗ trợ;
- khác 9: fail-close;
- chưa giả vờ hỗ trợ dynamic count.

## Static contracts

Build `[1]` đang chạy `tools/verify_auto_main_production_contract.py`; verifier này đã khóa cả Recipe + Recovery architecture.

Contract chuyên biệt cũng có:

- `tools/verify_recipe_architecture_contract.py`;
- `tools/verify_recovery_architecture_contract.py`.

Production gate kỳ vọng marker mới:

```text
AUTO MULTI DEV FUNCTION ONE STATIC CONTRACT VERIFIED
architecture=function-business+recipes-reusable+actions-atomic+recovery-centralized
recipe_book=shared-recovery-per-function
recipe_dried_apple=plant-apples+produce9+repair
recipe_apple_juice=standalone-main-or-candidate-floor2+proof+recover+produce9+repair
recipe_yellow_fabric=optional-apple-juice-dependency+cotton27+floor3+produce9+repair
```

## Build flow

Operator:

`KVTM_DEV_CONTROL.bat → [1] Cap nhat source + build runtime DEV`

Sau static/build PASS mới live smoke Function 1.

## Không được regression

- Function copy production/recovery đã nằm trong Recipe/RecoveryManager.
- AppleJuiceRecipe phụ thuộc Vải vàng.
- YellowFabricRecipe luôn sản xuất Nước táo khi flag=false.
- Function giả định sau trồng Bông là main.
- dùng `(257,416)` cho Vải vàng.
- panel sai machine vẫn x5 vô hạn.
- generic ScreenTimeout blind retry.
- background làm exact-main gate.
- blind click XUỐNG.
- thay đổi Sale/QC/Dọn quầy khi không có regression evidence.

## Read-first

1. `docs/AUTO_MULTI_DEV_LATEST_HANDOFF.md`
2. `docs/AUTO_MULTI_DEV_RECIPE_ARCHITECTURE.md`
3. `docs/AUTO_MULTI_DEV_RECOVERY_ARCHITECTURE.md`
4. `docs/AUTO_MULTI_DEV_FUNCTION_ONE.md`
5. `components/clientjs-auto/kvtm_automation/recipes/book.py`
6. `components/clientjs-auto/kvtm_automation/recipes/apple_juice.py`
7. `components/clientjs-auto/kvtm_automation/recipes/yellow_fabric.py`
8. `components/clientjs-auto/kvtm_automation/recovery/manager.py`
9. `components/clientjs-auto/kvtm_automation/recovery/production.py`
10. `components/clientjs-auto/kvtm_automation/workflows/auto_function_one/workflow.py`
11. `tools/verify_auto_main_production_contract.py`
12. `tools/verify_recipe_architecture_contract.py`
