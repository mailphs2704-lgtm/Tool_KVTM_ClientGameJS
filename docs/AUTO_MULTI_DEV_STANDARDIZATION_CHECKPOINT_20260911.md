# AUTO MULTI DEV — STANDARDIZATION CHECKPOINT 2026-09-11

Repo: `mailphs2704-lgtm/Tool_KVTM_ClientGameJS`
Branch bắt buộc: `develop/multi-auto-dev`
Trạng thái: **SOURCE STANDARDIZATION IN PROGRESS — NOT STATIC PASS — NOT RUNTIME PASS**

Tài liệu này là checkpoint chống mất ngữ cảnh. Nếu tài liệu cũ mâu thuẫn, ưu tiên contract operator và checkpoint này.

## 1. Kiến trúc hiện hành

```text
AUTO MAIN / SCHEDULER
        ↓
FUNCTION
        ↓
MODULE / RECIPE
        ↓
ACTION

        ↕
GLOBAL RECOVERY / ERROR MANAGER
        ↕
ACTIVE CHECKPOINT (metadata-only)
```

```text
Recovery != Function PASS
Recovery = interrupt → recover → resume same work
```

- Function: WHAT + thứ tự nghiệp vụ.
- Module/Recipe: ghép Action.
- Action: HOW thao tác/xác minh tái sử dụng.
- Recovery: typed error + checkpoint + resume/escalation.
- Worker: lifecycle host, không phải recovery engine thứ hai.

## 2. Startup — CHỐT, SOURCE IMPLEMENTED

```text
login/restart
→ camera mặc định MAIN
→ bắt đầu popup watch 60s
→ popup xuất hiện thì đóng ngay
→ tiếp tục scan đủ 60s
→ bàn giao MAIN
```

Không dùng `goDown(1)` để tự tạo exact-main sau login/restart.

## 3. Sale — CHỐT, SOURCE IMPLEMENTED

Mỗi View:

```text
thu vàng
→ QC nếu có
→ tìm ô trống
→ Kho 2
→ VP allowed theo Function
→ chứng minh đủ x10
→ đăng bán
```

- chuyển View = `stall.next_view()` = đúng 2 swipe;
- tổng 5 View;
- View 5 = final boundary/overlap check;
- one-listing transaction canonical facade = `VpSaleTransactionActions`;
- `AutoMainSellingActions` chỉ còn tên/base lịch sử.

## 4. Function boundary delay — CHỐT, SOURCE IMPLEMENTED

Delay giữa hai Function là **minimum boundary time**, không phải sleep cố định sau Sale.

```text
Function PASS
→ start boundary timer
→ Sale/Friend Refresh/maintenance nếu đến hạn
→ elapsed maintenance được tính vào delay
→ chỉ sleep phần còn thiếu
→ next Function
```

Ví dụ delay=60s:

```text
Sale 25s → sleep thêm 35s
Sale 65s → sleep 0s
```

Áp dụng AUTO Main và AUTO Builder `sale_after_each_loop`.

## 5. Navigation — CHỐT

`goUp(n)` là action mode, không phải N lần swipe.

```text
goUp(1) = short swipe (514,214) → (514,314)
goUp(2) = click anchor (257,191); floor1 → candidate floor3
goUp(4) = long swipe (387,69) → (387,918); floor1 → candidate floor5
goUp(3) = undefined → fail-close
```

Canonical primitive: `FloorNavigationActions`.

### Generic route ownership

`actions/farm_routes.py` là canonical implementation:

- `FarmRouteActions`
- `FarmBoundaryRouteActions`
- `NavigationEvidence`

`function_one_navigation.py` và `function_one_pass_three_navigation.py` chỉ là compatibility wrappers; không còn route implementation riêng.

## 6. Planting — SHARED ACTIONS

`PlantingActions` sở hữu verified paths:

```text
PATH_5
PATH_6
PATH_27
PATH_28
PATH_30
```

Crop identity tách khỏi geometry.

Apple Supply:

```text
FIVE_FLOOR_PATH = PlantingActions.PATH_30
FLOOR_6_ROW      = PlantingActions.PATH_6
```

Apple Supply giữ crop READY/GROWING semantics, không sở hữu navigation.

Cotton Action cung cấp current-view planting và neutral batch replenishment; Recovery quyết định vì sao cần batch Bông.

## 7. TDHH — CHỐT PHÂN LOẠI + RECIPE BOUNDARY

- Hồng = crop/material.
- Tuyết = crop/material.
- **TDHH/Tinh dầu hoa hồng = finished VP, không phải cây.**

Flow:

```text
Hồng 35
→ MAIN
→ Tuyết 28
→ máy TDHH
→ sản xuất TDHH x7
→ sửa máy
→ MAIN
```

`RoseOilRecipe` chỉ orchestration.

`RoseOilProductionActions` sở hữu thao tác production và semantic Action:

```text
close_panel_for_navigation()
```

Recipe không click tọa độ đóng panel trực tiếp nữa.

`KVAutomation` sở hữu một shared instance:

```text
rose_oil_production
```

Recipe dùng instance này thay vì tự `new RoseOilProductionActions`.

## 8. Recipe / Function — AUDIT HIỆN TẠI

Đã audit:

- DriedAppleRecipe
- AppleJuiceRecipe
- YellowFabricRecipe
- RoseOilRecipe
- RecipeBook
- FunctionOneWorkflow
- FunctionTwoWorkflow

Contract:

- không raw `driver.click/swipe/swipe_points` trong Recipe/Function;
- mỗi Function dùng một `RecipeBook` và một shared `RecoveryManager`;
- Function 2 compose Function 1 core, không copy business actions;
- Function 2 handoff known floor3 qua RecoveryManager rồi gọi RoseOilRecipe;
- không tạo parallel RecoveryManager trong Function.

Legacy modules đã audit:

- `auto_apple_dryer` = compatibility adapter gọi DriedAppleRecipe;
- `auto_planting` = isolated module ghép semantic Navigation + Planting Actions;
- `ProductionWarehouseRecovery` = compatibility facade delegate RecoveryManager.

## 9. Recovery — SOURCE HIỆN ĐÚNG RANH GIỚI

NavigationRecovery:

- gọi semantic `farm_routes/farm_boundary_routes`;
- không raw click/swipe;
- unknown camera recovery bounded theo policy hiện hữu.

ProductionRecovery:

- typed `WrongProductionMachine`;
- typed `InventoryFull`;
- dùng `ModuleRecoveryExecutor` giữ same-module checkpoint;
- generic ScreenTimeout không được tự retry;
- Sale recovery không trả control về Scheduler như Function PASS.

MaterialShortage:

- Action giữ progress nhỏ để resume;
- Recovery quyết định route/bổ sung/resume;
- Táo/Bông dùng policy hiện hữu;
- không tự áp policy đó cho Hồng/Tuyết.

## 10. Worker / scheduled restart — ĐÃ REFACTOR SOURCE

Worker không còn:

```text
Exception → về MAIN → rerun whole pipeline
```

Hiện:

```text
typed recoverable error → RecoveryManager
unregistered error       → fail-close/log
ClientRestartRequested   → dedicated lifecycle signal
```

Scheduled restart:

```text
3h = 10800s
→ không cắt ngang Function
→ Function PASS
→ safe sale nếu cần
→ ClientRestartRequested
→ supervisor relaunch exact profile
→ new worker/Bridge generation
→ startup 60s
→ skip initial sale once
```

Chưa gọi runtime PASS cho tới live test.

Emergency mid-Function restart chưa bật vì cần durable checkpoint + operator-defined policy.

## 11. Safety debt — KHÔNG TỰ SỬA

### Production panel open

`ProductionActions._click_until_panel_open(...)` còn wait loop không bounded.

Chưa có operator-defined max time/burst.

### Production idle-slot wait

`ProductionActions._wait_for_idle_open_panel(...)` còn wait không bounded để chờ machine/slot.

Chưa có operator-defined max wait.

### TDHH thiếu Hồng/Tuyết

Chưa có typed recovery do operator mô tả. Không tự suy diễn replenishment/resume.

### InventoryFull recovery rounds

InventoryFull recovery hiện dừng khi Sale không còn tạo tiến triển; chưa có hard max round riêng được operator chốt. Không tự thêm limit mới.

### Emergency restart

Không bật cho tới durable checkpoint + restore/clear contract.

## 12. Static verifiers

Workflow:

`.github/workflows/auto-standardization-contract.yml`

Verifiers:

```text
tools/verify_recovery_architecture_contract.py
tools/verify_function_boundary_delay_contract.py
tools/verify_action_standardization_contract.py
tools/verify_recipe_function_standardization_contract.py
```

Các verifier khóa:

- startup 60s/no startup goDown;
- worker typed-recovery boundary;
- scheduled restart 3h;
- boundary delay absorbs maintenance time;
- shared planting paths 5/6/27/28/30;
- generic farm routes canonical;
- Function-specific route files wrapper-only;
- neutral VP sale transaction + Sale 5 View;
- Recipe/Function không raw input;
- one shared RecoveryManager per Function;
- TDHH Action đi qua KVAutomation facade;
- RoseOilRecipe không trực tiếp đóng panel bằng tọa độ.

## 13. CI blocker hiện tại

Latest AUTO standardization workflow run cho HEAD `51a1a535...` vẫn:

```text
job=auto-contract
status=completed
conclusion=failure
steps=null
logs_url=null
```

=> runner/provisioning chưa thực thi bất kỳ step nào.

Do đó:

```text
KHÔNG gọi STATIC PASS
KHÔNG kết luận source compile fail từ run này
```

## 14. Checkpoint commits gần nhất

```text
f7dd679c  refactor(auto): move TDHH panel close gesture into Action
bb629c91  refactor(auto): export TDHH production Action through shared facade
f3f6b512  refactor(auto): expose TDHH production through KVAutomation facade
7dd06c5e  refactor(auto): keep TDHH recipe orchestration-only
cb4c54ee  test(auto): lock Recipe and Function orchestration boundaries
51a1a535  ci(auto): verify Recipe and Function orchestration contracts
```

Các checkpoint trước vẫn giữ hiệu lực: shared PATH_6, generic farm routes, neutral VP sale facade, boundary-aware Function delay, worker fail-close và restart 3h.

## 15. Điểm tiếp tục

Tiếp tục theo thứ tự:

1. audit FriendRefresh + Builder Modules;
2. audit canonical imports/aliases còn sót;
3. không đổi production wait/TDHH shortage/InventoryFull hard-limit khi operator chưa chốt;
4. cập nhật verifier khi phát hiện boundary mới;
5. khi CI runner thực thi được mới đánh dấu static PASS;
6. runtime/live PASS chỉ sau operator test.
