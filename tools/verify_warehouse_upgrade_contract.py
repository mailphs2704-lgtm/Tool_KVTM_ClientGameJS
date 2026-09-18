from __future__ import annotations

import ast
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "components/clientjs-auto"
WORKFLOW = CLEAN / "kvtm_automation/workflows/warehouse_upgrade.py"
SCHEDULE = CLEAN / "kvtm_automation/workflows/auto_main/pirate_chest_schedule.py"
WORKER = CLEAN / "worker/auto_multi_dev_worker.py"
OPTIONAL = ROOT / "source-archive/multi-current/kvtm_multi_tool/optional_features_integration.py"
UI = ROOT / "source-archive/multi-current/kvtm_multi_tool/auto_multi_dev_ui_integration.py"


def read(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path))
    return text


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def main() -> int:
    workflow = read(WORKFLOW)
    schedule = read(SCHEDULE)
    worker = read(WORKER)
    optional = read(OPTIONAL)
    ui = read(UI)
    for name in (
        "go", "gach", "son_do", "dinh", "son_vang", "da",
        "nang_kho", "xoa_vp_kc",
    ):
        path = CLEAN / "assets/items" / f"{name}.png"
        if not path.is_file() or path.stat().st_size <= 0:
            raise AssertionError(f"Missing warehouse AUTO-PRO asset: {name}")
    for digit in range(10):
        for suffix in ("", "_2", "_3"):
            path = CLEAN / "assets/items" / f"{digit}{suffix}.png"
            if not path.is_file() or path.stat().st_size <= 0:
                raise AssertionError(f"Missing warehouse digit asset: {path.name}")

    require(workflow, 'MODE_WAREHOUSE_1 = "warehouse_1"', "Kho 1 mode missing")
    require(workflow, 'MODE_WAREHOUSE_2 = "warehouse_2"', "Kho 2 mode missing")
    require(workflow, 'MODE_BOTH = "both"', "Both mode missing")
    require(workflow, 'MODE_MAX = "max"', "Max mode missing")
    require(workflow, "ceiling = baseline + 10", "Balance tolerance is not +10")
    require(workflow, "math.ceil(excess / 10.0)", "Balance batches are not fixed x10")
    require(workflow, "while self._sell_one_batch(item_id):", "Drain-until-below-x10 missing")
    require(workflow, 'self.auto.vision.driver.press("back")', "Single ESC/back exit missing")
    require(workflow, 'self.auto.vision.driver.click(*self.STORAGE_3_POINT)', "Required item-warehouse click missing")
    require(workflow, 'auto-warehouse-upgrade-select-item-warehouse', "Item-warehouse stage missing")
    require(workflow, 'auto-warehouse-upgrade-select-upgrade-category', "Upgrade-category stage missing")
    require(workflow, "self._delete_one_listing_for_slot()", "Diamond slot recovery missing")
    require(workflow, "quantity_passes >= 2", "Existing two-pass x10 proof missing")
    require(workflow, "if item_id in found:", "Post-swipe de-duplication missing")
    require(workflow, "Không quét đủ 6 nguyên liệu", "Six-material fail-close missing")

    require(optional, '"warehouse_upgrade_interval_hours": 2', "Default 2h missing")
    require(optional, 'window.title("Nâng kho")', "Nâng kho panel title missing")
    require(optional, 'text="Test từ Main"', "Warehouse one-shot test button missing")
    require(optional, 'warehouse-test-config.json', "Warehouse test marker missing")
    require(ui, 'text="Nâng kho"', "Quick Nâng kho button missing")
    require(worker, '"warehouse_upgrade_mode": "warehouse_1"', "Worker config missing")
    require(worker, 'outcome="warehouse_upgrade_test_finished"', "Warehouse test outcome missing")
    require(worker, "Test Nâng kho đã bán xong nhưng chưa chứng minh exact MAIN", "Test exact-main return proof missing")
    require(schedule, "WarehouseUpgradeWorkflow(", "Safe-boundary scheduler missing")
    require(schedule, "_warehouse_upgrade_due_after_sale", "Post-sale due gate missing")

    sys.path.insert(0, str(CLEAN))
    from kvtm_automation.workflows.warehouse_upgrade import WarehouseUpgradeWorkflow

    quantities = {"go": 142, "gach": 138, "son_do": 86, "dinh": 40, "son_vang": 31, "da": 28}
    plan = WarehouseUpgradeWorkflow.build_plan("warehouse_1", quantities)
    if plan.fixed_batches != {"go": 5, "gach": 5, "son_do": 0}:
        raise AssertionError(f"Kho 1 balance calculation changed: {plan.fixed_batches}")
    if plan.drain_items != ("dinh", "son_vang", "da"):
        raise AssertionError(f"Kho 1 drain policy changed: {plan.drain_items}")
    if WarehouseUpgradeWorkflow.build_plan("both", quantities).drain_items:
        raise AssertionError("Nâng cả 2 must retain all six materials")
    if len(WarehouseUpgradeWorkflow.build_plan("max", quantities).drain_items) != 6:
        raise AssertionError("Max kho must drain all six materials")

    print("AUTO MULTI DEV WAREHOUSE UPGRADE CONTRACT VERIFIED")
    print("modes=warehouse1|warehouse2|both|max; interval=2h-configurable")
    print("balance=fixed-at-scan+10-tolerance; drain=until-below-x10")
    print("sale=view1+gold+empty-or-1diamond+fresh-item-position+two-pass-x10")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
