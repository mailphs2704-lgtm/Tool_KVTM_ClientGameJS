# AUTO MULTI DEV — Function 3 Step 3 checkpoint

Date: 2026-09-14
Branch: `develop/multi-auto-dev`
Status: **STEP 2 LIVE PASS — STEP 3 SOURCE COMPLETE / BUILD+LIVE PENDING**

## Operator evidence before this checkpoint

Operator confirmed Function 3 Step 2 live PASS. The proven cumulative prefix is therefore:

```text
exact MAIN
→ Step 1 LIVE PASS
→ end floor 1
→ Step 2 LIVE PASS
→ 24 Tea on floor 2
→ 9/9 Apple Juice
→ repair
→ end floor 2
```

Step 3 must start from that exact floor-2 boundary without re-normalizing to MAIN.

## Operator-defined Step 3

```text
start: floor 2, exactly where Step 2 ended
→ shared planting Action on bottom row
   → harvest/check 6 bottom-row pots
   → reopen seed picker at verified first-pot hitbox
   → find Tea dynamically by template
   → replant only first 3 Tea pots
→ goUp(1) once to floor 3
→ shared Cotton planting Action
   → check/harvest PATH_27 = 4 visible rows + 1 hidden partial row
   → open picker at first pot
   → find cay_bong dynamically by template
   → plant 27 Cotton using existing verified PATH_27
→ remain floor 3
→ shared production path collects VP / opens Yellow Fabric panel
→ queue exactly 9/9 Yellow Fabric
→ shared MachineRepairActions
→ canonical floor_3_to_main_via_down_floor
   → goDown(1)
   → prove/click XUỐNG button
   → exact MAIN
→ goUp(1) once
→ end floor 1
→ Step 3 DONE
```

## Shared planting extension

`PlantingActions.harvest_and_replant_current_view(...)` now accepts optional `plant_count` while preserving all existing same-count callers.

```text
count       = harvest geometry/count
plant_count = replant geometry/count; defaults to count
```

New verified path:

```text
PATH_3 = START_POINT → (335,940) → (578,940)
```

This represents the first three pots of the bottom row. Function 3 Step 3 uses:

```text
count=6
plant_count=3
seed_template=cay_tra
```

The seed location remains dynamic. Page movement remains forbidden unless the seed-picker arrow template proves the picker is open.

## Step 3 source ownership

New Recipe:

```text
DriedTeaStepThreeRecipe.run_from_floor_2()
```

It composes only shared Actions/Recovery:

```text
PlantingActions
FloorNavigationActions
CottonPlantingActions
RecoveryManager.run_production
YellowFabricProductionActions
MachineRepairActions
FarmBoundaryRouteActions.floor_3_to_main_via_down_floor
```

No raw click/swipe coordinates are introduced in the Step 3 Recipe.

## Function 3 cumulative DEV gate

`FunctionThreeWorkflow.TOTAL_DEFINED_STEPS = 3`.

Added boundaries:

```text
run_step_3_from_floor_2()
run_steps_1_2_and_3()
```

The existing DEV compatibility mode/button still uses the historical `function-3-step-1` name, but the worker now runs the cumulative live gate:

```text
exact MAIN → Step 1 → Step 2 → Step 3 → end floor 1
```

Function 3 full `run()` remains fail-closed and is still not connected to AUTO Main because the operator has not finished defining the remaining Function 3 steps.

## Next gate

Run the authoritative build:

```text
KVTM_DEV_CONTROL.bat
→ [1] Cap nhat source + build runtime DEV
```

Only after build/static gates are clean, run the existing Function 3 DEV test once. Expected Step 3 evidence:

```text
thu/check bottom row 6
→ gieo Tea 3/3
→ goUp(1) floor 3
→ Cotton 27/27
→ Yellow Fabric 9/9
→ repair PASS
→ goDown(1)+XUỐNG exact MAIN
→ goUp(1)
→ end floor 1
```

Do not mark Step 3 runtime PASS until operator confirms live behavior/log evidence.
