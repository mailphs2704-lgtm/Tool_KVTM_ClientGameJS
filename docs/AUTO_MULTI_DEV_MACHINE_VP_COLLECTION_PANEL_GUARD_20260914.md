# AUTO MULTI DEV — Shared VP collection + page-turn guards

Date: 2026-09-14
Branch: `develop/multi-auto-dev`
Status: SOURCE UPDATED — LOCAL BUILD/LIVE RETEST PENDING

## Live evidence that triggered the fix

Function 3 Step 1 reached Trà sấy production with only one x5 machine-click burst, then started clicking the production-page arrow while no panel anchor had been proved (`empty_anchor=chưa thấy`). The operator stopped the run after repeated page clicks.

Operator contract superseding the old behavior:

- every production machine must use one shared VP-collection primitive;
- VP collection is hard minimum `4 x 5 = 20` clicks at the machine point before panel recognition may continue;
- product-specific Actions must not own their own smaller collect-click count;
- page-turn search is legal only after the relevant UI is proved open;
- seed picker may use its existing arrow template as open-panel proof;
- if panel proof is missing, never click a page arrow blindly.

## Source changes

### `ProductionPanelActions`

Canonical machine collector:

```text
collect_vp_before_machine_panel(...)
COLLECT_CLICK_BURST = 5
COLLECT_MIN_BURSTS = 4
COLLECT_MIN_CLICKS = 20
```

`_click_until_panel_open(...)` now runs this shared collector before each recognition round. Táo sấy, Nước táo, Vải vàng and TDHH already reach `_click_until_panel_open`; Nước táo direct floor probe was also routed through the same collector.

### Trà sấy

`DriedTeaProductionActions` no longer sends one private x5 burst.

```text
shared collect >=20
→ prove production panel by product anchor or empty-slot anchor
→ only then permit page-right click
→ if panel-open anchor disappears, do not turn page; wait/recheck
→ stop when tra_say template is found
```

### Shared planting / seed picker

Seed identity/location stays dynamic. Before every seed-picker page turn:

```text
find requested seed
→ MISS
→ prove picker open with template next_gieo_trai
→ only then click operator-defined right-page point
→ scan again
```

If the picker arrow cannot be proved after bounded rechecks, planting fails closed without a page click.

## Contract verifiers

- `verify_production_action_boundaries_contract.py` locks the shared >=20-click collector, removes direct product-level `_send_collect_burst(...)`, and locks Trà sấy panel proof before page movement.
- `verify_action_standardization_contract.py` locks dynamic seed location and `next_gieo_trai` proof before seed page movement.

## Commits

```text
48fcb0bd  fix(auto): harden shared VP collection to minimum 20 clicks
7262cdae  fix(auto): guard dried tea paging behind panel proof
7a0fa8f5  refactor(auto): route apple juice probe through shared VP collector
8139cf9c  fix(auto): guard seed paging behind picker proof
96a99b0e  test(auto): lock shared machine VP collection contract
5db3a995  test(auto): lock seed picker proof before page turn
```

## Next gate

Run the authoritative DEV update/build:

```text
KVTM_DEV_CONTROL.bat
→ [1] Cap nhat source + build runtime DEV
```

Then rerun Function 3 Step 1 live test. Expected log before any Trà sấy page turn must show shared collection reaches at least `20/20` and panel-open proof is present. Do not mark runtime PASS until operator confirms live behavior.
