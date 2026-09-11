# AUTO MULTI DEV — STANDARDIZATION CHECKPOINT 2026-09-11

Repo: `mailphs2704-lgtm/Tool_KVTM_ClientGameJS`
Branch bắt buộc: `develop/multi-auto-dev`
Trạng thái: **SOURCE STANDARDIZATION NEAR LIVE TEST — NOT STATIC PASS — NOT RUNTIME PASS**

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

Cotton Action chỉ cung cấp crop manipulation/batch neutral; Recovery quyết định vì sao cần bổ sung Bông.

## 7. Production Action architecture — ĐÃ TÁCH SHARED ENGINE

Canonical shared engine mới:

```text
ProductionPanelActions
```

Sở hữu reusable panel/slot mechanics:

- count/identify empty slots;
- product anchor recognition;
- wrong-machine detection;
- collect burst x5;
- panel-open proof;
- idle/capacity wait;
- typed `InventoryFull`/`WrongProductionMachine` handoff.

Product transactions độc lập dùng engine này:

```text
ProductionActions             → Táo sấy
AppleJuiceProductionActions   → Nước táo
YellowFabricProductionActions → Vải vàng
RoseOilProductionActions      → TDHH
```

`warehouse_full_guard.py` patch **ProductionPanelActions**, không patch riêng Táo sấy. Vì vậy detector KHO QUÁ TẢI dùng chung cho mọi product path.

TDHH khai báo explicit contract riêng:

```text
TARGET_COUNT = 7
REQUIRED_COUNT = 7
DRAG_ATTEMPTS = 3
VERIFY_RECHECKS = 4
```

TDHH không kế thừa transaction Táo sấy.

MaterialShortage resume-layer của Táo sấy/Nước táo/Vải vàng vẫn giữ nguyên; việc tách engine chỉ đổi ownership, không đổi gesture/threshold/retry hiện hữu.

## 8. TDHH — CHỐT PHÂN LOẠI + RECIPE BOUNDARY

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

`RoseOilProductionActions` sở hữu production + semantic `close_panel_for_navigation()`.

`KVAutomation` sở hữu shared instance `rose_oil_production`; Recipe không tự tạo Action riêng.

## 9. Recipe / Function / Module boundary

Đã audit và khóa:

- DriedAppleRecipe
- AppleJuiceRecipe
- YellowFabricRecipe
- RoseOilRecipe
- RecipeBook
- FunctionOneWorkflow
- FunctionTwoWorkflow
- FriendRefreshWorkflow
- Builder EnterGame/Sale/Function/MachineRepair modules

Contract:

- Recipe/Function không raw `driver.click/swipe/swipe_points`;
- mỗi Function dùng một `RecipeBook` + shared `RecoveryManager`;
- Function 2 compose Function 1 core, không copy business actions;
- Builder Module chỉ delegate đúng module hiển thị, không insert business module ẩn;
- boundary-delay wrapper không sở hữu một `run()` scheduler thứ hai.

Legacy adapters đã audit:

- `auto_apple_dryer` = compatibility adapter gọi DriedAppleRecipe;
- `auto_planting` = isolated module ghép semantic Navigation + Planting Actions;
- `ProductionWarehouseRecovery` = compatibility facade delegate RecoveryManager.

## 10. Recovery — SOURCE HIỆN ĐÚNG RANH GIỚI

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

## 11. Worker / scheduled restart — ĐÃ REFACTOR SOURCE

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

## 12. Safety debt — KHÔNG TỰ SỬA

### Production panel open

`ProductionPanelActions._click_until_panel_open(...)` còn wait loop không bounded.

Chưa có operator-defined max time/burst.

### Production idle-slot wait

`ProductionPanelActions._wait_for_idle_open_panel(...)` còn wait không bounded để chờ machine/slot.

Chưa có operator-defined max wait.

### TDHH thiếu Hồng/Tuyết

Chưa có typed recovery do operator mô tả. Không tự suy diễn replenishment/resume.

### InventoryFull recovery rounds

InventoryFull recovery hiện dừng khi Sale không còn tạo tiến triển; chưa có hard max round riêng được operator chốt. Không tự thêm limit mới.

### Emergency restart

Không bật cho tới durable checkpoint + restore/clear contract.

## 13. Static verifiers

Workflow:

`.github/workflows/auto-standardization-contract.yml`

Verifiers:

```text
tools/verify_recovery_architecture_contract.py
tools/verify_function_boundary_delay_contract.py
tools/verify_action_standardization_contract.py
tools/verify_recipe_function_standardization_contract.py
tools/verify_module_scheduler_boundaries_contract.py
tools/verify_production_action_boundaries_contract.py
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
- Module/Scheduler boundary;
- shared `ProductionPanelActions` ownership;
- warehouse-full guard bám shared panel engine;
- TDHH không kế thừa Táo sấy;
- MaterialShortage resume-layer được giữ.

## 14. CI blocker

GitHub Actions các run gần đây có hiện tượng:

```text
job=auto-contract
status=completed
conclusion=failure
steps=null
logs_url=null
```

=> runner/provisioning không thực thi step.

Do đó:

```text
KHÔNG gọi STATIC PASS
KHÔNG kết luận source compile fail chỉ từ run này
```

Nếu runner tiếp tục không thực thi, pre-live static/build phải được xác minh bằng luồng DEV chính thức trên máy operator.

## 15. Checkpoint commits gần nhất

```text
5526eb9f  refactor(auto): extract shared production panel engine
f9448a0a  refactor(auto): keep warehouse-full guard on shared production engine
3bae064f  refactor(auto): make dried apple transaction use shared panel engine
705343ec  refactor(auto): move apple juice panel helpers to shared engine
caaeb0e9  refactor(auto): move yellow fabric panel helpers to shared engine
148ec9ca  refactor(auto): move TDHH production onto shared panel engine
ae259553  refactor(auto): export shared production panel Action
8d1e2d5a  test(auto): lock shared production panel architecture
5d713a31  ci(auto): verify shared production Action boundaries
```

Các checkpoint trước vẫn giữ hiệu lực: Startup 60s, Sale 5 View, generic farm routes, shared planting geometry, Recipe/Function boundary, boundary-aware delay, worker fail-close, restart 3h.

## 16. Điểm tiếp tục trước LIVE TEST

Không mở rộng refactor lớn nếu không phát hiện regression thật.

Thứ tự còn lại:

1. rà import/export/canonical aliases sau khi tách `ProductionPanelActions`;
2. kiểm tra CI run mới; nếu vẫn `steps=null` ghi nhận hạ tầng;
3. cập nhật handoff final pre-live;
4. operator chạy `KVTM_DEV_CONTROL.bat` → `[1] Cap nhat source + build runtime DEV`;
5. static/build sạch thì bắt đầu LIVE TEST module-by-module, rồi Function 1/2 end-to-end.

Runtime/live PASS chỉ sau operator test thực tế.
