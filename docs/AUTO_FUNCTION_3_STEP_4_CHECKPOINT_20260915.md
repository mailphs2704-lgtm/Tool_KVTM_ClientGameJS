# AUTO MULTI DEV — Function 3 Step 4 checkpoint

Date: 2026-09-15
Branch: `develop/multi-auto-dev`
Status: **STEP 4 SOURCE COMPLETE — BUILD/LIVE PENDING**

## Live regression carried into this step

Operator evidence from the Step 3 live run:

```text
ScreenTimeout: Cuối vòng Function 1: sau goDown(1) không xác minh/click được nút XUỐNG ở mép dưới
```

The failure was in the shared upper-floor → MAIN route, not in the preceding Step 3 planting/production sequence.

The shared fix is now in `FarmBoundaryRouteActions`:

```text
known_upper_floor_to_main_via_down_floor(...)
→ goDown(1)
→ try template-driven XUỐNG click
→ if template is missing or the detected click gives no response,
   use the already operator-marked fallback point (497,978)
→ require real frame response
→ mark exact MAIN only after verified response
```

`floor_3_to_main_via_down_floor()`, `floor_5_to_main_via_down_floor()` and `floor_6_to_main_via_down_floor()` all route through that shared primitive. No Function-specific raw click was added.

## Operator-defined Step 4

Entry state is the end of Step 3: **floor 1**.

```text
floor 1
→ shared harvest/replant Hồng 30 (5 rows)
→ goUp(4) + goUp(1)
→ floor 6
→ shared harvest/replant Hồng 15
   = full bottom row 6
   + full second row 6
   + first 3 pots of third row
→ goDown(1) + XUỐNG
→ exact MAIN
→ goUp(1)
→ floor 1
→ goUp(4)
→ floor 5
→ shared VP collect/open TDHH machine
→ queue exactly 9/9 Tinh dầu hoa hồng
→ shared machine repair
→ goDown(1) + XUỐNG
→ exact MAIN
→ goUp(1)
→ floor 1
→ Step 4 DONE
```

## Shared planting extension

`PlantingActions` now includes the verified 15-pot geometry:

```text
PATH_15:
START_POINT
→ (335,940) → (835,940)
→ (835,725) → (335,725)
→ (335,505) → (578,505)
```

This is exactly 6 + 6 + 3 pots from the first pot of the bottom row through the first three pots of row 3.

The existing dynamic seed contract remains unchanged:
- seed identity comes from template recognition;
- no absolute Hồng seed coordinate;
- page movement is allowed only after picker-arrow proof;
- the drag starts from the detected `match.center`.

## TDHH exact-count extension

`RoseOilProductionActions` keeps the existing Function 2 exact-7 contract and additionally exposes a Step-4 exact-9 transaction:

```text
produce_7_rose_oils(...)  # Function 2 unchanged
produce_9_rose_oils(...)  # Function 3 Step 4
```

Both use the same shared ProductionPanel engine, VP collection, slot verification, material shortage fail-close, and machine-repair handoff.

## Function 3 source boundary

`FunctionThreeWorkflow.TOTAL_DEFINED_STEPS = 4`.

Step 4 source entry:

```text
run_step_4_from_floor_1()
```

Cumulative currently-defined Function 3 source:

```text
exact MAIN → Step 1 → Step 2 → Step 3 → Step 4 → end floor 1
```

Full Function 3 `run()` remains fail-closed and is not connected to AUTO Main until the operator finishes defining all later steps.

## Verification gate

Do not mark Step 4 runtime PASS yet.

Authoritative next step:

```text
KVTM_DEV_CONTROL.bat
→ [1] Cap nhat source + build runtime DEV
```

After a clean build, run the existing Function 3 DEV cumulative test once and verify live evidence for:

```text
Step 3 down-floor shared fallback → exact MAIN
Step 4 Hồng 30
Step 4 Hồng 15
TDHH 9/9
repair
second down-floor shared route → exact MAIN
goUp(1) → floor 1
```

Build/static PASS and runtime PASS remain separate gates.
