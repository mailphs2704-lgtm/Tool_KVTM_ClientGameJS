from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "components/clientjs-auto/kvtm_automation"
CONTEXT = CLEAN / "context.py"
POPUP = CLEAN / "actions/popup.py"
FUNCTION_NAV = CLEAN / "actions/function_one_navigation.py"
PASS_THREE_NAV = CLEAN / "actions/function_one_pass_three_navigation.py"
WORKER = ROOT / "components/clientjs-auto/worker/auto_multi_dev_worker.py"
FUNCTION_ONE = CLEAN / "workflows/auto_function_one/workflow.py"
WAREHOUSE = CLEAN / "workflows/production_warehouse_recovery.py"


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing main-boundary contract file: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(text, filename=str(path))
    return text


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def forbid(text: str, token: str, message: str) -> None:
    if token in text:
        raise AssertionError(message)


def main() -> int:
    context = read(CONTEXT)
    popup = read(POPUP)
    function_nav = read(FUNCTION_NAV)
    pass_nav = read(PASS_THREE_NAV)
    worker = read(WORKER)
    function_one = read(FUNCTION_ONE)
    warehouse = read(WAREHOUSE)

    # Exact-main is runtime state, not a world/background image classifier.
    require(context, "camera_exact_main_proven", "Runtime exact-main proof state missing")
    require(context, "camera_main_boundary_streak", "Main-boundary stable streak missing")
    require(context, "def invalidate_camera_main", "Camera proof invalidation API missing")
    require(context, "def mark_camera_exact_main", "Deterministic route proof API missing")
    require(context, "def observe_camera_down_boundary", "Behavioral boundary observer missing")

    require(popup, "def is_own_exact_main_screen", "Exact-main compatibility predicate missing")
    require(popup, "self.context.camera_exact_main_proven", "Exact-main predicate is not runtime-proof based")
    require(popup, "return self.is_own_main_screen()", "Exact-main must still require own-farm HUD")
    require(popup, 'invalidate_camera_main("ensure-farm-hud-camera-unknown")', "Farm recovery can carry stale camera proof")
    forbid(popup, "stall = self.vision.find(", "World-space stall image returned as exact-main runtime gate")
    forbid(popup, "return stall is not None", "Exact-main still depends on account background artwork")

    # Every normal vertical gesture invalidates old proof; only deterministic
    # routes ending at main may mark it true again.
    require(function_nav, "self.context.invalidate_camera_main", "Vertical gesture does not invalidate camera proof")
    require(function_nav, 'mark_camera_exact_main("floor1-to-main deterministic route")', "Floor1→main runtime proof missing")
    require(function_nav, 'mark_camera_exact_main("floor6-to-main deterministic route")', "Floor6→main runtime proof missing")

    # Unknown-state recovery must use repeated no-motion goDown evidence. Values
    # are locked to the live 2026-09-09 separation: movement 15.74/71.06 versus
    # boundary noise 2.53..2.94. Two consecutive lows prevent a single stale frame.
    require(pass_nav, "MAIN_BOUNDARY_MAX_CHANGE = 6.0", "Main-boundary change threshold changed")
    require(pass_nav, "MAIN_BOUNDARY_STABLE_REQUIRED = 2", "Main-boundary stable evidence count changed")
    require(pass_nav, "self.context.observe_camera_down_boundary(", "goDown boundary observer is not wired")
    require(pass_nav, "if exact and not was_exact:", "Boundary PASS transition guard missing")
    require(pass_nav, "không phụ thuộc background", "Background-independent policy marker missing")
    require(pass_nav, 'mark_camera_exact_main("floor2-to-main 1+3 deterministic route")', "Floor2→main deterministic proof missing")
    require(pass_nav, '"floor3-to-main-via-down-floor deterministic route"', "Floor3→main deterministic proof missing")

    # Existing worker/function recovery paths may keep calling the exact-main
    # predicate because that predicate is now runtime-proof based; ensure they do
    # not bypass it with the legacy quay_hang world anchor.
    require(worker, "_recover_auto_main_to_main_screen", "AUTO Main recovery helper missing")
    require(worker, "automation.popup.is_own_exact_main_screen()", "Worker no longer consumes runtime exact-main proof")
    require(function_one, "self.auto.popup.is_own_exact_main_screen()", "Function transitions no longer require exact-main proof")
    require(warehouse, "self.auto.popup.is_own_exact_main_screen()", "Warehouse recovery no longer requires exact-main proof")

    print("AUTO MULTI DEV MAIN BOUNDARY CONTRACT VERIFIED")
    print("own_farm=fixed_hud")
    print("exact_main=runtime_navigation_proof")
    print("unknown_camera=bounded_godown_until_two_low_change_frames")
    print("background_world_anchor=forbidden_as_runtime_gate")
    print("boundary_change_max=6.0")
    print("boundary_stable_required=2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
