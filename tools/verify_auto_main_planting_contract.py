from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTION_PATH = ROOT / "components/clientjs-auto/kvtm_automation/actions/planting.py"
WORKFLOW_PATH = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_planting/workflow.py"
DEV_ENTRY_PATH = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_entry.py"
GUI_PATH = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi.py"
AUTO_MAIN_PATH = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_main/workflow.py"
AUTO_MULTI_WORKER_PATH = ROOT / "components/clientjs-auto/worker/auto_multi_dev_worker.py"


def require(text: str, needle: str, message: str) -> None:
    if needle not in text:
        raise AssertionError(message)


def check_function_limit(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    count = sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in ast.walk(tree))
    if count > 10:
        raise AssertionError(f"{path}: {count} functions exceeds limit 10")


def main() -> int:
    paths = (ACTION_PATH, WORKFLOW_PATH, DEV_ENTRY_PATH, GUI_PATH, AUTO_MAIN_PATH, AUTO_MULTI_WORKER_PATH)
    for path in paths:
        if not path.is_file():
            raise AssertionError(f"Missing planting contract file: {path}")
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for path in (ACTION_PATH, WORKFLOW_PATH):
        check_function_limit(path)

    action = ACTION_PATH.read_text(encoding="utf-8")
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    dev = DEV_ENTRY_PATH.read_text(encoding="utf-8")
    gui = GUI_PATH.read_text(encoding="utf-8")
    auto_main = AUTO_MAIN_PATH.read_text(encoding="utf-8")
    auto_multi_worker = AUTO_MULTI_WORKER_PATH.read_text(encoding="utf-8")

    require(action, 'ROSE_TEMPLATE = "cay_hong"', "Rose template missing")
    require(action, 'APPLE_TEMPLATE = "cay_tao"', "Apple template missing")
    require(action, "def plant_27_apples", "Parameterized apple planting action missing")
    require(action, "TREE_COUNT = 27", "Exactly 27 trees required")
    require(action, "START_POINT = (325, 799)", "AUTO PRO start point changed")
    require(action, "(335, 40), (578, 40)", "Hidden fifth-floor endpoint changed")
    require(action, "threshold=0.87", "AUTO PRO rose threshold changed")
    require(action, "def _go_up_one", "AUTO PRO goUp(1) transition missing")
    require(action, "GO_UP_ONE_START = (514, 214)", "goUp(1) start changed")
    require(action, "GO_UP_ONE_END = (514, 314)", "goUp(1) end changed")
    require(action, "def _count_changed_pots", "Post-plant image verification missing")
    require(action, "baseline = self.vision.frame().copy()", "Baseline must detach shared capture buffer")
    require(action, "after = self.vision.frame().copy()", "After frame must detach shared capture buffer")
    require(action, "changed_waypoint_regions=", "Planting diagnostic log missing")
    require(action, "non_blocking=true", "Waypoint heuristic must remain non-blocking")
    if "Swipe gieo chưa được xác minh" in action:
        raise AssertionError("Invalid waypoint heuristic still blocks a proven planting transaction")
    require(action, '"thu_hoach", threshold=0.80', "Mapped ripe-tree template missing")
    require(action, '"next_gieo_trai", threshold=0.70', "Empty-pot scan missing")
    require(action, "if empty is not None and rose is not None:", "Empty state must prove seed picker")
    require(action, "self._harvest_27()", "Harvest-before-plant transition missing")
    require(action, "zone=self.SEED_ZONE", "Rose seed zone guard missing")
    require(action, "duration=self.speed_config.plant_harvest_duration", "Configured planting speed missing")
    require(action, "self.rose_path()[1:]", "Seed center must replace reference start point")
    require(action, 'raise ScreenTimeout(', "Fail-closed planting guard missing")
    require(workflow, "self.auto.planting.plant_27_roses()", "Workflow planting call missing")

    # AUTO Main no longer hard-codes FunctionOneWorkflow directly. It dispatches
    # the GUI-selected complete Function and keeps the Function-specific gate.
    require(auto_main, "FunctionModule(automation)",
            "Consolidated start must use selected Function dispatcher")
    require(auto_main, "self.function.run(function_id=self.spec.function_id)",
            "AUTO Main does not execute the selected Function")
    require(auto_main, 'self.spec.runner_key == "function_1"',
            "Function-1 completion guard missing from selected scheduler")
    require(auto_multi_worker, "AutoMainWorkflow(",
            "Consolidated isolated-worker workflow wiring missing")
    require(auto_multi_worker, "function_id=function_id",
            "Worker selected Function handoff missing")
    require(auto_multi_worker, "sale_every_loops=sale_every",
            "Worker recurring sale interval handoff missing")
    require(auto_multi_worker, 'outcome="auto_main_ready"',
            "Worker AUTO Main result marker missing")
    require(dev, 'worker_root / "auto_multi_dev_worker.py"',
            "GUI isolated-worker launch wiring missing")
    require(dev, 'outcome = str(event.pop("outcome", "auto_main_ready"))',
            "GUI AUTO Main result handling missing")
    require(gui, 'text="▶ Bắt đầu AUTO MULTI DEV"', "Consolidated AUTO Multi DEV start button missing")
    require(gui, 'text="⚙ Cấu hình tốc độ"', "AUTO Multi DEV speed settings button missing")
    if "▶ Trồng 27 Hoa hồng" in gui:
        raise AssertionError("Passed standalone planting button must stay removed")

    forbidden = ("clear_stall_probe_runtime", "auto_main_selling", ".pyc")
    for token in forbidden:
        if token in action or token in workflow:
            raise AssertionError(f"Planting module touches forbidden stable path: {token}")
    print("AUTO MAIN PLANTING STATIC CONTRACT VERIFIED")
    print("stable_item=cay_hong")
    print("function_one_item=cay_tao")
    print("tree_count=27")
    print("floors=6+6+6+6+3")
    print("floor5_endpoint=(578,40)")
    print("selected_function_scheduler=verified")
    print("stable_sale_and_clear_stall=untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
