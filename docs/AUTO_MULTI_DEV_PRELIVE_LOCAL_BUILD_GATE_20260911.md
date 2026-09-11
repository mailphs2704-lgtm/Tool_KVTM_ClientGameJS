# AUTO MULTI DEV — PRE-LIVE LOCAL BUILD GATE — 2026-09-11

Repo: `mailphs2704-lgtm/Tool_KVTM_ClientGameJS`
Branch: `develop/multi-auto-dev`

## Local build evidence

Operator ran the authoritative flow:

```text
KVTM_DEV_CONTROL.bat
→ [1] Cap nhat source + build runtime DEV
```

Pull reached source HEAD `97f6a4ffb4ff4262447376f976146d0a14c5fbe1` and persistent-settings verification passed.

The build then stopped at:

```text
tools/verify_multi_dev_main_boundary_contract.py
AssertionError: Vertical gesture does not invalidate camera proof
```

This was diagnosed as a **stale static verifier**, not a runtime failure and not a package-output lock. Navigation ownership had already moved from the historical `function_one_navigation.py` implementation into canonical `FloorNavigationActions` + `FarmRouteActions`; the old verifier still required the implementation token inside the compatibility wrapper.

The final generic message telling the operator to close Multi/ClientJS was therefore not the root cause of this failure.

## Stale build-gate cleanup committed

The local package path still executes several historical verifiers, so the cleanup was expanded beyond the first failing assertion to prevent one-error-per-build churn.

Updated gates:

```text
cb02aae0  fix(auto): align main-boundary verifier with standardized architecture
13c5b274  fix(auto): align VP advertising verifier with five-view sale flow
2fe5f668  fix(auto): align floor-navigation verifier with semantic modes
afd4beef  fix(auto): align planting verifier with shared planting Actions
3dcc10ce  fix(auto): accept current Function 2 UI and catalog labels
6d8f5ad8  fix(auto): align Function 2 verifier with Recipe-based architecture
cfaf82b7  fix(auto): align Function 2 handoff verifier with known floor3 route
79cf2277  fix(auto): align AUTO Main sale verifier with five-view and 3h scheduler
33327100  fix(auto): compose production gate from standardized contracts
882ef3ad  fix(auto): align speed verifier with shared production panel engine
```

## Contracts now reflected by local build gates

### Navigation

```text
goUp(1) = short swipe
goUp(2) = pot-anchor semantic click
goUp(4) = long swipe
goUp(3) = unsupported/fail-close
```

Implementation owner:

```text
FloorNavigationActions
FarmRouteActions
FarmBoundaryRouteActions
```

Function-1 navigation files are compatibility wrappers only.

### Sale

```text
5 Views
per View: collect gold → QC → empty/list VP
next view = exactly two swipes
View 5 = final boundary/overlap check
Sale returns caller, not Scheduler-specific completion
```

Sale must consume an exact-main handoff and must not send hidden `goDown(1)` to manufacture MAIN.

### Function boundary / restart

Scheduled ClientJS restart is:

```text
10800s = 3h
```

Deadline during a Function is deferred until Function PASS, a safe sale is guaranteed at the boundary, then a dedicated `ClientRestartRequested` lifecycle signal is emitted.

### Planting

Canonical shared geometry:

```text
PATH_5
PATH_6
PATH_27
PATH_28
PATH_30
```

New code composes Navigation separately from current-view crop planting.

### Function 2 / TDHH

```text
Hồng = crop/material
Tuyết = crop/material
TDHH = finished VP
```

`function_two_planting.py` is compatibility-only. `RoseOilRecipe` owns business order using generic Navigation + Planting Actions and shared Function-2 RecoveryManager.

Function-2 inherited Vải vàng handoff is known floor 3:

```text
floor3 → RecoveryManager.to_main_from_floor(3) → exact-main
```

not unknown-camera recovery.

### Production

Shared panel/slot mechanics are owned by:

```text
ProductionPanelActions
```

Product transactions:

```text
ProductionActions             → Táo sấy
AppleJuiceProductionActions   → Nước táo
YellowFabricProductionActions → Vải vàng
RoseOilProductionActions      → TDHH
```

The speed verifier now checks x5 collection and settle/fresh-frame proof on `ProductionPanelActions`, not on the Táo-sấy transaction class.

## Gates intentionally left unchanged after audit

`verify_multi_dev_bridge_v3_contract.py` remains valid for the strict Bridge V3 contract (`CAPTURE3`, `INPUT4`, `BATCH_SWIPE`, `WRITERMAP2`, `WRITERMSG1`).

`verify_multi_dev_asset_contract.py` remains valid for self-contained Multi DEV assets and adaptive-resolution verification.

Builder core keeps historical Function-1 full-source/inspection strings because that document is read-only inspection metadata; they are not runtime ownership dependencies.

## Current status

```text
SOURCE: committed
LOCAL BUILD: previous attempt FAILED on stale verifier
RUNTIME: not tested
STATIC PASS: not yet claimed
```

Next authoritative action:

```text
KVTM_DEV_CONTROL.bat
→ [1] Cap nhat source + build runtime DEV
```

The next run must first pull the verifier-cleanup commits above. If the local build completes all static/package gates successfully, move to LIVE TEST smoke modules. If another verifier fails, treat the exact assertion as evidence and repair only the stale/real contract involved; do not bypass gates and do not call runtime PASS.
