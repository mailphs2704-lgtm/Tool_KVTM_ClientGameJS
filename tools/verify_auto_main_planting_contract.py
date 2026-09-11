from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTION_PATH = ROOT / "components/clientjs-auto/kvtm_automation/actions/planting.py"
WORKFLOW_PATH = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_planting/workflow.py"
FLOOR_PATH = ROOT / "components/clientjs-auto/kvtm_automation/actions/floor_navigation.py"
DEV_ENTRY_PATH = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_entry.py"
GUI_PATH = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi.py"
AUTO_MAIN_PATH = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_main/workflow.py"
AUTO_MULTI_WORKER_PATH = ROOT / "components/clientjs-auto/worker/auto_multi_dev_worker.py"


def require(text: str, needle: str, message: str) -> None:
    if needle not in text:
        raise AssertionError(message)


def forbid(text: str, needle: str, message: str) -> None:
    if needle in text:
        raise AssertionError(message)


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing planting contract file: {path}")
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path))
    return text


def main() -> int:
    action = read(ACTION_PATH)
    workflow = read(WORKFLOW_PATH)
    floor = read(FLOOR_PATH)
    dev = read(DEV_ENTRY_PATH)
    gui = read(GUI_PATH)
    auto_main = read(AUTO_MAIN_PATH)
    auto_multi_worker = read(AUTO_MULTI_WORKER_PATH)

    # Shared crop identity is independent from verified geometry.
    require(action, 'ROSE_TEMPLATE = "cay_hong"', "Rose template missing")
    require(action, 'APPLE_TEMPLATE = "cay_tao"', "Apple template missing")
    require(action, 'SNOW_TEMPLATE = "cay_tuyet"', "Snow template missing")
    for token in ("PATH_5 = (", "PATH_6 = (", "PATH_27 = (", "PATH_28 = (", "PATH_30 = ("):
        require(action, token, f"Shared planting geometry missing: {token}")
    require(action, "VERIFIED_PATHS = {", "Verified planting path table missing")
    require(action, "5: PATH_5", "PATH_5 not registered")
    require(action, "6: PATH_6", "PATH_6 not registered")
    require(action, "27: PATH_27", "PATH_27 not registered")
    require(action, "28: PATH_28", "PATH_28 not registered")
    require(action, "30: PATH_30", "PATH_30 not registered")
    require(action, "def path_for_count", "Shared planting path selector missing")
    require(action, "Chưa có planting path được xác minh", "Unknown planting count must fail-close")

    # Current-view Action owns recognition + batch swipe only. Navigation is a
    # separate caller responsibility for new code.
    require(action, "def harvest_and_replant_current_view", "Current-view planting Action missing")
    require(action, "seed_template: str", "Crop template parameter missing")
    require(action, "count: int", "Planting count parameter missing")
    require(action, '"thu_hoach", threshold=0.80', "Ripe-tree proof missing")
    require(action, '"next_gieo_trai", threshold=0.70', "Empty-pot proof missing")
    require(action, "threshold=0.87", "Seed recognition threshold changed")
    require(action, "self.vision.driver.swipe_points(", "BATCH_SWIPE planting primitive missing")
    require(action, "duration=self.speed_config.plant_harvest_duration", "Configured planting speed missing")
    require(action, "plant_path = (match.center,) + tuple(selected_path[1:])", "Seed center does not replace reference start")
    require(action, "PlantingSegmentResult", "Planting evidence result missing")
    require(action, "raise ScreenTimeout(", "Fail-close planting guard missing")

    # Legacy 27 wrappers may remain for compatibility, but isolated workflow and
    # standardized recipes must compose Navigation + current-view planting.
    require(workflow, "self.auto.popup.is_own_exact_main_screen()", "Planting workflow exact-main precondition missing")
    require(workflow, 'self.auto.floors.go_up(1, label="rose-plant-main-to-floor1")', "Planting workflow does not use Navigation Action")
    require(workflow, "self.auto.planting.plant_current_view(", "Planting workflow does not use current-view Action")
    require(workflow, "count=27", "Isolated rose workflow target changed")
    forbid(workflow, "plant_27_roses()", "Workflow regressed to legacy hidden-navigation planting wrapper")
    require(floor, "def go_up(self, mode: int", "Shared Navigation Action missing")

    # AUTO Main remains selected-Function driven through the isolated worker.
    require(auto_main, "FunctionModule(automation)", "Selected Function dispatcher missing")
    require(auto_main, "self.function.run(function_id=self.spec.function_id)", "AUTO Main does not execute selected Function")
    require(auto_multi_worker, "AutoMainWorkflow(", "Isolated worker AUTO Main wiring missing")
    require(auto_multi_worker, "function_id=function_id", "Worker selected Function handoff missing")
    require(auto_multi_worker, "sale_every_loops=sale_every", "Worker sale interval handoff missing")
    require(auto_multi_worker, 'outcome="auto_main_ready"', "Worker AUTO Main terminal marker missing")
    require(dev, 'worker_root / "auto_multi_dev_worker.py"', "GUI isolated-worker launch wiring missing")
    require(gui, 'text="▶ Bắt đầu AUTO MULTI DEV"', "AUTO Multi DEV start button missing")
    require(gui, 'text="⚙ Cấu hình tốc độ"', "AUTO speed settings button missing")
    forbid(gui, "▶ Trồng 27 Hoa hồng", "Standalone legacy planting button returned")

    for token in ("clear_stall_probe_runtime", ".pyc"):
        forbid(action, token, f"Planting Action touches forbidden stable/legacy path: {token}")
        forbid(workflow, token, f"Planting workflow touches forbidden stable/legacy path: {token}")

    print("AUTO MAIN PLANTING STATIC CONTRACT VERIFIED")
    print("crops=rose+apple+snow")
    print("shared_paths=5,6,27,28,30")
    print("action=current-view-recognize+harvest/replant")
    print("navigation=separate-semantic-action")
    print("isolated_rose=exact-main->goUp1->plant-current-view-27")
    print("selected_function_scheduler=verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
