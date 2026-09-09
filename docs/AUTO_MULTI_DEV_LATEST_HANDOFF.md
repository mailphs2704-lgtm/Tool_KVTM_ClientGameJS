# AUTO MULTI DEV — LATEST HANDOFF

Cập nhật: 2026-09-09

Đây là **tài liệu đọc đầu tiên** khi một AI khác tiếp nhận branch `develop/multi-auto-dev`.

## 1. Trạng thái đã chốt với operator

Các mốc hiện tại:

- Function 1: runtime đã chạy nhiều vòng và được operator chốt PASS qua các lần sửa gần đây.
- Sale VP: PASS baseline; không thay đổi nếu không có regression evidence.
- QC/Quảng cáo VP: LIVE PASS.
- Recovery/Event/Error architecture: PASS.
- Recipe architecture: đang được Function 1 sử dụng thực tế; không quay lại copy production/recovery vào Function.
- exact-main đa background: PASS theo runtime-navigation proof, không dùng world/background anchor làm gate.
- visual nút `XUỐNG` upper-floor: đang dùng detector bottom-edge; không blind click tọa độ cũ.
- WrongProductionMachine recovery: đã sửa case mở nhầm máy rồi click thu VP vô hạn.
- Friend refresh chống item treo: source hoàn tất, operator đã PASS runtime sau fix circular import.
- Periodic ClientJS restart: **test 60 giây đã PASS**, đã promote production interval lên **7200 giây = 2 giờ**.
- Runtime: isolated worker + Bridge V3/CAPTURE3 ownership.
- Persistent settings: `%APPDATA%\KVTM Multi DEV`; rebuild không overwrite operator values.

## 2. Kiến trúc chuẩn

Luồng source chuẩn:

```text
Function
  → RecipeBook
    → Product Recipe
      → Atomic Action
      + RecoveryManager
```

Không được trộn vai trò:

- `errors.py`: typed signal/error only;
- `recovery/`: policy điều hướng/sai máy/kho đầy;
- `recipes/`: quy trình reusable cho từng VP;
- `actions/`: click/gesture/production primitive;
- `workflows/auto_function_*`: business composition của Function;
- `workflows/auto_main`: scheduler chung giữa Function/sale/maintenance/restart.

## 3. Recovery architecture

Package:

```text
components/clientjs-auto/kvtm_automation/recovery/
```

Các file chính:

- `events.py` — typed recovery events;
- `navigation.py` — exact-main/unknown/floor routes;
- `production.py` — `WrongProductionMachine` + `InventoryFull` policy;
- `manager.py` — facade mà Recipe/Function dùng.

Nguyên tắc quan trọng:

- generic `ScreenTimeout` **không** được blind retry;
- sai máy → đóng panel → camera unknown → exact-main → requested floor → retry có giới hạn;
- kho đầy → về exact-main → sale VP theo Function → requested floor → retry;
- Function sau có thể inject route/event handler riêng qua `RecoveryManager` thay vì copy recovery code.

Chi tiết: `docs/AUTO_MULTI_DEV_RECOVERY_ARCHITECTURE.md`.

## 4. Recipe architecture

Package:

```text
components/clientjs-auto/kvtm_automation/recipes/
```

Hiện có:

- `dried_apple.py`;
- `apple_juice.py`;
- `yellow_fabric.py`;
- `book.py`.

`RecipeBook(function_id=...)` dùng shared `RecoveryManager` của Function.

### AppleJuiceRecipe

Standalone từ main:

```python
recipes.apple_juice.run_from_main(count=9)
```

Function 1 dùng đường nhanh:

```python
recipes.apple_juice.run_from_candidate_floor_2(count=9)
```

Candidate floor2 từ movement không tự được tin. Recipe vẫn probe `nuoc_tao`; probe Nước táo hiện bounded tối đa **4 burst x5 = 20 click** để tránh false MISS sau chỉ 10 click. Nếu thấy anchor máy khác thì fail fast sang wrong-machine recovery.

### YellowFabricRecipe

Khi đang known floor2 sau Nước táo:

```python
recipes.yellow_fabric.run_after_floor_2(count=9)
```

Standalone có dependency explicit:

```python
recipes.yellow_fabric.run_from_main(
    count=9,
    include_apple_juice_dependency=True,
)
```

`include_apple_juice_dependency=False` không được tự sản xuất Nước táo.

Chi tiết: `docs/AUTO_MULTI_DEV_RECIPE_ARCHITECTURE.md`.

## 5. Function 1 current business flow

Function 1 hiện ghép nghiệp vụ thay vì nhúng recovery:

1. `DriedAppleRecipe.run_from_session(count=9)`;
2. supply Táo qua 5 tầng + trồng thêm tầng 6;
3. tầng 6 → `goDown(4)` tạo candidate tầng 2;
4. `AppleJuiceRecipe.run_from_candidate_floor_2(count=9)`;
5. `YellowFabricRecipe.run_after_floor_2(count=9)`;
6. normalize cuối vòng về exact-main;
7. PASS 3/3.

Function 1 không được gọi trực tiếp production/recovery đã thuộc Recipe/RecoveryManager.

## 6. Route và floor proof đã sửa theo live evidence

### Nước táo

Sau trồng Táo tầng 6:

```text
floor6
→ goDown(4)
→ candidate floor2
→ probe nuoc_tao
→ đúng: sản xuất ngay
→ sai: close panel → exact-main → floor2 → retry
```

Không đi vòng xuống main rồi lên lại floor2 nếu direct route đã đúng.

### Vải vàng

Live correction:

- `(257,416)` chỉ đưa tới tầng 2 trong state runtime đã test;
- floor1 → floor3 dùng click chậu tầng 4 `(257,191)`;
- movement vẫn không tự prove floor3; production phải thấy đúng `vai_vang`.

## 7. Shared production panel rule

Sau burst x5 bắt buộc:

```text
x5 raw click
→ vp_collect_delay
→ fresh frame
→ panel_state(frame)
→ target/wrong-machine scan trên cùng frame
```

Known product anchors:

- `tao_say`;
- `nuoc_tao`;
- `vai_vang`.

Nếu cần `vai_vang` nhưng thấy `nuoc_tao`, phải phát `WrongProductionMachine`, không được tiếp tục x5 vô hạn.

## 8. exact-main contract

Không phụ thuộc background/account farm skin.

- fixed own-farm HUD chỉ chứng minh own farm;
- exact-main = runtime navigation proof;
- unknown camera → bounded `goDown`;
- boundary fallback = 2 low-change frame liên tiếp;
- `MAIN_BOUNDARY_MAX_CHANGE = 6.0`;
- `MAIN_BOUNDARY_STABLE_REQUIRED = 2`;
- upper-floor recovery dùng visual `XUỐNG` và click `match.center`;
- không blind click `(497,978)`;
- chain upper-floor recovery tối đa 10 bước.

## 9. QC/Quảng cáo VP — LIVE PASS

Mỗi sale duyệt 3 checkpoint gần physical slot `1 / 10 / 20`:

- slot có dấu QC đỏ → skip, không click;
- slot chưa QC → mở listing;
- nút QC xanh miễn phí hồi → click;
- cooldown → đóng X;
- không click quảng cáo kim cương;
- quầy full vẫn chạy checkpoint QC;
- QC failure non-blocking.

Không regression phần này khi làm Function/cleanup.

## 10. Friend refresh chống item treo

Workflow chung:

```text
workflows/auto_main/friend_refresh.py
```

GUI AUTO MULTI DEV có persistent toggle:

```text
LÀM MỚI ITEM TREO
[ Qua bạn #1 / 3 vòng ]
```

Khi bật:

```text
sau Function loop 3 / 6 / 9 / ...
→ nếu cùng boundary có sale thì sale/QC trước
→ go_to_friend(1)
→ chờ scene settle
→ return_home()
→ re-prove exact-main
→ tiếp tục vòng kế
```

Workflow reuse navigation/assets của Dọn quầy nhưng **không** mở quầy bạn, không mua VP, không chạy Clear Stall business logic.

Đã từng có circular import:

```text
recovery → auto_builder.__init__ → runner → FunctionOne → recipes → recovery
```

Đã fix bằng lazy import trong `workflows/auto_builder/__init__.py`. Không được đưa eager import `runner` trở lại package init.

Chi tiết: `docs/AUTO_MULTI_DEV_FRIEND_REFRESH.md`.

## 11. Periodic ClientJS restart — PRODUCTION 2H

Test 60 giây đã PASS. Production hiện khóa:

```text
AutoMainWorkflow.CLIENT_RESTART_INTERVAL_SECONDS = 7200.0
_CLIENT_RESTART_INTERVAL_SECONDS = 7200.0
```

Safe flow:

```text
2h đến hạn
→ nếu đang giữa Function: defer
→ hoàn thành đủ vòng theo sale_every_loops
→ sale VP + QC PASS và đóng quầy
→ ClientRestartRequested
→ worker cooperative stop
→ Multi đóng đúng ClientJS/profile
→ chờ old supervisor thread chết
→ relaunch đúng profile ClientJS
→ worker mới + Bridge V3 generation mới
→ game session + exact-main
→ skip_initial_sale_once=true
→ vào Function tiếp theo
```

Không restart giữa planting/production/sale transaction.

Không được bỏ guard:

```text
old_thread.is_alive()
```

vì supervisor cũ có thể cleanup ownership map sau callback GUI.

Operator Stop trong pending restart phải hủy pending/relaunch config.

Chi tiết: `docs/AUTO_MULTI_DEV_CLIENT_RESTART.md`.

## 12. Build/static contracts

Operator build:

```text
KVTM_DEV_CONTROL.bat
→ [1] Cap nhat source + build runtime DEV
```

Các gate quan trọng gồm:

- persistent settings;
- main boundary;
- VP advertising;
- Clear Stall;
- AUTO Builder;
- VP Sale;
- planting;
- speed config;
- floor navigation;
- Bridge V3;
- production;
- Recipe architecture;
- Recovery architecture;
- asset/package checks.

VP sale contract hiện phải in:

```text
client_restart=2h+defer-until-function-sale-boundary+same-profile-relaunch
client_restart_resume=skip-duplicate-initial-sale+new-worker+new-bridge-generation
```

## 13. Packaging input hiện tại

`packaging/suite-v0.15/BUILD_FULL_PACKAGE.ps1` vẫn lấy production package từ 5 path:

```text
source-archive/auto-pro-reference
source-archive/multi-current/kvtm_multi_tool
test-candidates/auto-pro-clientjs-temp
bridge-v3
components/clientjs-auto
```

Vì vậy **không được xóa `source-archive` hoặc `test-candidates` theo tên folder**. Hai nơi này vẫn có production inputs thật.

## 14. Kế hoạch dọn dẹp/chuẩn hóa repo — CHƯA THỰC HIỆN

Có branch riêng:

```text
maintenance/repo-cleanup-packaging
```

Branch này hiện đứng ở snapshot cũ, trước nhiều thay đổi runtime mới. Trước khi cleanup phải rebase/recreate từ HEAD develop mới nhất.

Không thực hiện destructive cleanup trên `develop/multi-auto-dev`.

Tài liệu bắt buộc đọc:

```text
docs/PROJECT_CLEANUP_PACKAGING_PLAN.md
```

Mục tiêu dài hạn:

```text
src/multi
src/clientjs-auto
native/bridge-v3
vendor/auto-pro-reference
vendor/auto-pro-clientjs-runtime
packaging/suite-v0.15
tools/verify
tools/diagnostics
tools/ops
docs
tests
```

Tên folder có thể điều chỉnh sau dependency audit; nguyên tắc là mỗi production component chỉ có một authoritative location và builder không lấy production source từ path mang nghĩa `test-candidates`.

### Cleanup phải theo stage

1. snapshot + dependency inventory, chưa xóa;
2. ignore/generated artifact hygiene;
3. relocate từng authoritative component + update callers;
4. normalize packaging inputs;
5. chỉ xóa prototype/legacy khi zero refs;
6. full static/build/smoke trước merge.

Các path như `KVTM_DON_QUAY_SAFE.bat`, `ai-don-quay/step1_probe.py`, `test-candidates/function-builder-core` chỉ là **candidate**, không được xóa trước dependency search.

`KVTM_DEV_CONTROL.bat` là operator entry quan trọng; nếu move root scripts phải update caller cùng commit.

## 15. Không được regression

- đưa production/recovery logic trở lại Function;
- generic `ScreenTimeout` blind retry;
- background/world landmark làm exact-main gate;
- blind click nút XUỐNG;
- dùng `(257,416)` cho route Vải vàng hiện tại;
- panel sai machine tiếp tục x5 vô hạn;
- AppleJuice candidate probe quay về giới hạn 2 burst khi chưa có evidence;
- QC click slot đã có quảng cáo;
- QC click quảng cáo kim cương;
- friend refresh mở quầy/mua VP;
- eager-import AutoBuilder runner từ package init làm circular import;
- restart ClientJS giữa Function/sale;
- restart tất cả account khi chỉ một profile đến hạn;
- duplicate sale ngay sau ClientJS restart;
- thay đổi Dọn quầy/Bridge V3/persistent settings trong cleanup không có evidence.

## 16. Read-first cho AI tiếp theo

Theo thứ tự:

1. `docs/AUTO_MULTI_DEV_LATEST_HANDOFF.md`
2. `docs/AUTO_MULTI_DEV_CLIENT_RESTART.md`
3. `docs/AUTO_MULTI_DEV_FRIEND_REFRESH.md`
4. `docs/AUTO_MULTI_DEV_RECIPE_ARCHITECTURE.md`
5. `docs/AUTO_MULTI_DEV_RECOVERY_ARCHITECTURE.md`
6. `docs/AUTO_MULTI_DEV_FUNCTION_ONE.md`
7. `docs/PROJECT_CLEANUP_PACKAGING_PLAN.md`
8. `components/clientjs-auto/kvtm_automation/workflows/auto_main/workflow.py`
9. `components/clientjs-auto/kvtm_automation/workflows/auto_main/friend_refresh.py`
10. `components/clientjs-auto/kvtm_automation/recipes/book.py`
11. `components/clientjs-auto/kvtm_automation/recovery/manager.py`
12. `source-archive/multi-current/kvtm_multi_tool/auto_builder_integration.py`
13. `components/clientjs-auto/worker/auto_multi_dev_worker.py`
14. `tools/verify_auto_main_sale_contract.py`
15. `tools/verify_auto_main_production_contract.py`
16. `packaging/suite-v0.15/BUILD_FULL_PACKAGE.ps1`
17. `packaging/suite-v0.15/BUILD_FULL_PACKAGE_PS51.ps1`
18. `KVTM_DEV_CONTROL.bat`

## 17. Quy tắc làm việc cho phiên tiếp theo

- Runtime regression: sửa trên `develop/multi-auto-dev`, commit nhỏ, build `[1]`, live-test.
- Cleanup/relocation: chỉ trên `maintenance/repo-cleanup-packaging` đã cập nhật từ develop mới.
- Không trộn cleanup với feature/runtime fix.
- Sau mọi thay đổi architecture/path, cập nhật static contract trước khi coi là hoàn tất.
- Khi operator nói PASS, cập nhật handoff/documentation ngay để phiên AI tiếp theo không dùng trạng thái cũ.
