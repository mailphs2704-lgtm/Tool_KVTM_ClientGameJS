# AUTO Function 3 — Step 2 checkpoint — 2026-09-14

Repo: `mailphs2704-lgtm/Tool_KVTM_ClientGameJS`  
Branch: `develop/multi-auto-dev`  
Status: **STEP 2 SOURCE COMPLETE — BUILD/LIVE PASS PENDING**

## Boundary

Step 1 remains the already live-verified boundary and must not be changed without live regression evidence.

Step 2 starts exactly where Step 1 ends: **floor 1**.

## Operator-defined Step 2

```text
end Step 1: floor 1
→ goUp(1)
→ floor 2
→ shared harvest/plant Action on the four visible rows
→ harvest 24 pots when RIPE
→ open the seed picker at the first pot on the lowest visible row
→ find `cay_tra` by template
→ if missing, click the fixed right-page arrow and scan again
→ stop paging only when the Tea template is found
→ drag from the detected template center, never from an absolute Tea coordinate
→ plant 24 Tea = 4 rows x 6
→ remain on floor 2
→ collect ready VP/open the floor-2 Apple Juice machine through the shared production Action
→ queue exactly 9/9 Apple Juice
→ repair machine
→ remain on floor 2
→ Step 2 DONE
```

## Dynamic seed-location contract

The seed/item order and positions inside the picker may differ by account/session. This rule is global for planting, not Tea-specific:

- crop identity is recognized by template;
- crop/seed absolute coordinates are forbidden;
- only the picker right-page arrow has a fixed operator-marked click point;
- after every page move, scan again;
- once found, `match.center` becomes the drag start;
- shared farm geometry remains fixed/verified separately from seed identity.

Current shared planting geometry includes `PATH_24` in addition to the existing 5/6/27/28/30 paths.

## Source ownership

- `actions/planting.py`: shared 24-pot geometry + dynamic seed paging/template center.
- `recipes/dried_tea_step_two.py`: Step 2 choreography only.
- `actions/apple_juice_production.py`: floor-2 machine, ready-VP collection/panel proof, exact 9/9 Apple Juice production.
- `actions/machine_repair.py`: shared repair Action.
- `workflows/auto_function_three/workflow.py`: exposes isolated Step 2 and cumulative Step 1+2 composition with one Function-3 RecipeBook/RecoveryManager.

Step 2 deliberately does not add raw machine clicks in the Recipe. `AppleJuiceProductionActions.produce_9_apple_juices(close_after_success=False)` owns the verified machine/panel path, including collection of ready VP before queueing the new batch, then hands the open panel to the shared repair Action.

## Current Function 3 state

`FunctionThreeWorkflow.TOTAL_DEFINED_STEPS = 2`.

Available source boundaries:

```text
run_step_1()                 → Step 1 only, end floor 1
run_step_2_from_floor_1()    → Step 2 only, assumes Step-1 boundary, end floor 2
run_steps_1_and_2()          → exact MAIN → Step 1 → Step 2, end floor 2
```

The full `run()` remains fail-closed and Function 3 is **not** connected to AUTO Main yet because later Function 3 work has not been defined.

## Verification status

Do not call Step 2 runtime PASS yet. Source is complete from the operator description, but Windows DEV build and live behavior still need operator evidence.
