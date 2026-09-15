# AUTO MULTI DEV — Function 3 Step 5 checkpoint

Date: 2026-09-15
Branch: `develop/multi-auto-dev`
Status: **STEP 4 LIVE PASS — STEP 5 SOURCE COMPLETE / BUILD+LIVE PENDING**

## Operator evidence

Operator confirmed Step 4 live PASS. Step 5 therefore starts exactly at the Step-4 boundary: **floor 1**.

## Step 5 operator contract

```text
start floor 1
→ shared harvest/replant current view
   → harvest/check 30 pots = 4 visible rows + hidden fifth row
   → open seed picker at first bottom pot
   → find cay_tuyet dynamically
   → plant 30 Snow
→ goUp(4) + goUp(1) → floor 6
→ shared harvest/replant current view
   → harvest/check bottom row 6 pots
   → plant 6 Snow
→ remain floor 6
→ shared VP collection / open production panel
→ scan paged panel for tra_da
→ only page-turn while panel-open proof is present
→ queue exactly 9/9 Trà đá
→ shared machine repair
→ shared floor-6 boundary route
   → goDown(1)
   → wait exactly 1.0s for down-button animation stabilization
   → detect/click XUỐNG; fixed operator-point fallback remains guarded by frame response
   → exact MAIN
→ goUp(1) → floor 1
→ Step 5 DONE
```

## Source ownership

- `actions/planting.py`: existing `PATH_30`, `PATH_6`, dynamic Snow seed lookup.
- `actions/iced_tea_production.py`: shared >=20 VP collector, panel proof, paged `tra_da` search, exact 9/9 queue.
- `actions/farm_routes.py`: shared known-upper-floor boundary route now waits 1.0s after goDown(1) before down-button click.
- `recipes/dried_tea_step_five.py`: Step-5 choreography only; no raw farm/machine coordinates.
- `workflows/auto_function_three/workflow.py`: `TOTAL_DEFINED_STEPS = 5`, isolated Step 5 and cumulative Step 1→5.

## Runtime gate

Do not mark Step 5 runtime PASS until operator build is clean and live logs prove:

```text
Snow 30/30
→ floor 6
→ Snow 6/6
→ tra_da found by paged panel scan
→ Trà đá 9/9
→ repair PASS
→ goDown(1)
→ explicit 1.0s settle
→ XUỐNG → exact MAIN
→ goUp(1)
→ end floor 1
```
