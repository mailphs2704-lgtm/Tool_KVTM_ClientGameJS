from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "components/clientjs-auto/kvtm_automation/actions/production.py"
AUTOMATION = ROOT / "components/clientjs-auto/kvtm_automation/automation.py"
WORKFLOW = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_apple_dryer/workflow.py"
AUTO_MAIN = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_main/workflow.py"
DEV_ENTRY = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_entry.py"
MULTI_DEV_DRIED_APPLE = ROOT / "components/clientjs-auto/assets/items/tao_say.png"
MULTI_DEV_EMPTY_SLOT = ROOT / "components/clientjs-auto/assets/items/o_trong.png"


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def main() -> int:
    for path in (ACTION, AUTOMATION, WORKFLOW, AUTO_MAIN, DEV_ENTRY):
        if not path.is_file():
            raise AssertionError(f"Missing production contract file: {path}")
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        functions = sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            for node in ast.walk(tree)
        )
        if path in (ACTION, WORKFLOW) and functions > 10:
            raise AssertionError(f"{path}: {functions} functions exceeds limit 10")

    if not MULTI_DEV_DRIED_APPLE.is_file():
        raise AssertionError("Multi Dev production asset missing: tao_say.png")
    if not MULTI_DEV_EMPTY_SLOT.is_file():
        raise AssertionError("Multi Dev production asset missing: o_trong.png")

    action = ACTION.read_text(encoding="utf-8")
    automation = AUTOMATION.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    auto_main = AUTO_MAIN.read_text(encoding="utf-8")
    dev = DEV_ENTRY.read_text(encoding="utf-8")

    require(action, "DRYER_POINT = (262, 917)", "AUTO PRO dryer coordinate changed")
    require(action, 'DRIED_APPLE_PRODUCTION_TEMPLATE = "tao_say"', "AUTO PRO production template missing")
    if 'DRIED_APPLE_PRODUCTION_TEMPLATE = "kho_tao_say"' in action:
        raise AssertionError("Warehouse dried-apple template must never drive production")
    require(action, "PRODUCT_SEARCH_ZONE = (9, 341, 402, 386)", "Product reference zone changed")
    require(action, "DRIED_APPLE_GUARD_ZONE = (180, 360, 150, 125)",
            "Fixed dried-apple guard zone changed")
    require(action, "PRODUCT_SLOT_0 = (252, 421)", "Dried apple reference slot changed")
    require(action, "empty_before, product_point = self._open_verified_dryer()",
            "Detected production center is not returned to queue loop")
    require(action, "(product_point, self.QUEUE_DROP_POINT)",
            "Production swipe must start from detected AUTO PRO icon")
    require(action, "DRIED_APPLE_GUARD_THRESHOLD = 0.28", "Live-calibrated dried-apple threshold changed")
    require(action, "QUEUE_DROP_POINT = (400, 719)", "Queue drop point changed")
    require(action, "REQUIRED_COUNT = 9", "Exactly nine dried apples required")
    require(action, "empty < self.REQUIRED_COUNT", "Nine-empty-slot precondition missing")
    require(action, "consumed < self.REQUIRED_COUNT", "Post-production accounting missing")
    require(action, "self.speed_config.vp_production_delay", "Production speed binding missing")
    require(action, "_collect_finished_before_open()", "Finished-output collection gate missing")
    require(action, "for batch, click_count in ((1, 1), (2, 5), (3, 5))",
            "AUTO PRO bounded collection pulses missing")
    require(action, "đã thu hết VP chắn máy và mở được panel tầng 1",
            "Collection-to-panel verification missing")
    require(action, "Không thu hết VP hoàn thành hoặc không mở được panel",
            "Collection/panel fail-close missing")
    require(action, "for attempt in range(1, 4)", "Three product-render retries missing")
    require(action, 'threshold=0.70', "AUTO PRO initial empty-slot gate missing")
    require(action, "TOP_EMPTY_SLOT_ZONE = (335, 650, 130, 135)",
            "Upper queue slot zone missing")
    require(action, "top = min(1, self._count_matches(",
            "Upper queue slot must count once")
    require(action, "lower = min(8, self._count_matches(",
            "Lower queue slots must count at most eight")
    require(action, "total = top + lower",
            "Nine-slot queue total must include upper and lower slots")
    require(action, "slot cố định (252,421) không khớp Táo sấy",
            "Wrong-item fail-close missing")
    require(automation, "self.production = ProductionActions(", "Resident production wiring missing")
    require(workflow, "plant_27_apples()", "Apple planting step missing")
    require(workflow, "produce_9_dried_apples()", "Dried apple production step missing")
    require(auto_main, "AppleDryerWorkflow(self.auto).run", "Function one pipeline missing")
    require(dev, "PASS CHỨC NĂNG 1", "GUI result status missing")

    forbidden = (
        "clear_stall_probe_runtime",
        "auto_main_selling.py",
        "RosePlantingWorkflow",
        "adb_controller.pyc",
    )
    for token in forbidden:
        if token in action or token in workflow:
            raise AssertionError(f"New production module touches stable/legacy path: {token}")

    print("AUTO MULTI DEV FUNCTION ONE STATIC CONTRACT VERIFIED")
    print("runtime=clean_resident")
    print("flow=plant_27_apples_then_collect_finished_output_then_queue_9_dried_apples")
    print("dryer_floor=1")
    print("legacy_auto_pro=reference_only")
    print("stable_sale_and_clear_stall=untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
