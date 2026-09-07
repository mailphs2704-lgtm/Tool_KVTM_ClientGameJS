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
    require(action, "AUTO_PRO_GO_UP_4_SWIPE = (387, 69, 387, 918)",
            "Exact Auto Pro goUp(4) swipe missing")
    require(action, "AUTO_PRO_GO_UP_3_POINT = (257, 191)",
            "Exact Auto Pro goUp(3) point missing")
    require(action, "def reference_main_to_floor_6(self)",
            "Auto Pro target-6 reference sequence missing")
    require(action, "duration=self.speed_config.plant_harvest_duration",
            "Auto Pro goUp(4) harvest-speed binding missing")
    require(action, "mốc live kỳ vọng=tầng 3",
            "Mode-4 live checkpoint missing")
    require(action, "goUp(4) → goUp(3)",
            "Target-6 command order missing")
    require(action, "chờ người vận hành xác nhận tầng 6",
            "Reference demo must not claim an absolute-floor PASS")
    if "FloorNavigationActions" in planting:
        raise AssertionError("Stable planting flow must not be rewritten by floor navigation")

    print("AUTO MULTI DEV FLOOR NAVIGATION STATIC CONTRACT VERIFIED")
    print("reference=auto_pro_goUp_1_and_exact_goUp_4")
    print("movement=stable_one_floor_primitive_plus_goUp_4_then_goUp_3_target_6")
    print("maximum_steps=5")
    print("pre_production_scan=fresh_frame_required")
    print("stable_planting=untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
