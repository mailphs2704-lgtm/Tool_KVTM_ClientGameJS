from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "components/clientjs-auto/kvtm_automation/actions/floor_navigation.py"
AUTOMATION = ROOT / "components/clientjs-auto/kvtm_automation/automation.py"
ACTIONS_INIT = ROOT / "components/clientjs-auto/kvtm_automation/actions/__init__.py"
PLANTING = ROOT / "components/clientjs-auto/kvtm_automation/actions/planting.py"


def read_python(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    functions = sum(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for node in ast.walk(tree)
    )
    if path == ACTION and functions > 10:
        raise AssertionError("Floor navigation module exceeds ten functions")
    return text


def require(text: str, needle: str, message: str) -> None:
    if needle not in text:
        raise AssertionError(message)


def main() -> int:
    action = read_python(ACTION)
    automation = read_python(AUTOMATION)
    actions_init = read_python(ACTIONS_INIT)
    planting = read_python(PLANTING)

    require(action, "MAX_STEPS = 5", "Five-floor safety bound missing")
    require(action, "UP_SWIPE = (514, 214, 514, 314)",
            "AUTO PRO goUp(1) geometry missing")
    require(action, "DOWN_SWIPE = (514, 314, 514, 214)",
            "Symmetric one-floor down geometry missing")
    require(action, "for ordinal in range(1, requested + 1):",
            "Movement must execute one verified pulse per floor")
    require(action, "duration=self.speed_config.floor_swipe_duration",
            "Independent floor speed is not applied")
    require(action, "before = self.vision.frame().copy()",
            "Pre-movement fresh frame missing")
    require(action, "after = self.vision.frame().copy()",
            "Post-movement fresh frame missing")
    require(action, "if change < self.MIN_FRAME_CHANGE:",
            "No-response fail-closed guard missing")
    require(action, "dừng trước khi quét hoặc chọn máy sản xuất",
            "Production safety boundary missing")
    require(automation, "FloorNavigationActions(",
            "Floor navigation is not wired to resident automation")
    require(actions_init, "FloorNavigationActions",
            "Floor navigation export missing")
    if "goUp(4)" in action:
        raise AssertionError("Rejected multi-floor jump reintroduced")
    if "FloorNavigationActions" in planting:
        raise AssertionError("Stable planting flow must not be rewritten by floor navigation")

    print("AUTO MULTI DEV FLOOR NAVIGATION STATIC CONTRACT VERIFIED")
    print("reference=auto_pro_goUp_1")
    print("movement=one_floor_one_pulse")
    print("maximum_steps=5")
    print("pre_production_scan=fresh_frame_required")
    print("stable_planting=untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
