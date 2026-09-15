# AUTO Function 3 — Step 4 TDHH material correction

Date: 2026-09-15
Branch: `develop/multi-auto-dev`

## Operator evidence / correction

Operator confirmed Step 5 live PASS, then identified one earlier Step 4 material-sequencing defect: the TDHH production phase was missing the required 36 Tuyết preparation after the 45 Hồng pass.

Corrected Step 4 boundary:

```text
start floor 1
→ Hồng 30
→ goUp(4)+goUp(1) floor 6
→ Hồng 15
→ total Hồng = 45
→ goDown(1)+wait 1s+XUỐNG exact MAIN
→ goUp(1) floor 1
→ Tuyết 30
→ goUp(4)+goUp(1) floor 6
→ Tuyết 6
→ total Tuyết = 36
→ goDown(1) only, floor 6 → floor 5
→ shared VP collect / TDHH panel
→ produce TDHH 9/9
→ repair
→ goDown(1)+wait 1s+XUỐNG exact MAIN
→ goUp(1) floor 1
→ Step 4 DONE
```

The old pre-production detour `floor6 → MAIN → floor1 → goUp(4) floor5` is removed after the Tuyết pass. Once the final 6 Tuyết are planted on floor 6, the TDHH machine is directly one `goDown(1)` below on floor 5.

## Source ownership

- `components/clientjs-auto/kvtm_automation/recipes/dried_tea_step_four.py`
  - adds shared PlantingAction Tuyết 30 + 6 before TDHH;
  - keeps dynamic `SNOW_TEMPLATE` seed lookup;
  - uses canonical `floor_6_to_main_via_down_floor()` after Hồng 45;
  - uses one canonical `go_down(1)` floor6→floor5 after Tuyết 36;
  - retains TDHH 9/9 + repair + floor5→MAIN + floor1 end boundary.
- `tools/verify_recipe_function_standardization_contract.py`
  - locks Hồng45 → MAIN/floor1 → Tuyết36 → direct floor6→floor5 → TDHH9 order;
  - forbids reintroducing `floor1_to_floor5()` before TDHH.

## PASS discipline

This correction is **SOURCE COMPLETE / BUILD+LIVE PENDING**. Existing Step 5 operator PASS remains evidence for Step 5 itself, but the cumulative Function 3 prefix must be live-tested again because Step 4 choreography changed before Step 5.
