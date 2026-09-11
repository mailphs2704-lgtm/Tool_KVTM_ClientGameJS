from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "components/clientjs-auto/kvtm_automation/actions/floor_navigation.py"
FARM_ROUTES = ROOT / "components/clientjs-auto/kvtm_automation/actions/farm_routes.py"
AUTOMATION = ROOT / "components/clientjs-auto/kvtm_automation/automation.py"
ACTIONS_INIT = ROOT / "components/clientjs-auto/kvtm_automation/actions/__init__.py"
PLANTING = ROOT / "components/clientjs-auto/kvtm_automation/actions/planting.py"
PLANTING_WORKFLOW = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_planting/workflow.py"


def read_python(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing floor-navigation contract file: {path}")
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path))
    return text


def require(text: str, needle: str, message: str) -> None:
    if needle not in text:
        raise AssertionError(message)


def forbid(text: str, needle: str, message: str) -> None:
    if needle in text:
        raise AssertionError(message)


def main() -> int:
    action = read_python(ACTION)
    farm_routes = read_python(FARM_ROUTES)
    automation = read_python(AUTOMATION)
    actions_init = read_python(ACTIONS_INIT)
    planting = read_python(PLANTING)
    planting_workflow = read_python(PLANTING_WORKFLOW)

    # goUp integer is a semantic mode, not N repeated pulses.
    require(action, "GO_UP_ONE_SWIPE = (514, 214, 514, 314)",
            "goUp(1) geometry changed")
    require(action, "GO_UP_TWO_POT_POINT = (257, 191)",
            "goUp(2) floor-4 pot anchor changed")
    require(action, "GO_UP_FOUR_SWIPE = (387, 69, 387, 918)",
            "goUp(4) AUTO PRO geometry changed")
    require(action, "GO_DOWN_ONE_SWIPE = (514, 314, 514, 214)",
            "goDown(1) geometry changed")
    require(action, "GO_DOWN_FOUR_SWIPE = (387, 918, 387, 69)",
            "goDown(4) geometry changed")
    require(action, "def go_up(self, mode: int", "Semantic go_up dispatcher missing")
    require(action, "elif selected == 2:", "goUp(2) semantic branch missing")
    require(action, "self.GO_UP_TWO_POT_POINT", "goUp(2) does not use pot anchor")
    require(action, "elif selected == 4:", "goUp(4) semantic branch missing")
    require(action, "elif selected == 3:", "goUp(3) explicit unsupported branch missing")
    require(action, "goUp(3) chưa được operator định nghĩa", "goUp(3) fail-close marker missing")
    forbid(action, "for _ in range(selected)", "goUp(mode) regressed to repeated primitive pulses")

    # Every primitive invalidates old camera proof and verifies a fresh frame.
    require(action, "def _prepare_camera_input", "Camera-input preparation missing")
    require(action, "self.context.invalidate_camera_main", "Navigation no longer invalidates stale exact-main proof")
    require(action, "before = self.vision.frame().copy()", "Pre-movement fresh frame missing")
    require(action, "after = self.vision.frame().copy()", "Post-movement fresh frame missing")
    require(action, "if change < self.MIN_FRAME_CHANGE:", "No-response fail-close guard missing")
    require(action, "duration=self.speed_config.plant_harvest_duration", "Canonical primitive speed binding missing")

    # Explicit repeated one-floor compatibility sequences remain separate from
    # semantic goUp(mode), so old callers can still request UP/DOWN steps safely.
    require(action, "MAX_STEP_SEQUENCE = 8", "Compatibility step safety bound changed")
    require(action, "def move(self, direction: str, steps: int = 1)", "Compatibility move helper missing")
    require(action, "for ordinal in range(1, requested + 1):", "Compatibility move does not verify each one-floor pulse")
    require(action, 'label=f"move-UP-one-{ordinal}-of-{requested}"', "Compatibility UP sequence is not explicit goUp(1)")

    # Target-6 demo is composition of canonical modes 1 -> 4 -> 1.
    require(action, "def reference_main_to_floor_6(self)", "Target-6 compatibility route missing")
    require(action, 'first = self.go_up(1, label="target6-goUp(1)-initial")', "Target-6 initial goUp(1) missing")
    require(action, 'middle = self.go_up(4, label="target6-goUp(4)")', "Target-6 goUp(4) missing")
    require(action, 'final = self.go_up(1, label="target6-goUp(1)-final")', "Target-6 final goUp(1) missing")
    require(action, "goUp(1) → goUp(4) → goUp(1) PASS", "Target-6 command order marker missing")

    # Business routes live in farm_routes.py. Standardized planting runtime must
    # compose Navigation separately. planting.py may retain a dormant LEGACY
    # compatibility wrapper during staged migration, but it must not import the
    # canonical Navigation class and the live isolated workflow must not call the
    # hidden-navigation legacy 27 wrappers.
    require(farm_routes, "class FarmRouteActions(FloorNavigationActions):", "Canonical farm route composer missing")
    require(farm_routes, "class FarmBoundaryRouteActions(FarmRouteActions):", "Boundary farm route composer missing")
    require(farm_routes, "self.go_up(2", "Farm route does not consume semantic goUp(2)")
    require(automation, "FloorNavigationActions(", "Floor navigation is not wired to resident automation")
    require(automation, "self.farm_routes = FarmRouteActions(", "Canonical farm route facade missing")
    require(actions_init, "FloorNavigationActions", "Floor navigation export missing")
    require(actions_init, "FarmRouteActions", "Farm route export missing")

    forbid(planting, "from .floor_navigation import", "Planting must not import canonical floor navigation")
    forbid(planting, "from .farm_routes import", "Planting must not import farm route choreography")
    require(planting, "def harvest_and_replant_current_view", "Current-view planting Action missing")
    require(planting_workflow, 'self.auto.floors.go_up(1, label="rose-plant-main-to-floor1")',
            "Live planting workflow must own Navigation separately")
    require(planting_workflow, "self.auto.planting.plant_current_view(",
            "Live planting workflow must use current-view planting Action")
    forbid(planting_workflow, "plant_27_roses()",
           "Live planting workflow regressed to legacy hidden-navigation wrapper")
    forbid(planting_workflow, "plant_27_apples()",
           "Live planting workflow regressed to legacy hidden-navigation wrapper")

    print("AUTO MULTI DEV FLOOR NAVIGATION STATIC CONTRACT VERIFIED")
    print("goUp_modes=1-swipe|2-pot-anchor|4-long-swipe|3-unsupported")
    print("camera_proof=invalidate-before-input+fresh-frame-postcheck")
    print("compat_move=explicit-one-floor-sequence")
    print("target6=goUp1+goUp4+goUp1")
    print("route_owner=farm_routes")
    print("planting_runtime=current-view-only+separate-navigation")
    print("planting_legacy_wrapper=dormant-compatibility-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
