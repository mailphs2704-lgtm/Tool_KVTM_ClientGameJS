from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "components/clientjs-auto/kvtm_automation/actions/production.py"
FLOOR_ACTION = ROOT / "components/clientjs-auto/kvtm_automation/actions/floor_navigation.py"
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
    for path in (ACTION, FLOOR_ACTION, AUTOMATION, WORKFLOW, AUTO_MAIN, DEV_ENTRY):
        if not path.is_file():
            raise AssertionError(f"Missing production contract file: {path}")
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        functions = sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            for node in ast.walk(tree)
        )
        if path in (ACTION, FLOOR_ACTION, WORKFLOW) and functions > 10:
            raise AssertionError(f"{path}: {functions} functions exceeds limit 10")

    if not MULTI_DEV_DRIED_APPLE.is_file():
        raise AssertionError("Multi Dev production asset missing: tao_say.png")
    if not MULTI_DEV_EMPTY_SLOT.is_file():
        raise AssertionError("Multi Dev production asset missing: o_trong.png")

    action = ACTION.read_text(encoding="utf-8")
    floor_action = FLOOR_ACTION.read_text(encoding="utf-8")
    automation = AUTOMATION.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    auto_main = AUTO_MAIN.read_text(encoding="utf-8")
    dev = DEV_ENTRY.read_text(encoding="utf-8")

    require(action, "DRYER_POINT = (262, 917)", "AUTO PRO dryer coordinate changed")
    require(action, 'DRIED_APPLE_PRODUCTION_TEMPLATE = "tao_say"', "AUTO PRO production template missing")
    if 'DRIED_APPLE_PRODUCTION_TEMPLATE = "kho_tao_say"' in action:
        raise AssertionError("Warehouse dried-apple template must never drive production")
    require(action, "PRODUCT_SEARCH_ZONE = None",
            "Production image must be searched across the open panel")
    require(action, "DRIED_APPLE_GUARD_THRESHOLD = 0.70",
            "Production image threshold must reject the observed 0.301 false match")
    require(action, "empty_before, product_point, top_point = self._open_verified_dryer()",
            "Detected source and top-slot centers are not returned to queue loop")
    require(action, "(product_point, top_point)",
            "Production swipe must run from library tao_say to detected top slot")
    require(action, "REQUIRED_COUNT = 9", "Exactly nine dried apples required")
    require(action, "empty < self.REQUIRED_COUNT", "Nine-empty-slot precondition missing")
    require(action, "current_empty >= empty_after",
            "Per-drag empty-slot state-change gate missing")
    require(action, "consumed != self.REQUIRED_COUNT", "Exact post-production accounting missing")
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
    require(action, '"full_kho"', "Canonical full warehouse template missing")
    require(action, "TOP_EMPTY_SLOT_ZONE = (335, 650, 130, 135)",
            "Upper queue slot zone missing")
    require(action, "def _find_top_empty_slot(self):",
            "Reusable upper queue-slot detector missing")
    require(action, "top_match = self._find_top_empty_slot()",
            "Upper queue count must use detected library template")
    require(action, "scales=(1.00, 1.15, 1.30, 1.45, 1.60)",
            "Upper queue slot scales changed")
    require(action, "lower = min(8, self._count_matches(",
            "Lower queue slots must count at most eight")
    require(action, "total = top + lower",
            "Nine-slot queue total must include upper and lower slots")
    require(action, "không khớp chắc chắn ảnh thư viện tao_say",
            "Wrong-item fail-close missing")
    require(action, "Không tìm thấy ô top bằng ảnh thư viện o_trong",
            "Top destination fail-close missing")
    require(automation, "self.production = ProductionActions(", "Resident production wiring missing")
    require(workflow, "plant_27_apples()", "Apple planting step missing")
    require(workflow, "produce_9_dried_apples()", "Dried apple production step missing")
    require(auto_main, "AppleDryerWorkflow(self.auto).run", "Function one pipeline missing")
    require(dev, "PASS CHỨC NĂNG 1", "GUI result status missing")
    require(dev, 'text="↟ Demo Auto Pro tới tầng 6"', "Dedicated floor demo button missing")
    require(dev, "profile_id in self._clean_floor_demo_requested",
            "Floor demo request is not isolated per profile")
    require(dev, "automation.floors.reference_main_to_floor_6()",
            "Floor demo must replay Auto Pro goUp(4) then goUp(3)")
    require(dev, '"floor_demo_finished"', "Floor demo result path missing")
    require(automation, "self.floors = FloorNavigationActions(",
            "Resident floor navigation wiring missing")
    require(floor_action, "AUTO_PRO_GO_UP_4_SWIPE = (387, 69, 387, 918)",
            "Exact Auto Pro goUp(4) geometry missing")
    require(floor_action, "AUTO_PRO_GO_UP_3_POINT = (257, 191)",
            "Exact Auto Pro goUp(3) click missing")
    require(floor_action, "duration=self.speed_config.plant_harvest_duration",
            "Auto Pro goUp(4) must use the harvest-speed equivalent")
    require(floor_action, "AUTO_PRO_GO_UP_WAIT = 0.70",
            "Auto Pro go_up_wait reference missing")
    require(floor_action, "AUTO_PRO_POST_WAIT = 0.15",
            "Auto Pro post-command wait missing")

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
