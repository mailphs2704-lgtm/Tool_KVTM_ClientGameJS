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
        "nang_kho", "check_vp_nang_kho", "xoa_vp_kc",
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
    require(workflow, 'auto-warehouse-upgrade-prove-upgrade-category', "Upgrade-category proof stage missing")
    require(workflow, '"check_vp_nang_kho"', "Selected upgrade-category template missing")
    require(workflow, "tab nguyên liệu nền vàng VERIFIED", "Selected upgrade-category proof missing")
    require(workflow, "if not self.allow_diamond_slot_delete:", "Diamond consent gate missing")
    require(workflow, "self._delete_one_listing_for_slot()", "Diamond slot recovery missing")
    require(workflow, "Nâng kho bỏ qua • quầy không có ô trống • không dùng KC", "Safe no-slot skip missing")
    require(workflow, "quantity_passes >= 2", "Existing two-pass x10 proof missing")
    require(workflow, "center[0] - 42, center[1] + 12, 100, 42", "Quantity crop must retain final digit")
    require(workflow, "panel Tôm READY", "Tom material sale panel proof missing")
    require(workflow, "xác nhận Tôm mua", "Tom confirmation wait missing")
    require(workflow, "Tôm đã mua", "Tom confirmed-sale accounting missing")
    require(workflow, "quầy sau khi Tôm mua nguyên liệu", "Post-Tom own-stall proof missing")
    require(workflow, "tái dùng ô trống", "Empty-slot reuse contract missing")
    require(workflow, "self._sale_slot_center", "Cached empty-slot coordinate missing")
    require(workflow, "FAST REUSE ô trống", "Fast empty-slot reuse path missing")
    require(workflow, "bỏ quét lại quầy/kho", "Repeated stall/storage scan removal missing")
    if "wait_sale_dialog_ready(" in workflow:
        raise AssertionError("Warehouse material sale must not wait for ordinary dat_ban dialog")
    require(workflow, "if item_id in found:", "Post-swipe de-duplication missing")
    require(workflow, "Không quét đủ 6 nguyên liệu", "Six-material fail-close missing")

    require(optional, '"warehouse_upgrade_interval_hours": 2', "Default 2h missing")
    require(optional, 'window.title("Cấu hình Nâng kho")', "Official panel title missing")
    require(optional, 'text="Lưu cấu hình"', "Official save action missing")
    require(optional, 'style="Section.TLabel"', "Warehouse header is not synchronized with Config UI")
    require(optional, 'style="Auto.TLabelframe"', "Warehouse sections are not synchronized with Config UI")
    require(optional, 'style="AutoStart.TButton"', "Warehouse save button is not synchronized with Config UI")
    require(optional, 'text="Mặc định"', "Warehouse default action missing")
    require(optional, 'text="Đóng"', "Warehouse close action missing")
    require(optional, 'placer = getattr(self, "_place_auto_child_window", None)', "Warehouse dialog placement helper missing")
    require(optional, 'text="Cho phép dùng 1 KC xóa VP khi quầy không có ô trống"', "Diamond consent checkbox missing")
    require(optional, '"warehouse_upgrade_allow_diamond_slot_delete": False', "Diamond consent must default OFF")
    require(optional, 'window.transient(self)', "Configuration dialog ownership missing")
    require(optional, 'window.grab_set()', "Configuration dialog modal behavior missing")
    require(optional, '"✓ Nâng kho" if warehouse_enabled', "Quick status indicator missing")
    require(ui, 'text="Nâng kho"', "Quick Nâng kho button missing")
    require(worker, '"warehouse_upgrade_mode": "warehouse_1"', "Worker config missing")
    require(worker, '"warehouse_upgrade_allow_diamond_slot_delete": False', "Worker diamond consent default missing")
    require(schedule, "WarehouseUpgradeWorkflow(", "Safe-boundary scheduler missing")
    require(schedule, "_warehouse_upgrade_due_after_sale", "Post-sale due gate missing")
    combined = optional + worker + ui
    for forbidden in (
        'Test từ Main',
        'warehouse-test-config.json',
        'warehouse_test_only',
        'warehouse_upgrade_test_finished',
    ):
        if forbidden in combined:
            raise AssertionError(f"Warehouse test-only path still present: {forbidden}")

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
    print("sale=view1+gold+empty; 1diamond=explicit-consent-only; full-stall=safe-skip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
