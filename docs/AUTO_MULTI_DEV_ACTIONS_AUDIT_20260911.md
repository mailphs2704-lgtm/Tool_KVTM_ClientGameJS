# AUTO MULTI DEV — ACTIONS AUDIT 2026-09-11

Repo: `mailphs2704-lgtm/Tool_KVTM_ClientGameJS`
Branch: `develop/multi-auto-dev`
Status: **SOURCE STANDARDIZATION IN PROGRESS — NOT RUNTIME PASS**

Mục tiêu:

```text
FUNCTION = WHAT + order
RECIPE/MODULE = compose Actions
ACTION = HOW reusable manipulation/verification
RECOVERY = typed error + checkpoint + resume/escalation
```

Không dùng build/static PASS thay cho live PASS.

## 1. CANONICAL ACTIONS

### Navigation primitive

`actions/floor_navigation.py`

Operator contract:

```text
goUp(1) = swipe một tầng
goUp(2) = click anchor pot; từ tầng 1 → candidate tầng 3
goUp(4) = long swipe; từ tầng 1 → candidate tầng 5
goUp(3) = undefined → fail-close
```

Không được triển khai `goUp(n)` bằng loop `goUp(1)`.

### Farm route composer

`actions/farm_routes.py` hiện là **canonical implementation**, không còn kế thừa implementation từ Function 1.

Canonical classes:

- `FarmRouteActions`
- `FarmBoundaryRouteActions`
- `NavigationEvidence`

Chúng sở hữu các route dùng chung như:

- MAIN → tầng 1
- tầng 1 → tầng 5
- tầng 1 → tầng 6
- MAIN → tầng 2 bằng `goUp(1) + goUp(1)`
- tầng 1 → tầng 3 bằng `goUp(2)`
- known floor → MAIN / boundary proof

`function_one_navigation.py` và `function_one_pass_three_navigation.py` chỉ còn compatibility wrapper, không được chứa route implementation mới.

### Planting

`actions/planting.py` là canonical geometry/crop manipulation.

Shared verified paths:

```text
PATH_5
PATH_6
PATH_27
PATH_28
PATH_30
```

Crop identity tách khỏi geometry. Action không quyết định floor route hay thứ tự crop.

`PATH_6` được promote từ exact geometry hàng 6 chậu tầng 6 đã tồn tại trong Apple Supply; behavior không đổi.

### Apple Supply

`actions/apple_supply.py`

- kế thừa `PlantingActions`;
- `FIVE_FLOOR_PATH = PlantingActions.PATH_30`;
- `FLOOR_6_ROW = PlantingActions.PATH_6`;
- giữ semantics READY/GROWING/wait đã có;
- không sở hữu navigation.

### Cotton

`actions/cotton_planting.py`

- `plant_27_cotton()` = crop manipulation current-view;
- `wait_harvest_and_replant_27_cotton()` = lấy một batch 27 Bông thật rồi gieo lại;
- Action không biết vì sao cần batch Bông.

`recovery/material_shortage.py` sở hữu route/reason/resume.

### VP sale transaction

`actions/vp_sale_transaction.py`

Canonical facade:

```text
VpSaleTransactionActions
```

Tên cũ `AutoMainSellingActions` chỉ là implementation lịch sử/base compatibility. Code Sale mới không phụ thuộc tên AUTO Main.

Một transaction gồm:

```text
empty slot
→ Kho 2
→ VP allowed by Function
→ proof số lượng >= 10 / exact x10
→ đăng bán
→ post-sale proof
```

Vòng 5 View không thuộc Action này.

### Sale Module

`workflows/auto_vp_sale/workflow.py`

Business order đã chốt:

```text
View 1..5
→ thu vàng
→ QC nếu có
→ tìm ô trống
→ Kho 2
→ VP Function
→ x10
→ 2 swipe sang View tiếp theo
```

View 5 là final boundary/overlap check.

### Production / Repair

`actions/production.py` sở hữu shared product-panel/slot primitives.

Gesture retry hiện bounded:

```text
DRAG_ATTEMPTS = 3
VERIFY_RECHECKS = 4
```

Product Actions:

- Táo sấy
- Nước táo
- Vải vàng
- TDHH

**TDHH/Tinh dầu hoa hồng là finished VP. Hồng và Tuyết là crop/material input.**

`actions/machine_repair.py` chỉ sở hữu transaction `? → Sửa → verify → close`, không chứa scheduler/Friend Refresh/restart policy.

## 2. DOMAIN ACTIONS — RANH GIỚI HIỆN ĐÚNG

Đã audit và hiện không thấy Scheduler/Function completion nằm trong:

- `inventory.py`
- `selling.py`
- `buying.py`
- `popup.py`
- `stall.py`
- `stall_advertising.py`
- `warehouse_full_guard.py`
- `item_recognition.py`

Các file này có thể có retry/recheck cục bộ để chứng minh thao tác UI, nhưng không được tự quyết định Function PASS, Friend Refresh hay ClientJS restart.

## 3. COMPATIBILITY-ONLY

### Function 1 navigation names

`actions/function_one_navigation.py`

```text
FunctionOneNavigationActions(FarmRouteActions)
```

`actions/function_one_pass_three_navigation.py`

```text
FunctionOnePassThreeNavigationActions(FarmBoundaryRouteActions)
```

Hai file không còn implementation thật.

### Function 2 planting

`actions/function_two_planting.py`

- compatibility facade only;
- geometry lấy từ `PlantingActions`;
- choreography authoritative nằm trong `RoseOilRecipe`;
- method choreography cũ fail rõ để tránh hai nguồn business logic.

### Planting legacy wrappers

Một số helper cũ trong `planting.py` vẫn giữ để tránh vỡ import/diagnostic. Code mới phải dùng current-view Planting + Navigation riêng.

## 4. RECOVERY-AWARE ACTION

`actions/material_shortage_production.py` được phép giữ progress nhỏ để resume side effect an toàn:

```text
queued
slot evidence
recovery_count
```

Nó không sở hữu policy:

```text
về MAIN
→ bổ sung nguyên liệu
→ quay đúng floor/machine
→ Friend Refresh
→ restart
```

Policy thuộc `recovery/`.

## 5. FUNCTION BOUNDARY DELAY — CHỐT

Thời gian chờ giữa hai Function là **minimum boundary time**, không phải sleep cố định cộng thêm sau Sale.

```text
Function PASS
→ bắt đầu boundary timer
→ Sale/Friend Refresh/maintenance nếu đến hạn
→ elapsed = thời gian maintenance đã dùng
→ chỉ sleep phần delay còn thiếu
→ Function tiếp theo
```

Nếu maintenance đã dùng >= configured delay thì Function tiếp theo bắt đầu ngay.

Áp dụng cho:

- AUTO Main
- AUTO Builder `sale_after_each_loop`

Verifier: `tools/verify_function_boundary_delay_contract.py`.

## 6. SAFETY DEBT — KHÔNG TỰ SỬA

### Production panel open

`ProductionActions._click_until_panel_open(...)` còn `while True`.

Chưa có operator-defined max time/burst. Không tự đặt timeout.

### Production idle-slot wait

`ProductionActions._wait_for_idle_open_panel(...)` còn chờ không bounded để máy chạy xong/đủ slot.

Chưa có operator-defined max wait. Không tự đặt timeout.

### TDHH thiếu Hồng/Tuyết

Hiện chưa có typed material recovery được operator mô tả/chốt. Không tự suy diễn cách bổ sung và resume.

### Emergency restart

Không bật mid-Function emergency restart cho tới khi durable checkpoint + policy được chốt.

Scheduled restart 3 giờ tại safe Function boundary là luồng riêng.

## 7. VERIFIERS

CI standardization hiện gọi:

```text
tools/verify_recovery_architecture_contract.py
tools/verify_function_boundary_delay_contract.py
tools/verify_action_standardization_contract.py
```

`verify_action_standardization_contract.py` khóa:

- PATH 5/6/27/28/30;
- Apple Supply dùng shared geometry;
- generic farm routes là canonical implementation;
- Function 1 navigation chỉ compatibility wrapper;
- VP sale dùng neutral transaction facade;
- Sale Module giữ 5 View + vàng → QC;
- Function 2 planting choreography không quay lại Actions.

## 8. TRẠNG THÁI

```text
SOURCE STANDARDIZATION IN PROGRESS
≠ STATIC PASS nếu CI chưa thực thi thành công
≠ RUNTIME PASS cho tới khi operator live test
```
