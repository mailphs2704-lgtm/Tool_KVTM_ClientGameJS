# AUTO Function 3 — Step 6 checkpoint — 2026-09-15

## Operator evidence

- Step 5: **LIVE PASS** theo xác nhận trực tiếp của operator ngày 2026-09-15.
- Step 6: operator chốt đây là bước cuối của Function 3.
- Build/static PASS không thay cho Step 6 live/runtime evidence.

## Step 6 contract

Điểm vào: đúng boundary cuối Step 5, đứng ở tầng 1.

```text
tầng 1
→ shared harvest/replant: thu/check 30 chậu (5 hàng) và gieo lại 30 Hoa hồng
→ goUp(4) + goUp(1) lên tầng 6
→ shared harvest/replant: thu/check 6 chậu hàng cuối và gieo lại 6 Hoa hồng
→ goUp(2): click chậu đầu hàng 4 bằng primitive chuẩn để lên candidate tầng 8
→ shared VP collector mở panel sản xuất
→ tìm nuoc_hoa_hong trong panel an toàn; chỉ page khi panel-open đã được chứng minh
→ sản xuất đúng 9/9 Nước hoa hồng
→ Sửa máy
→ goDown(1)
→ dùng shared down-floor route hiện có: chờ 1.0s ổn định animation nút XUỐNG
→ click XUỐNG; template miss/no-response thì dùng operator-point fallback hiện có và vẫn bắt buộc frame response
→ exact MAIN
→ Function 3 DONE
```

## Source ownership

- Crop geometry/seed lookup: `PlantingActions` dùng `ROSE_TEMPLATE`, `PATH_30`, `PATH_6`; không hard-code vị trí seed.
- `goUp(2)`: `FloorNavigationActions.go_up(2)` với operator-marked `GO_UP_TWO_POT_POINT`; Recipe không raw click.
- Down-floor: `FarmBoundaryRouteActions.known_upper_floor_to_main_via_down_floor(...)`; giữ wait 1.0s đã live-PASS ở Step 5.
- Nước hoa hồng: `RoseWaterProductionActions`; dùng `ProductionPanelActions.collect_vp_before_machine_panel(...)`, exact 9/9, panel proof trước page-turn, warehouse-full typed path dùng shared engine.
- Recovery floor 8 được đăng ký trên cùng `RecoveryManager` của Function 3: MAIN→1→6→8 và tầng8→MAIN.

## Function 3 source state

`FunctionThreeWorkflow.TOTAL_DEFINED_STEPS = 6`.

Cumulative DEV compatibility gate `run_steps_1_2_and_3()` hiện delegate tới toàn bộ:

```text
Step 1 → Step 2 → Step 3 → Step 4 → Step 5 → Step 6 → exact MAIN
```

`run()` của Function 3 vẫn fail-close trước AUTO Main cho tới khi operator xác nhận Step 6 live PASS. Sau live PASS mới được nối Function 3 hoàn chỉnh vào AUTO Main/Builder production path.

## Next gate

Operator chạy đúng workflow dự án:

```text
KVTM_DEV_CONTROL.bat
→ [1] Cap nhat source + build runtime DEV
```

Sau build sạch, chạy nút DEV Function 3 hiện có một lần và xác nhận Step 6 bằng live behavior/log. Không gọi Step 6 PASS trước evidence đó.
