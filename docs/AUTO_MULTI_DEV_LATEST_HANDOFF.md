# AUTO MULTI DEV — LATEST HANDOFF

Cập nhật: 2026-09-11
Repo: `mailphs2704-lgtm/Tool_KVTM_ClientGameJS`
Branch bắt buộc: `develop/multi-auto-dev`
Trạng thái: **WHOLE-AUTO STANDARDIZATION IN PROGRESS — SOURCE REFACTORED, NOT RUNTIME PASS**

> Operator cho phép triển khai/refactor từng đoạn ngay khi mô tả và hiện đã yêu cầu chuẩn hóa toàn bộ AUTO. Không cần chờ mô tả xong toàn bộ Function. Build/static PASS không được thay cho live/runtime evidence.

## 1. Read-first bắt buộc

1. `docs/AUTO_MULTI_DEV_STANDARDIZATION_CHECKPOINT_20260911.md` — checkpoint source/refactor mới nhất;
2. `docs/AUTO_MULTI_DEV_LATEST_HANDOFF.md` — handoff hiện hành;
3. `docs/AUTO_MULTI_DEV_STANDARDIZATION_LATEST.md` — thiết kế tích lũy, có thể chứa wording lịch sử;
4. `docs/AUTO_MULTI_DEV_CONFIRMED_FLOW_LATEST.md` — Startup/Sale/Navigation đã xác nhận;
5. `docs/AUTO_MULTI_DEV_ACTIONS_STANDARDIZATION.md`;
6. `docs/AUTO_MULTI_DEV_FUNCTION_RECOVERY_MAPPING.md`;
7. `docs/AUTO_MULTI_DEV_GLOBAL_RECOVERY_CHECKPOINTS.md`;
8. `docs/AUTO_MULTI_DEV_RECOVERY_ARCHITECTURE.md`;
9. `AI_COORDINATION.md`.

Nếu tài liệu cũ còn nói popup sweep sau khi chờ 60s, restart 2h, TDHH là planting/cây, hoặc worker catch-all rerun pipeline thì coi đó là **lịch sử đã bị override**.

## 2. Kiến trúc đang áp dụng

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

Nguyên tắc:

```text
Recovery != Function completion
Recovery = interrupt -> recover -> resume same work
```

- Function mô tả WHAT + thứ tự nghiệp vụ.
- Recipe/Module ghép các Action.
- Action thực hiện HOW dùng chung.
- Recovery xử lý typed error/checkpoint/escalation; Action/Function không tự tạo loop recovery riêng.

## 3. Startup/Login/Popup — CHỐT + SOURCE ĐÃ REFACTOR, CHỜ LIVE TEST

Sau ClientJS open/restart:

```text
login game thành công
→ camera mặc định MAIN
→ bắt đầu timer 60s
→ trong đủ 60s liên tục check popup
→ popup xuất hiện thì đóng ngay
→ tiếp tục scan cho tới hết 60s
→ bàn giao MAIN cho scheduler
```

- Không dùng `goDown(1)` để tạo exact-main sau login/restart.
- `GameSessionWorkflow.POPUP_WATCH_SECONDS = 60.0`.
- Startup ghi exact-main theo startup contract; nếu mất contract thì fail-close.

## 4. Sale VP — CHỐT + SOURCE ĐÃ REFACTOR, CHỜ LIVE TEST

View 1 bắt đầu ở 8 ô đầu.

Trong mỗi View:

```text
check vàng → thu vàng nếu có
→ check QC
→ tìm ô trống
→ nếu có: mở Kho 2 → quét VP allowed theo Function → chứng minh x10 → đăng bán
→ tiếp tục lấp ô trống
```

Nếu không có ô trống:

```text
stall_next_view()
= đúng 2 nhịp swipe
→ scan lại vàng/QC/slot/sale
```

Tổng 5 View; View 5 là final overlap/end check. Sale dừng khi không còn VP hợp lệ đủ 10 hoặc đã quét hết boundary mà không còn chỗ hợp lệ.

## 5. Navigation Actions — CHỐT + SOURCE ĐÃ REFACTOR

`goUp(n)` là mode hành động, không phải lặp swipe N lần.

```text
goUp(1) = swipe ngắn một tầng
          current reference (514,214) → (514,314)

goUp(2) = click anchor chậu (257,191)
          nếu đang tầng 1 → candidate tầng 3
          KHÔNG bằng goUp(1) + goUp(1)

goUp(4) = swipe dài (387,69) → (387,918)
          nếu đang tầng 1 → candidate tầng 5

goUp(3) = chưa định nghĩa → fail-close
```

Canonical primitive: `FloorNavigationActions`.

Route composer dùng chung mới:

- `FarmRouteActions`
- `FarmBoundaryRouteActions`

`KVAutomation` expose:

```text
farm_routes
farm_boundary_routes
```

Hai attribute lịch sử `function_one_navigation` và `function_one_pass_three_navigation` chỉ là compatibility aliases trỏ cùng object; code mới không được phụ thuộc tên Function-specific.

## 6. Planting / TDHH — CHỐT PHÂN LOẠI

Planting path/count dùng chung:

```text
PATH_5
PATH_27
PATH_28
PATH_30
```

Crop identity tách khỏi geometry.

### Function 2

- Hoa hồng = cây/nguyên liệu.
- Cây tuyết = cây/nguyên liệu.
- **TDHH / Tinh dầu hoa hồng = VP thành phẩm, KHÔNG phải cây.**

Flow:

```text
Hồng 35
→ MAIN
→ Tuyết 28
→ tới máy TDHH
→ sản xuất VP TDHH x7
→ sửa máy
→ MAIN
```

`RoseOilRecipe` ghép Material Preparation + Navigation + `RoseOilProductionActions` + Repair + Return MAIN.

## 7. Function / Recipe standardization hiện tại

- Function 1 dùng RecipeBook và `farm_routes`; không sở hữu primitive điều hướng.
- Function 2 kế thừa Function 1 core và dùng cùng RecipeBook/RecoveryManager.
- `DriedAppleRecipe`, `AppleJuiceRecipe`, `YellowFabricRecipe`, `RoseOilRecipe` dùng chung một `RecoveryManager` cho mỗi Function.
- `auto_apple_dryer` là compatibility adapter gọi Recipe chuẩn; không giữ recovery riêng.
- `actions/function_two_planting.py` đã retire khỏi runtime business path; Hồng/Tuyết choreography nằm ở Recipe, primitive/path nằm ở PlantingActions.

## 8. Recovery/checkpoint — SOURCE ĐÃ CHUẨN HÓA MỘT PHẦN

Lifecycle:

```text
MODULE_STARTED
MODULE_INTERRUPTED
MODULE_RESUMED
MODULE_COMPLETED
```

`RecoveryManager` là facade chung; `NavigationRecovery` dùng `farm_routes`/`farm_boundary_routes`.

Production hiện chỉ đăng ký typed recovery đã biết như:

- `WrongProductionMachine`;
- `InventoryFull`.

Generic `ScreenTimeout` không được tự retry/restart nếu chưa có policy.

Worker không còn:

```text
Exception → đưa MAIN → rerun toàn pipeline
```

Hiện tại:

```text
registered typed error
→ RecoveryManager
→ resume module/checkpoint

unregistered error
→ fail-close + log
```

Đây là thay đổi bắt buộc để không làm mất checkpoint hoặc chạy lại Function từ đầu.

## 9. ClientJS scheduled restart — SOURCE TARGET ĐÃ ĐỔI 3H, CHỜ LIVE TEST

```text
CLIENT_RESTART_INTERVAL = 10800s = 3h
```

Scheduled restart:

```text
3h due giữa Function
→ defer
→ Function hiện tại PASS
→ sale an toàn tại safe boundary nếu cần
→ ClientRestartRequested
→ worker phát lifecycle signal
→ Multi supervisor đóng đúng ClientJS/profile
→ chờ process/worker cũ kết thúc
→ relaunch đúng profile
→ worker + Bridge generation mới
→ startup/login + popup watch 60s
→ skip startup sale đúng 1 lần vì sale đã chạy trước restart
→ scheduler tiếp tục với timer ClientJS mới 3h
```

Source đã nối Scheduler → Worker → Multi integration theo flow trên. **Chưa gọi runtime PASS cho đến live test.**

Emergency restart giữa Function là luồng khác và chưa được tự bật: muốn làm phải có durable checkpoint + policy theo các điểm lỗi operator mô tả.

## 10. Friend Refresh / escalation

Periodic Friend Refresh và Recovery Friend Refresh phải độc lập.

Escalation mục tiêu:

```text
specialized recovery nếu có
→ bounded local retry
→ Friend Refresh #1
→ resume same checkpoint
→ retry
→ Friend Refresh #2
→ resume same checkpoint
→ retry
→ emergency restart chỉ khi policy được chốt
→ fail-close khi hết giới hạn
```

Không tự invent retry count/error policy trước khi operator mô tả điểm bắt lỗi tương ứng.

## 11. Static verification / CI

Verifier chuẩn hóa:

`tools/verify_recovery_architecture_contract.py`

Workflow tập trung:

`.github/workflows/auto-standardization-contract.yml`

Workflow kiểm tra:

- compile `kvtm_automation`;
- py_compile worker/integration/profile settings/verifier;
- chạy recovery/architecture contract verifier.

Hiện GitHub Actions đang có lỗi hạ tầng: job được tạo nhưng `steps=null`, tức runner chưa thực thi bất kỳ step nào. Vì vậy trạng thái CI `failure` hiện tại **không được diễn giải là compile fail**, đồng thời cũng không được gọi static PASS.

## 12. Checkpoint commits quan trọng của đợt chuẩn hóa này

- `82bc3da80d62e2d56691761dc28583aa9c9f690c` — one RecoveryManager per Function.
- `e26bbfbc26776a242bf806f9d3e5a23ccb49ddf2` — TDHH = finished VP, Hồng/Tuyết = materials.
- `aa41cdcb0c8556ce300839778d0f6d1222c941e1` — standardization checkpoint doc.
- `9e3267ec4dd9ae09394459969ed367d50519693c` — worker typed-recovery boundary.
- `1e83c1031a5574070a84f27d1aadd8332f343c5b` — scheduled restart lifecycle bridge.
- `df863951654a1e8e42637fcbee39abe2b273e463` — 3h ClientJS restart integration.
- `f2dd4f749f63bd1c90bf311c1914b2483ea2fb5d` — per-profile UI/config 3h.
- `c28220b65bdf80276c64ce3c1fb903cebc6f5dd2` — verifier locks new contracts.
- `eb66b63352e867beb1f985fee4f75a49eb8fff4e` — focused AUTO contract workflow.
- `3aa21dec65e5dcec2c7790e97c37d6db70c4c4d6` — generic FarmRouteActions facade.
- `f229749c21c01968a08ad9b9f08f3a730dff6f30` — KVAutomation exposes generic route facade.
- `ceb621d4b22bcf26079f43ae7eec0e6712b0d4bb` — Global Recovery uses generic farm routes.
- `a3e00d5962c85c1c4bce74a9e138d13d985cf555` — TDHH Recipe uses generic farm routes.
- `6413f6084391da2489dc999a362e688fcb6c3bc5` — Function 1 uses generic farm routes.

## 13. Điểm tiếp tục chuẩn hóa

Ưu tiên tiếp theo:

1. audit `material_shortage_production.py` và production subclasses để tách Action / Recipe / Recovery đúng ranh giới;
2. retire dần các class/file `FunctionOneNavigation*` thành compatibility-only;
3. kiểm tra Machine Repair/Production không chứa scheduler/recovery escalation;
4. cập nhật verifier khi mỗi boundary mới được chuyển;
5. khi runner GitHub hoạt động, yêu cầu compile/verifier xanh trước live test;
6. sau static evidence mới chuyển sang operator live test, không tự gọi runtime PASS.
