from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTION_PATH = ROOT / "components/clientjs-auto/kvtm_automation/actions/planting.py"
WORKFLOW_PATH = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_planting/workflow.py"
DEV_ENTRY_PATH = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_entry.py"
GUI_PATH = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi.py"


def require(text: str, needle: str, message: str) -> None:
    if needle not in text:
        raise AssertionError(message)


def check_function_limit(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    count = sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in ast.walk(tree))
    if count > 10:
        raise AssertionError(f"{path}: {count} functions exceeds limit 10")


def main() -> int:
    paths = (ACTION_PATH, WORKFLOW_PATH, DEV_ENTRY_PATH, GUI_PATH)
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

    require(action, 'ROSE_TEMPLATE = "cay_hong"', "Rose template missing")
    require(action, "TREE_COUNT = 27", "Exactly 27 trees required")
    require(action, "START_POINT = (325, 799)", "AUTO PRO start point changed")
    require(action, "(335, 40), (578, 40)", "Hidden fifth-floor endpoint changed")
    require(action, "threshold=0.87", "AUTO PRO rose threshold changed")
    require(action, "def _go_up_one", "AUTO PRO goUp(1) transition missing")
    require(action, "GO_UP_ONE_START = (514, 214)", "goUp(1) start changed")
    require(action, "GO_UP_ONE_END = (514, 314)", "goUp(1) end changed")
    require(action, "def _count_changed_pots", "Post-plant image verification missing")
    require(action, "if changed < 20:", "False PASS guard missing")
    require(action, '"harvestBasket", threshold=0.80', "Ripe-tree scan missing")
    require(action, '"next_gieo_trai", threshold=0.70', "Empty-pot scan missing")
    require(action, "self._harvest_27()", "Harvest-before-plant transition missing")
    require(action, "zone=self.SEED_ZONE", "Rose seed zone guard missing")
    require(action, "swipe_points(path, duration=self.SWIPE_DURATION)", "Single path swipe missing")
    require(action, "self.rose_path()[1:]", "Seed center must replace reference start point")
    require(action, 'raise ScreenTimeout(', "Fail-closed planting guard missing")
    require(workflow, "self.auto.planting.plant_27_roses()", "Workflow planting call missing")
    require(dev, "run_rose_plant: bool", "Resident planting selector missing")
    require(dev, 'outcome = "rose_plant_finished"', "Planting completion outcome missing")
    require(gui, 'text="▶ Trồng 27 Hoa hồng"', "AUTO Multi DEV planting button missing")

    forbidden = ("clear_stall_probe_runtime", "auto_main_selling", ".pyc")
    for token in forbidden:
        if token in action or token in workflow:
            raise AssertionError(f"Planting module touches forbidden stable path: {token}")
    print("AUTO MAIN PLANTING STATIC CONTRACT VERIFIED")
    print("item=cay_hong")
    print("tree_count=27")
    print("floors=6+6+6+6+3")
    print("floor5_endpoint=(578,40)")
    print("stable_sale_and_clear_stall=untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
