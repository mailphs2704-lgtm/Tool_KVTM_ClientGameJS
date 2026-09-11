# AUTO MULTI DEV — LATEST HANDOFF

Cập nhật: 2026-09-11
Repo: `mailphs2704-lgtm/Tool_KVTM_ClientGameJS`
Branch bắt buộc: `develop/multi-auto-dev`
Trạng thái: **WHOLE-AUTO STANDARDIZATION IN PROGRESS — SOURCE REFACTORED, NOT RUNTIME PASS**

> Operator đã yêu cầu chuẩn hóa toàn bộ AUTO và cho phép triển khai/refactor từng đoạn ngay khi mô tả. Build/static PASS không thay cho live/runtime evidence.

## 1. Read-first bắt buộc

1. `docs/AUTO_MULTI_DEV_LATEST_HANDOFF.md` — handoff hiện hành;
2. `docs/AUTO_MULTI_DEV_ACTIONS_AUDIT_20260911.md` — audit Action mới nhất;
3. `docs/AUTO_MULTI_DEV_STANDARDIZATION_CHECKPOINT_20260911.md` — checkpoint source/refactor;
4. `docs/AUTO_MULTI_DEV_STANDARDIZATION_LATEST.md` — thiết kế tích lũy;
5. `docs/AUTO_MULTI_DEV_CONFIRMED_FLOW_LATEST.md`;
6. `docs/AUTO_MULTI_DEV_ACTIONS_STANDARDIZATION.md`;
7. `docs/AUTO_MULTI_DEV_FUNCTION_RECOVERY_MAPPING.md`;
8. `docs/AUTO_MULTI_DEV_GLOBAL_RECOVERY_CHECKPOINTS.md`;
9. `docs/AUTO_MULTI_DEV_RECOVERY_ARCHITECTURE.md`;
10. `AI_COORDINATION.md`.

Nếu tài liệu cũ nói popup chỉ sweep sau khi chờ 60s, restart 2h, TDHH là cây, worker catch-all rerun pipeline, Sale chỉ 4 View, hoặc Function 1 là owner của farm routes thì coi là **lịch sử đã bị override**.

## 2. Kiến trúc hiện hành

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
ACTIVE CHECKPOINT (RAM, metadata-only)
```

```text
Recovery != Function completion
Recovery = interrupt → recover → resume same work
```

- Function = WHAT + order.
- Module/Recipe = compose Actions.
- Action = HOW reusable manipulation/verification.
- Recovery = typed error + checkpoint + resume/escalation.

## 3. Startup/Login/Popup — CHỐT, SOURCE ĐÃ REFACTOR

```text
login/restart
→ camera mặc định MAIN
→ bắt đầu timer 60s
→ trong đủ 60s liên tục scan popup
→ popup nào xuất hiện thì đóng ngay
→ tiếp tục scan tới hết 60s
→ bàn giao MAIN
```

Không dùng `goDown(1)` để tạo exact-main sau login/restart.

## 4. Sale VP — CHỐT, SOURCE ĐÃ REFACTOR

Mỗi View:

```text
thu vàng nếu có
→ QC nếu có
→ tìm ô trống
→ Kho 2
→ VP allowed theo Function
→ chứng minh đủ x10
→ đăng bán
```

Nếu View hết ô trống:

```text
stall.next_view()
= đúng 2 swipe
```

Tổng **5 View**; View 5 là final boundary/overlap check.

Canonical one-listing transaction Action:

```text
VpSaleTransactionActions
```

`AutoMainSellingActions` là tên/base lịch sử; code Sale mới không phụ thuộc tên AUTO Main.

## 5. Function boundary delay — CHỐT + SOURCE IMPLEMENTED

Operator phát hiện lỗi cũ:

```text
Function PASS
→ Sale
→ sleep nguyên delay
→ Function kế tiếp
```

Contract mới:

```text
Function PASS
→ bắt đầu boundary timer
→ Sale/Friend Refresh/maintenance nếu đến hạn
→ elapsed = thời gian maintenance đã dùng
→ sleep chỉ phần delay còn thiếu
→ Function kế tiếp
```

Ví dụ delay 60s:

```text
Sale 25s → chờ thêm 35s
Sale 65s → không chờ thêm
```

Áp dụng cho:

- AUTO Main;
- AUTO Builder `sale_after_each_loop`.

Runtime AUTO Main export hiện dùng `workflows/auto_main/boundary_delay.py`.

Verifier: `tools/verify_function_boundary_delay_contract.py`.

## 6. Navigation primitive — CHỐT

`goUp(n)` là mode hành động, không phải N lần swipe.

```text
goUp(1) = swipe ngắn một tầng
          (514,214) → (514,314)

goUp(2) = click anchor (257,191)
          nếu tầng 1 → candidate tầng 3
          KHÔNG bằng 2 x goUp(1)

goUp(4) = long swipe (387,69) → (387,918)
          nếu tầng 1 → candidate tầng 5

goUp(3) = undefined → fail-close
```

Canonical primitive: `FloorNavigationActions`.

## 7. Farm routes — CANONICAL OWNERSHIP ĐÃ CHUYỂN

`actions/farm_routes.py` hiện sở hữu **implementation thật**:

- `FarmRouteActions`
- `FarmBoundaryRouteActions`
- `NavigationEvidence`

Các route dùng chung như MAIN→1, 1→5, 1→6, MAIN→2, 1→3, known-floor→MAIN/boundary proof nằm ở đây.

Hai file lịch sử chỉ còn compatibility wrapper:

```text
FunctionOneNavigationActions(FarmRouteActions)
FunctionOnePassThreeNavigationActions(FarmBoundaryRouteActions)
```

Không thêm implementation mới vào file Function-specific.

`KVAutomation` expose canonical facade:

```text
farm_routes
farm_boundary_routes
```

## 8. Planting — SHARED GEOMETRY

`PlantingActions` hiện giữ verified shared paths:

```text
PATH_5
PATH_6
PATH_27
PATH_28
PATH_30
```

`PATH_6` được promote từ exact geometry hàng 6 chậu tầng 6 đã tồn tại trong Apple Supply; không đổi gesture.

Apple Supply hiện dùng:

```text
FIVE_FLOOR_PATH = PlantingActions.PATH_30
FLOOR_6_ROW      = PlantingActions.PATH_6
```

Crop identity tách khỏi geometry; Action không quyết định floor route.

## 9. Function 2 / TDHH — CHỐT PHÂN LOẠI

- Hồng = crop/material.
- Tuyết = crop/material.
- **TDHH/Tinh dầu hoa hồng = finished VP, không phải cây.**

Flow hiện hiểu:

```text
Hồng 35
→ MAIN
→ Tuyết 28
→ tới máy TDHH
→ sản xuất TDHH x7
→ sửa máy
→ MAIN
```

`RoseOilRecipe` sở hữu choreography; `PlantingActions` chỉ sở hữu crop gesture/path; `RoseOilProductionActions` sản xuất VP TDHH.

`actions/function_two_planting.py` là compatibility-only và choreography cũ bị chặn.

## 10. Function / Recipe standardization

- Function 1 dùng RecipeBook + generic farm routes.
- Function 2 dùng cùng RecipeBook/RecoveryManager và thêm RoseOilRecipe.
- `DriedAppleRecipe`, `AppleJuiceRecipe`, `YellowFabricRecipe`, `RoseOilRecipe` dùng chung **một RecoveryManager per Function**.
- `auto_apple_dryer` là adapter gọi Recipe chuẩn.

## 11. Recovery / checkpoint

Lifecycle:

```text
MODULE_STARTED
MODULE_INTERRUPTED
MODULE_RESUMED
MODULE_COMPLETED
```

Known typed recovery hiện gồm các nhánh như:

- `WrongProductionMachine`;
- `InventoryFull`;
- typed MaterialShortage nơi đã được triển khai.

Generic `ScreenTimeout` không được tự biến thành recovery/restart.

Worker:

```text
registered typed error
→ RecoveryManager
→ resume same module/checkpoint

unregistered error
→ fail-close + log
```

Không còn:

```text
Exception → MAIN → rerun whole pipeline
```

## 12. Material Shortage boundary

Action được giữ progress nhỏ để resume side effect:

```text
queued
slot evidence
recovery_count
```

Crop Action Bông chỉ biết cách lấy batch 27 Bông thật và gieo lại.

Recovery mới biết:

```text
vì sao thiếu
→ route về MAIN/floor cần thiết
→ bổ sung
→ quay máy
→ resume
```

## 13. Machine Repair / Production audit

Machine Repair hiện đúng boundary:

```text
verified production handoff
→ ?
→ Sửa
→ verify UI change
→ close modal
```

Không chứa Friend Refresh/restart/scheduler.

Production shared engine sở hữu panel/product/slot proof và typed signals.

Gesture retry hiện bounded:

```text
DRAG_ATTEMPTS = 3
VERIFY_RECHECKS = 4
```

## 14. ClientJS scheduled restart — 3H

```text
CLIENT_RESTART_INTERVAL = 10800s
```

```text
3h due giữa Function
→ defer
→ Function hiện tại PASS
→ sale an toàn tại boundary nếu cần
→ ClientRestartRequested
→ worker lifecycle signal
→ supervisor đóng/relaunch đúng profile
→ worker + Bridge generation mới
→ startup 60s
→ skip startup sale đúng 1 lần
→ timer ClientJS mới 3h
```

Chưa gọi runtime PASS cho đến live test.

Emergency restart giữa Function chưa bật: cần durable checkpoint + operator-defined policy.

## 15. Friend Refresh / escalation

Periodic Friend Refresh và Recovery Friend Refresh độc lập.

Target escalation:

```text
specialized recovery
→ bounded local retry
→ Friend Refresh #1
→ resume same checkpoint
→ retry
→ Friend Refresh #2
→ resume
→ retry
→ emergency restart chỉ khi policy được chốt
→ fail-close
```

Không invent retry/error policy khi operator chưa mô tả điểm lỗi.

## 16. Safety debt — CẦN OPERATOR CHỐT

### Production panel open

`ProductionActions._click_until_panel_open(...)` còn wait loop không bounded.

Chưa có max burst/time được operator quy định.

### Production idle-slot wait

`ProductionActions._wait_for_idle_open_panel(...)` còn wait không bounded để chờ máy/slot.

Chưa có max wait operator-defined.

### TDHH thiếu Hồng/Tuyết

Chưa có typed recovery được operator mô tả. Không tự suy diễn cách bổ sung/resume.

### Emergency mid-Function restart

Chưa bật trước durable checkpoint + clear/restore policy.

## 17. Static verification / CI

Workflow:

`.github/workflows/auto-standardization-contract.yml`

Verifiers:

```text
tools/verify_recovery_architecture_contract.py
tools/verify_function_boundary_delay_contract.py
tools/verify_action_standardization_contract.py
```

Action verifier khóa:

- PATH 5/6/27/28/30;
- Apple Supply dùng shared paths;
- generic farm routes sở hữu implementation;
- Function 1 route files chỉ wrapper;
- VP sale neutral transaction facade;
- Sale 5 View + vàng→QC;
- Function 2 planting compatibility-only.

GitHub Actions trước đó có lỗi hạ tầng `steps=null`; khi runner chưa thực thi, không được gọi static PASS cũng không kết luận compile fail.

## 18. Checkpoint commits mới đáng chú ý

```text
1b1a8697  refactor(auto): promote verified 6-pot planting path to shared Actions
5c115ace  refactor(auto): reuse shared 6-pot path for apple supply
224229a9  test(auto): lock shared Action standardization contracts
6fae962a  ci(auto): verify shared Action standardization contracts
fa649e33  refactor(auto): make generic farm routes canonical implementation
80f73684  refactor(auto): reduce Function 1 navigation to compatibility wrapper
b306f7a9  refactor(auto): reduce Function 1 boundary navigation to compatibility wrapper
43fe1ec6  test(auto): lock generic farm route ownership
8fd129eb  docs(auto): refresh Actions audit after route and path standardization
```

Boundary-delay checkpoints trước đó:

```text
5e9c7ec1  fix(auto): count sale time inside Function loop delay
521c77cd  fix(auto): absorb maintenance time into AUTO Main loop delay
97e89156  fix(auto): export boundary-aware AUTO Main scheduler
3aa62fd4  test(auto): lock boundary-aware Function delay contract
0aa39e07  ci(auto): verify Function boundary delay contract
0108b5fe  docs(auto): define Function boundary delay semantics
```

## 19. Tiếp tục chuẩn hóa

Ưu tiên an toàn tiếp theo:

1. audit remaining Action imports/aliases để code mới chỉ dùng canonical generic names;
2. audit Recipe/Module để loại raw coordinate/gesture hoặc duplicated recovery còn sót;
3. giữ production wait-loop/TDHH shortage untouched cho tới khi operator chốt;
4. cập nhật verifier + docs theo từng boundary;
5. khi CI runner thực thi được, yêu cầu compile/verifier xanh trước live test;
6. live test theo từng Module/Function, không tự gọi runtime PASS.
