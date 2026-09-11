# AUTO MULTI DEV — ACTIONS AUDIT 2026-09-11

Repo: `mailphs2704-lgtm/Tool_KVTM_ClientGameJS`
Branch: `develop/multi-auto-dev`
Status: **SOURCE STANDARDIZATION IN PROGRESS — NOT RUNTIME PASS**

Mục tiêu của audit này là giữ ranh giới:

```text
FUNCTION = WHAT + order
RECIPE/MODULE = compose Actions
ACTION = HOW reusable manipulation/verification
RECOVERY = typed error + checkpoint + resume/escalation
```

Không dùng build/static PASS thay cho live PASS.

## 1. CANONICAL / DÙNG CHUNG

### `actions/floor_navigation.py`

Canonical primitive cho chuyển tầng.

Quy ước operator:

```text
goUp(1) = swipe một tầng
goUp(2) = click anchor pot; từ tầng 1 → candidate tầng 3
goUp(4) = long swipe; từ tầng 1 → candidate tầng 5
goUp(3) = undefined → fail-close
```

Không được biến `goUp(n)` thành loop `goUp(1)`.

### `actions/farm_routes.py`

Canonical route composer dùng chung:

- `FarmRouteActions`
- `FarmBoundaryRouteActions`

`KVAutomation.farm_routes` và `KVAutomation.farm_boundary_routes` là facade mới. Tên `function_one_*` chỉ còn compatibility alias trỏ cùng object.

### `actions/planting.py`

Canonical geometry/crop manipulation:

- PATH 5
- PATH 27
- PATH 28
- PATH 30

Crop identity tách khỏi geometry. Action không quyết định floor route hay thứ tự crop trong Function.

### `actions/cotton_planting.py`

Current-view cotton Action.

- `plant_27_cotton()` = crop manipulation trên view caller đã đưa tới.
- `wait_harvest_and_replant_27_cotton()` = chờ tới khi thực sự thu được một batch 27 Bông rồi gieo lại 27.

Action này không biết vì sao cần batch Bông; `recovery/material_shortage.py` sở hữu lý do/route/resume.

### `actions/apple_supply.py`

Crop Action đặc thù cho semantics chờ Táo chín đã có live/source history.

Đã chuẩn hóa:

- kế thừa `PlantingActions`;
- path 30 lấy từ `PlantingActions.PATH_30`;
- không sở hữu navigation;
- giữ nguyên wait/scan behavior cũ để tránh regression.

`FLOOR_6_ROW` 6 chậu vẫn là geometry riêng đã có; chưa tạo project-wide PATH_6 cho tới khi được chuẩn hóa/verified riêng.

### `actions/machine_repair.py`

Ranh giới hiện đúng:

```text
verified production handoff
→ ?
→ Sửa
→ verify UI change
→ close modal
```

Không chứa Friend Refresh/restart/scheduler policy.

### `actions/production.py`

Shared panel/slot engine + current Táo sấy transaction.

Canonical reusable pieces gồm:

- open/verify product panel;
- detect wrong product/machine;
- detect warehouse full;
- count empty production slots;
- collect burst x5;
- verify each queue drag by slot delta.

Gesture retry hiện bounded:

```text
DRAG_ATTEMPTS = 3
VERIFY_RECHECKS = 4
```

Xem Safety Debt bên dưới cho hai wait loop chưa bounded.

### `actions/apple_juice_production.py`

Product transaction cho VP Nước táo. Dùng shared `ProductionActions` panel/slot engine. Candidate floor-2 probe bounded riêng.

### `actions/yellow_fabric_production.py`

Product transaction cho VP Vải vàng. Dùng shared production panel/slot engine.

### `actions/rose_oil_production.py`

Product transaction cho **VP TDHH / Tinh dầu hoa hồng**.

TDHH là finished VP, không phải crop.

### `actions/stall.py`

Low/domain-level stall interaction:

- open/close stall;
- collect gold;
- two-swipe `next_view()`;
- slot geometry/scan helpers.

Business loop 5 View không nằm ở đây; nó nằm trong `AutoVpSaleWorkflow`.

### `actions/inventory.py`, `selling.py`, `item_recognition.py`, `stall_advertising.py`

Domain Actions. Chúng thao tác/xác minh UI và transaction; Scheduler/Function completion nằm ngoài.

## 2. DOMAIN ACTION ĐÚNG RANH GIỚI NHƯNG TÊN CŨ CÒN GÂY NHẦM

### `actions/auto_main_selling.py`

Thực tế là VP sale transaction Action, không phải AUTO Main scheduler.

Nó xử lý:

```text
own stall ready
→ empty slot
→ storage2
→ scan allowed VP
→ selected item proof
→ exact x10 proof
→ place sale
→ post-sale stall proof
```

Vòng 5 View, vàng/QC, và quyết định kết thúc Sale nằm trong `AutoVpSaleWorkflow`, nên ranh giới behavior hiện đúng.

Có thể đổi facade/tên thành `VpSaleTransactionActions` sau để bỏ coupling bằng tên; không cần đổi gameplay.

## 3. COMPATIBILITY-ONLY / KHÔNG DÙNG CHO CODE MỚI

### `actions/function_one_navigation.py`
### `actions/function_one_pass_three_navigation.py`

Implementation lịch sử hiện được generic facade kế thừa. Code mới phải dùng:

```text
farm_routes
farm_boundary_routes
```

Hai file này chưa xóa để không phá import/runtime/Builder cũ.

### `actions/function_two_planting.py`

Retired khỏi business runtime.

- constants trỏ lại `PlantingActions`;
- `harvest_and_replant_materials()` fail rõ;
- choreography authoritative nằm trong `RoseOilRecipe`.

Không được thêm business flow mới vào file này.

### legacy wrappers trong `actions/planting.py`

Các helper như `_go_up_one`, `_open_seed_picker`, `_plant_27` chỉ giữ compatibility. Code mới phải tách Navigation và current-view Planting Action.

## 4. RECOVERY-AWARE ACTION — CẦN GIỮ PROGRESS, KHÔNG ĐƯỢC SỞ HỮU POLICY

### `actions/material_shortage_production.py`

Nhiệm vụ đúng của lớp Action:

- detect material-shortage visual;
- raise typed `MaterialShortage`;
- giữ progress queue nhỏ trong memory (`queued`, slot evidence...);
- khi được caller gọi lại thì tiếp tục phần còn thiếu, không replay toàn bộ VP đã xếp.

Policy:

```text
về MAIN
→ bổ sung cây
→ quay đúng máy
→ retry/resume
```

nằm ở `recovery/material_shortage.py`, không nằm trong Action.

Một helper Bông recovery-named cũ vẫn có thể còn trong subclass compatibility, nhưng Recovery chuẩn mới không gọi nó nữa.

## 5. SALE MODULE — RANH GIỚI ĐÃ AUDIT

`workflows/auto_vp_sale/workflow.py` sở hữu business loop:

```text
View 1..5
→ thu vàng
→ QC nếu có
→ empty slot
→ sale transaction
→ 2 swipe sang view tiếp theo
```

Thứ tự operator-approved:

```text
VÀNG → QC → Ô TRỐNG → KHO 2 → VP FUNCTION → x10
```

View 5 là final boundary/overlap check.

`AutoMainSellingActions` chỉ xử lý một transaction sale hợp lệ; không quyết định Function PASS hoặc Scheduler next-loop.

## 6. SAFETY DEBT — KHÔNG TỰ SỬA KHI CHƯA CÓ CONTRACT OPERATOR

### Production panel open wait

Trong `ProductionActions._click_until_panel_open(...)` hiện có `while True`.

Nó liên tục x5 collect burst cho tới khi:

- đúng product panel xuất hiện;
- wrong machine signal;
- warehouse full signal.

Chưa có operator-defined maximum time/burst cho normal production open. Không tự invent timeout vì có thể cắt một machine đang legitimate chờ/render/collect.

### Production idle-slot wait

`ProductionActions._wait_for_idle_open_panel(...)` cũng có `while True` để giữ panel chờ máy chạy xong/đủ slot trống.

Chưa có operator-defined maximum wait. Đánh dấu **CẦN CHỐT**.

### TDHH shortage

`RoseOilProductionActions` hiện nếu thiếu Hồng/Tuyết vẫn raise `ScreenTimeout`; chưa có typed material recovery cho TDHH.

Không tự suy diễn cách bổ sung Hồng/Tuyết hoặc resume TDHH cho tới khi operator mô tả điểm bắt lỗi này.

### Emergency restart

Không bật emergency mid-Function restart khi chưa có durable checkpoint + policy rõ. Scheduled 3h restart tại safe Function boundary là luồng riêng.

## 7. NEXT SAFE REFACTOR TARGETS

Không cần operator bổ sung gameplay để làm các bước sau:

1. thêm neutral facade `VpSaleTransactionActions` và giữ `AutoMainSellingActions` compatibility alias;
2. tiếp tục retire tên Function-specific trong import mới;
3. khóa các ranh giới trên bằng verifier;
4. cập nhật handoff/checkpoint.

Cần operator mô tả/CHỐT trước khi làm:

1. timeout/burst tối đa khi mở production panel;
2. thời gian tối đa chờ production slot rảnh;
3. TDHH thiếu Hồng/Tuyết recovery;
4. các unknown-error escalation cụ thể;
5. emergency restart/durable checkpoint chi tiết.
