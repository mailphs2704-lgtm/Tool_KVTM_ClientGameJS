# AUTO MULTI DEV — LATEST HANDOFF

Cập nhật: 2026-09-14
Repo: `mailphs2704-lgtm/Tool_KVTM_ClientGameJS`
Branch bắt buộc: `develop/multi-auto-dev`
Trạng thái: **FUNCTION 3 STEP 2 SOURCE COMPLETE — BUILD/LIVE PASS PENDING**

> Operator đã yêu cầu chuẩn hóa toàn bộ AUTO. Không tiếp tục refactor lớn nếu không phát hiện regression thật. Build/static PASS không thay cho live/runtime evidence.

## 1. Read-first bắt buộc

1. `docs/AUTO_MULTI_DEV_LATEST_HANDOFF.md` — handoff hiện hành;
2. `docs/AUTO_MULTI_DEV_STANDARDIZATION_CHECKPOINT_20260911.md` — checkpoint pre-live mới nhất;
3. `docs/AUTO_MULTI_DEV_ACTIONS_AUDIT_20260911.md` — audit Action;
4. `docs/AUTO_MULTI_DEV_STANDARDIZATION_LATEST.md` — thiết kế tích lũy;
5. `docs/AUTO_MULTI_DEV_FUNCTION_RECOVERY_MAPPING.md`;
6. `docs/AUTO_MULTI_DEV_GLOBAL_RECOVERY_CHECKPOINTS.md`;
7. `docs/AUTO_MULTI_DEV_RECOVERY_ARCHITECTURE.md`;
8. `AI_COORDINATION.md`.

Nếu tài liệu cũ nói popup chỉ sweep sau 60s, restart 2h, TDHH là cây, worker catch-all rerun pipeline, Sale 4 View, Function 1 sở hữu farm routes, hoặc product khác phải mượn `ProductionActions` Táo sấy để dùng panel helper thì coi là **lịch sử đã bị override**.

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

## 3. Startup/Login/Popup — CHỐT + SOURCE

```text
login/restart
→ camera mặc định MAIN
→ popup watch 60s
→ popup xuất hiện lúc nào đóng ngay lúc đó
→ tiếp tục scan đủ 60s
→ bàn giao MAIN
```

Không `goDown(1)` để tạo exact-main sau login/restart.

## 4. Sale VP — CHỐT + SOURCE

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

- chuyển view = đúng 2 swipe;
- tổng 5 View;
- View 5 = final overlap/boundary check;
- canonical transaction facade = `VpSaleTransactionActions`.

## 5. Function boundary delay — CHỐT + SOURCE

Delay là **minimum boundary time**:

```text
Function PASS
→ start boundary timer
→ Sale/Friend Refresh/maintenance nếu đến hạn
→ maintenance time được tính vào delay
→ chỉ sleep phần còn thiếu
→ Function tiếp theo
```

Ví dụ delay 60s:

```text
Sale 25s → chờ 35s
Sale 65s → chờ 0s
```

Áp dụng AUTO Main + Builder `sale_after_each_loop`.

## 6. Navigation / Farm routes — CANONICAL

`goUp(n)` là semantic mode:

```text
goUp(1) = short swipe
goUp(2) = click anchor (257,191); floor1 → candidate floor3
goUp(4) = long swipe; floor1 → candidate floor5
goUp(3) = undefined → fail-close
```

Canonical:

```text
FloorNavigationActions
FarmRouteActions
FarmBoundaryRouteActions
```

Function 1 navigation files chỉ compatibility wrappers.

## 7. Planting — SHARED GEOMETRY + DYNAMIC SEED IDENTITY

`PlantingActions` giữ:

```text
PATH_5
PATH_6
PATH_24
PATH_27
PATH_28
PATH_30
```

Crop identity tách khỏi geometry. Apple Supply tái sử dụng `PATH_30` + `PATH_6`; Cotton Action không tự quyết định recovery policy.

Từ Function 3 Step 2, seed/cây trong bảng gieo phải được tìm bằng template động cho **mọi loại cây**, không riêng Trà. Vị trí seed thay đổi theo account/session nên cấm dùng tọa độ seed tuyệt đối. Nếu template chưa xuất hiện, click mũi tên chuyển trang phải đã được operator đánh dấu, scan lại và chỉ dừng khi template mục tiêu được tìm thấy; điểm bắt đầu kéo là `match.center`.

## 8. Production — SHARED PANEL ENGINE

Canonical reusable engine:

```text
ProductionPanelActions
```

Sở hữu:

- panel/product proof;
- empty-slot counting;
- collect burst x5;
- wrong-machine detection;
- InventoryFull signal;
- panel/capacity waits.

Product transactions:

```text
ProductionActions             → Táo sấy
AppleJuiceProductionActions   → Nước táo
YellowFabricProductionActions → Vải vàng
RoseOilProductionActions      → TDHH
```

`warehouse_full_guard.py` patch `ProductionPanelActions`, vì vậy KHO QUÁ TẢI dùng chung cho mọi product path.

TDHH không kế thừa Táo sấy; contract riêng:

```text
TARGET_COUNT = 7
DRAG_ATTEMPTS = 3
VERIFY_RECHECKS = 4
```

MaterialShortage resume state hiện hữu được giữ nguyên qua refactor.

## 9. Function 2 / TDHH — CHỐT PHÂN LOẠI

- Hồng = crop/material.
- Tuyết = crop/material.
- **TDHH = VP thành phẩm, không phải cây.**

```text
Hồng 35
→ MAIN
→ Tuyết 28
→ máy TDHH
→ TDHH x7
→ sửa máy
→ MAIN
```

`RoseOilRecipe` chỉ orchestration; production nằm trong `RoseOilProductionActions` và được expose qua `KVAutomation.rose_oil_production`.

## 10. Recipe / Function / Module boundary

Đã audit và verifier khóa:

- Recipe/Function không raw input;
- một `RecoveryManager` per Function;
- Function 2 compose Function 1 core;
- Builder Modules delegate đúng chức năng hiển thị;
- FriendRefresh dùng semantic Navigation/Recovery;
- boundary-delay wrapper không tạo scheduler `run()` thứ hai;
- legacy workflow chỉ adapter khi phù hợp.

## 11. Recovery / Worker

Known typed recovery gồm:

- `WrongProductionMachine`;
- `InventoryFull`;
- MaterialShortage nơi đã triển khai.

Generic `ScreenTimeout` không tự retry.

Worker hiện:

```text
typed recoverable error → RecoveryManager → same module/checkpoint
unregistered error       → fail-close/log
ClientRestartRequested   → lifecycle signal
```

Không còn `Exception → MAIN → rerun whole pipeline`.

## 12. Scheduled restart — 3H

```text
CLIENT_RESTART_INTERVAL = 10800s
```

```text
3h due giữa Function
→ defer
→ Function PASS
→ safe sale nếu cần
→ ClientRestartRequested
→ supervisor relaunch exact profile
→ new worker/Bridge generation
→ startup 60s
→ skip initial sale once
```

Emergency restart giữa Function chưa bật; cần durable checkpoint + operator policy.

## 13. Safety debt — KHÔNG TỰ SỬA

- `ProductionPanelActions._click_until_panel_open(...)` còn unbounded wait; chưa có operator max burst/time.
- `ProductionPanelActions._wait_for_idle_open_panel(...)` còn unbounded wait; chưa có operator max wait.
- TDHH thiếu Hồng/Tuyết chưa có typed replenishment recovery do operator mô tả.
- InventoryFull recovery chưa có hard max round operator-defined; hiện fail-close khi Sale recovery không tạo tiến triển.
- Emergency restart giữa Function chưa bật.

## 14. Static verification / CI

Workflow:

`.github/workflows/auto-standardization-contract.yml`

Verifiers hiện gồm:

```text
verify_recovery_architecture_contract.py
verify_function_boundary_delay_contract.py
verify_action_standardization_contract.py
verify_recipe_function_standardization_contract.py
verify_module_scheduler_boundaries_contract.py
verify_production_action_boundaries_contract.py
```

Production verifier khóa:

- `ProductionPanelActions` product-agnostic;
- Táo sấy subclass shared panel engine;
- Nước táo/Vải vàng không mượn Táo sấy làm slot helper;
- TDHH trực tiếp dùng shared panel engine + explicit x7;
- warehouse-full guard patch shared engine;
- material-shortage resume-layer được giữ.

Run `AUTO standardization contract` cho commit `5d713a31...` vẫn bị blocker hạ tầng:

```text
run_id=34614344739
job=auto-contract
conclusion=failure
steps=[]
runner_id=0
runner_name=""
```

=> GitHub chưa cấp runner và **không thực thi compile/verifier**. Vì vậy:

```text
KHÔNG gọi source compile fail
KHÔNG gọi STATIC PASS
```

Pre-live static/build phải chuyển sang luồng DEV chính thức trên máy operator.

## 15. Import/export audit sau ProductionPanel refactor — COMPLETE

Đã kiểm tra source hiện tại:

- `actions/__init__.py` export `ProductionPanelActions`;
- warehouse-full guard được install trước product Action imports;
- `ProductionActions` chỉ còn Táo sấy và subclass `ProductionPanelActions`;
- Nước táo/Vải vàng dùng neutral `ProductionPanelActions` helper;
- TDHH subclass trực tiếp `ProductionPanelActions` và khai báo explicit constants riêng;
- `KVAutomation` vẫn khởi tạo các product Action bằng constructor tương thích;
- không phát hiện regression import/ownership mới trong audit này.

Đây là **source audit**, không thay cho Python compile thật.

## 16. Checkpoint commits gần nhất

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
047cac1e  docs(auto): refresh pre-live-test standardization checkpoint
eda5b0e9  docs(auto): move handoff to pre-live-test checkpoint
```

## 17. NEXT GATE — LOCAL BUILD, KHÔNG REFACTOR THÊM

Source chuẩn hóa hiện đã tới gate build trước live test.

Operator thực hiện đúng luồng dự án:

```text
D:\Tool_KVTM_Multi_DEV\KVTM_DEV_CONTROL.bat
→ [1] Cap nhat source + build runtime DEV
```

Sau khi build/static thật sự sạch:

```text
LIVE TEST smoke modules
→ Startup 60s
→ Navigation
→ Planting
→ Production/Repair
→ Sale 5 View
→ Friend Refresh

sau đó:
Function 1 full loop
→ Function 2 full loop
```

Nếu build fail, sửa đúng lỗi compile/import/contract trước. Không mở lại refactor kiến trúc rộng nếu không có bằng chứng regression.

**Không gọi STATIC PASS hoặc RUNTIME PASS trước bằng chứng tương ứng.**

## 18. Function 3 — STEP 1 LIVE PASS

Operator xác nhận live test **PASS** ngày 2026-09-14 trên source/build mốc `ac31388c`.

Quy trình đã chứng minh:

```text
MAIN → goUp(1) tầng 1
→ chậu đầu (388,946)
→ RIPE: thu 30 chậu / EMPTY: mở bảng gieo trực tiếp
→ gieo 30 Táo tầng 1-5
→ tầng 6 thu/gieo 6 Táo
→ goDown(1) + click nút XUỐNG → exact MAIN
→ goUp(1) tầng 1
→ thu VP/mở máy
→ tìm tra_say; MISS thì chuyển trang phải từng lần
→ sản xuất 9/9 Trà sấy
→ Sửa máy
→ giữ nguyên tại tầng 1
```

Ranh giới hiện tại:

- Step 1 vẫn giữ nguyên recipe/live-PASS boundary và kết thúc ở tầng 1;
- Function 3 dùng chung RecipeBook/RecoveryManager và sale policy Nước hoa hồng/Trà đá/Vải vàng;
- không sửa lại Step 1 nếu không có regression live.

## 19. Function 3 — STEP 2 SOURCE COMPLETE / LIVE PENDING

Operator chốt **Step 2 DONE về mặt mô tả** ngày 2026-09-14. Source đã cập nhật, nhưng chưa gọi runtime PASS trước Windows live evidence.

Quy trình Step 2:

```text
đầu Step 2: đứng tầng 1
→ goUp(1) lên tầng 2
→ dùng shared Planting Action thu hoạch 4 tầng trên màn hình
→ mở bảng gieo tại chậu đầu tầng dưới cùng
→ tìm cay_tra bằng template động
→ MISS: click mũi tên chuyển trang phải, scan lại, chỉ dừng khi tìm thấy
→ kéo từ match.center của cay_tra, không dùng tọa độ cây Trà tuyệt đối
→ gieo 24 Trà = 4 tầng x 6
→ đứng nguyên tầng 2
→ thu VP/mở máy Nước táo tầng 2 bằng shared production Action
→ sản xuất 9/9 Nước táo
→ Sửa máy
→ đứng nguyên tầng 2
→ Step 2 DONE
```

Source boundary:

```text
FunctionThreeWorkflow.TOTAL_DEFINED_STEPS = 2
run_step_1()              → end floor 1
run_step_2_from_floor_1() → end floor 2
run_steps_1_and_2()       → exact MAIN → Step 1 → Step 2 → end floor 2
```

`DriedTeaStepTwoRecipe` không raw-click máy. `AppleJuiceProductionActions.produce_9_apple_juices(close_after_success=False)` sở hữu thao tác thu VP/mở đúng máy, xác minh panel và xếp chính xác 9/9; sau đó bàn giao panel cho shared `MachineRepairActions`.

Checkpoint chi tiết: `docs/AUTO_FUNCTION_3_STEP_2_CHECKPOINT_20260914.md`.

Function 3 đầy đủ vẫn chưa nối AUTO Main. NEXT: nhận mô tả phần tiếp theo từ operator; nếu operator muốn live-gate Step 2 ngay thì wire DEV cumulative test rồi build `[1]` và lấy live evidence. Không đổi Step 1 đã PASS.
