from __future__ import annotations

import ast
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "components/clientjs-auto/kvtm_automation/actions/production.py"
FLOOR_ACTION = ROOT / "components/clientjs-auto/kvtm_automation/actions/floor_navigation.py"
AUTOMATION = ROOT / "components/clientjs-auto/kvtm_automation/automation.py"
WORKFLOW = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_apple_dryer/workflow.py"
GAME_SESSION = ROOT / "components/clientjs-auto/kvtm_automation/workflows/game_session/workflow.py"
AUTO_MAIN = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_main/workflow.py"
FUNCTION_ONE = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_function_one/workflow.py"
APPLE_JUICE = ROOT / "components/clientjs-auto/kvtm_automation/actions/apple_juice_production.py"
COTTON = ROOT / "components/clientjs-auto/kvtm_automation/actions/cotton_planting.py"
PASS_THREE_NAV = ROOT / "components/clientjs-auto/kvtm_automation/actions/function_one_pass_three_navigation.py"
YELLOW_FABRIC = ROOT / "components/clientjs-auto/kvtm_automation/actions/yellow_fabric_production.py"
DEV_ENTRY = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_entry.py"
AUTO_MULTI_WORKER = ROOT / "components/clientjs-auto/worker/auto_multi_dev_worker.py"
MULTI_DEV_DRIED_APPLE = ROOT / "components/clientjs-auto/assets/items/tao_say.png"
MULTI_DEV_EMPTY_SLOT = ROOT / "components/clientjs-auto/assets/items/o_trong.png"
MULTI_DEV_COTTON = ROOT / "components/clientjs-auto/assets/items/cay_bong.png"
MULTI_DEV_YELLOW_FABRIC = ROOT / "components/clientjs-auto/assets/items/vai_vang.png"
MULTI_DEV_WAREHOUSE_YELLOW_FABRIC = ROOT / "components/clientjs-auto/assets/items/kho_vai_vang.png"
EXPECTED_COTTON_BLOB_SHA = "a828d5a796579f58de77989a80bd92d1122336d3"
EXPECTED_YELLOW_FABRIC_BLOB_SHA = "e963be3a5c33b85732f1b611b6801a741a4837ec"
EXPECTED_WAREHOUSE_YELLOW_FABRIC_BLOB_SHA = "f1d6135fa1af9725897f8a5b046e6fd2e5220754"


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def main() -> int:
    contract_files = (
        ACTION,
        FLOOR_ACTION,
        AUTOMATION,
        WORKFLOW,
        GAME_SESSION,
        AUTO_MAIN,
        FUNCTION_ONE,
        APPLE_JUICE,
        COTTON,
        PASS_THREE_NAV,
        YELLOW_FABRIC,
        DEV_ENTRY,
        AUTO_MULTI_WORKER,
    )
    for path in contract_files:
        if not path.is_file():
            raise AssertionError(f"Missing production contract file: {path}")
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        functions = sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            for node in ast.walk(tree)
        )
        if path in (ACTION, FLOOR_ACTION, WORKFLOW, GAME_SESSION, COTTON, PASS_THREE_NAV, YELLOW_FABRIC) and functions > 10:
            raise AssertionError(f"{path}: {functions} functions exceeds limit 10")

    for asset in (
        MULTI_DEV_DRIED_APPLE,
        MULTI_DEV_EMPTY_SLOT,
        MULTI_DEV_COTTON,
        MULTI_DEV_YELLOW_FABRIC,
        MULTI_DEV_WAREHOUSE_YELLOW_FABRIC,
    ):
        if not asset.is_file():
            raise AssertionError(f"Multi Dev production asset missing: {asset.name}")

    asset_blob_contract = (
        (MULTI_DEV_COTTON, EXPECTED_COTTON_BLOB_SHA),
        (MULTI_DEV_YELLOW_FABRIC, EXPECTED_YELLOW_FABRIC_BLOB_SHA),
        (MULTI_DEV_WAREHOUSE_YELLOW_FABRIC, EXPECTED_WAREHOUSE_YELLOW_FABRIC_BLOB_SHA),
    )
    for asset, expected_sha in asset_blob_contract:
        actual_sha = git_blob_sha(asset)
        if actual_sha != expected_sha:
            raise AssertionError(
                f"Canonical asset blob changed: {asset.name} expected={expected_sha} actual={actual_sha}"
            )

    if EXPECTED_YELLOW_FABRIC_BLOB_SHA == EXPECTED_WAREHOUSE_YELLOW_FABRIC_BLOB_SHA:
        raise AssertionError("Production and warehouse yellow-fabric assets must remain distinct")

    action = ACTION.read_text(encoding="utf-8")
    floor_action = FLOOR_ACTION.read_text(encoding="utf-8")
    automation = AUTOMATION.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    game_session = GAME_SESSION.read_text(encoding="utf-8")
    auto_main = AUTO_MAIN.read_text(encoding="utf-8")
    function_one = FUNCTION_ONE.read_text(encoding="utf-8")
    apple_juice = APPLE_JUICE.read_text(encoding="utf-8")
    cotton = COTTON.read_text(encoding="utf-8")
    pass_three_nav = PASS_THREE_NAV.read_text(encoding="utf-8")
    yellow_fabric = YELLOW_FABRIC.read_text(encoding="utf-8")
    dev = DEV_ENTRY.read_text(encoding="utf-8")
    auto_multi_worker = AUTO_MULTI_WORKER.read_text(encoding="utf-8")

    # Startup routing remains diagnostic/non-fatal. Exact main gates now belong
    # only to explicit business transitions between planting/production stages.
    require(game_session, "DOWN_ONE = (514, 314, 514, 214)", "Startup goDown(1) geometry changed")
    require(game_session, 'started_on_main = self.auto.popup.is_own_main_screen()', "Startup routing hint missing")
    require(game_session, 'self._startup_go_down_one("startup-low-floor-probe-1-of-4")', "STEP 2 initial goDown(1) probe missing")
    require(game_session, "for index in range(2, 5):", "STEP 2 must issue exactly three additional goDown(1)s")
    require(game_session, "fresh_frame=true", "STEP 2 must capture a fresh frame after each goDown(1)")
    require(game_session, "không gate main tại startup", "Startup must not exact-gate main after low-floor settling")
    if "STEP 2 đã gửi 1+3 goDown(1) nhưng chưa xác nhận" in game_session:
        raise AssertionError("Obsolete startup exact-main ScreenTimeout gate returned")
    if "if change <" in game_session:
        raise AssertionError("Startup STEP 2 must not use frame-change as a floor/main detector")
    if "self.auto.ensure_main_screen(timeout=timeout)" in workflow:
        raise AssertionError("AppleDryer must not duplicate the startup exact-main gate")
    require(function_one, "def _require_main_transition", "Inter-stage exact-main gate helper missing")
    require(function_one, 'self._require_main_transition("sau trồng Táo tầng 6 → trước SX Nước táo")', "Missing main gate between apple planting and juice production")
    require(function_one, 'self._require_main_transition("sau SX Nước táo → trước trồng Bông")', "Missing main gate between juice production and cotton planting")

    # Pass 1: keep the already verified dried-apple contract intact.
    require(action, "DRYER_POINT = (262, 917)", "AUTO PRO dryer coordinate changed")
    require(action, 'DRIED_APPLE_PRODUCTION_TEMPLATE = "tao_say"', "AUTO PRO production template missing")
    if 'DRIED_APPLE_PRODUCTION_TEMPLATE = "kho_tao_say"' in action:
        raise AssertionError("Warehouse dried-apple template must never drive production")
    require(action, "PRODUCT_SEARCH_ZONE = None", "Production image must be searched across the open panel")
    require(action, "DRIED_APPLE_GUARD_THRESHOLD = 0.70", "Production image threshold must reject observed false match")
    require(action, "empty_before, product_point, top_point = self._open_verified_dryer()", "Detected source/top centers are not returned")
    require(action, "(product_point, top_point)", "Production swipe must use detected centers")
    require(action, "REQUIRED_COUNT = 9", "Exactly nine dried apples required")
    require(action, "current_empty >= empty_after", "Per-drag empty-slot state-change gate missing")
    require(action, "consumed != self.REQUIRED_COUNT", "Exact post-production accounting missing")
    require(action, "self.speed_config.vp_production_delay", "Production speed binding missing")
    require(action, "self.context.ensure_running()", "Production loops must remain stoppable")
    require(action, "for attempt in range(1, 4)", "Three product-render retries missing")
    require(action, '"full_kho"', "Canonical full warehouse template missing")
    require(action, "def _find_top_empty_slot(self):", "Reusable upper queue-slot detector missing")

    # Pass 2: keep the verified apple-juice stage and navigation route.
    require(function_one, "AppleDryerWorkflow(self.auto).run", "Stable dried-apple stage missing")
    require(function_one, "floor_1_to_floor_6()", "Floor-1 to floor-6 route missing")
    require(function_one, "produce_9_apple_juices()", "Apple-juice intermediate stage missing")
    require(apple_juice, 'PRODUCT_TEMPLATE = "nuoc_tao"', "Apple-juice production asset missing")
    require(apple_juice, "if panel_ready:", "Apple-juice panel verification missing")

    # Pass 3: cotton -> verified floor 3 -> exactly nine yellow fabrics.
    require(cotton, 'COTTON_TEMPLATE = "cay_bong"', "Cotton template id changed")
    require(cotton, "if not self.vision.assets.has(self.COTTON_TEMPLATE):", "Cotton must fail-close before gesture when clean asset is missing")
    require(cotton, 'baseline = self._open_seed_picker(self.COTTON_TEMPLATE, "Bông")', "Cotton must reuse the proven seed-picker and capture a pre-plant baseline")
    require(cotton, "path = (seed.center,) + self.rose_path()[1:]", "Cotton must reuse the proven 27-pot planting geometry")
    require(cotton, "changed = self._count_changed_pots(baseline, after)", "Cotton visible-region diagnostic missing")
    require(cotton, "non_blocking=true", "Cotton visible-region diagnostic must remain advisory")
    if "if changed != self.TREE_COUNT:" in cotton:
        raise AssertionError("Cotton must not block on 27/27 visible regions")
    if "fail_close=true" in cotton:
        raise AssertionError("Cotton visible-region diagnostic must not regress to blocking")
    require(pass_three_nav, "def floor_2_to_main", "Pass-3 floor2-to-main route missing")
    require(pass_three_nav, "def _settle_down_one", "Pass-3 post-juice settle primitive missing")
    require(pass_three_nav, "*self.DOWN_ONE", "Pass-3 post-juice descent must use goDown(1) geometry")
    require(pass_three_nav, '"post-juice-goDown(1)-probe-1-of-4"', "Pass-3 post-juice first down probe missing")
    require(pass_three_nav, '"post-juice-goDown(1)-settle-4-of-4"', "Pass-3 post-juice must include all three settling downs")
    require(pass_three_nav, "boundary_change_non_blocking=true", "Post-juice boundary frame-change must remain diagnostic")
    require(pass_three_nav, "def floor_1_to_floor_3", "Pass-3 floor1-to-floor3 route missing")
    require(pass_three_nav, "self._gesture(self.UP_ONE", "Pass-3 upward route must use verified fresh-frame gesture")
    require(yellow_fabric, 'PRODUCT_TEMPLATE = "vai_vang"', "Yellow-fabric production template missing")
    if "kho_vai_vang" in yellow_fabric:
        raise AssertionError(
            "Warehouse yellow-fabric template must never be referenced by production"
        )
    require(yellow_fabric, "REQUIRED_COUNT = 9", "Exactly nine yellow fabrics required")
    require(yellow_fabric, "MAX_OPEN_CLICKS = 30", "Yellow-fabric machine opening must be bounded")
    require(yellow_fabric, "for click_count in range(1, self.MAX_OPEN_CLICKS + 1)", "Bounded yellow-fabric opening loop missing")
    require(yellow_fabric, "if not panel_ready:", "Yellow-fabric panel fail-close missing")
    require(yellow_fabric, "current >= empty_after", "Yellow-fabric per-drag empty-slot gate missing")
    require(yellow_fabric, "empty_before - empty_after != self.REQUIRED_COUNT", "Yellow-fabric exact post-accounting missing")
    require(yellow_fabric, "self.speed_config.vp_production_delay", "Yellow-fabric speed binding missing")
    require(function_one, "floor_2_to_main()", "Pass-3 must return from floor 2 to main")
    require(function_one, "plant_27_cotton()", "Pass-3 cotton planting missing")
    require(function_one, "floor_1_to_floor_3()", "Pass-3 floor-3 navigation missing")
    require(function_one, "produce_9_yellow_fabrics()", "Pass-3 yellow-fabric production missing")
    require(function_one, "progress_steps=3", "Function 1 result must report progress 3")
    require(function_one, "total_steps=3", "Function 1 result must report total 3")

    require(auto_main, "function_one.progress_steps != 3", "Auto Main PASS 3/3 guard missing")
    require(auto_main, "function_one.yellow_fabrics != 9", "Auto Main yellow-fabric final guard missing")
    require(auto_main, "function_one.cotton_planted != 27", "Auto Main cotton final guard missing")
    require(auto_main, "production_ready=True", "Auto Main must be ready only after PASS 3/3")
    require(auto_main, '"auto-main-function-1-pass-3-of-3"', "Auto Main final stage marker missing")

    require(automation, "self.production = ProductionActions(", "Resident production wiring missing")
    require(automation, "self.cotton_planting = CottonPlantingActions(", "Resident cotton wiring missing")
    require(automation, "self.yellow_fabric_production = YellowFabricProductionActions(", "Resident yellow-fabric wiring missing")
    require(automation, "self.function_one_pass_three_navigation = FunctionOnePassThreeNavigationActions(", "Resident pass-3 navigation wiring missing")
    require(auto_main, "FunctionOneWorkflow(self.auto).run", "Function one pipeline missing")
    require(dev, 'text="↟ Demo Auto Pro tới tầng 6"', "Dedicated floor demo button missing")
    require(auto_multi_worker, "automation.floors.reference_main_to_floor_6()", "Floor demo worker must replay target=6 state machine")
    require(floor_action, "AUTO_PRO_GO_UP_4_SWIPE = (387, 69, 387, 918)", "Exact Auto Pro goUp(4) geometry missing")

    forbidden = (
        "clear_stall_probe_runtime",
        "auto_main_selling.py",
        "RosePlantingWorkflow",
        "adb_controller.pyc",
    )
    for token in forbidden:
        if token in action or token in workflow or token in yellow_fabric or token in cotton:
            raise AssertionError(f"New production module touches stable/legacy path: {token}")

    print("AUTO MULTI DEV FUNCTION ONE STATIC CONTRACT VERIFIED")
    print("runtime=isolated_worker_v3")
    print("startup_step2=low_floor_1_plus_3_godown1_no_exact_main_gate")
    print("main_gate=business_transitions_only")
    print("post_juice_navigation=1_plus_3_godown1_boundary_non_blocking_exact_main_gate")
    print("flow=pass1_dried_apple pass2_apple_juice pass3_cotton_yellow_fabric")
    print("pass3=cotton_27 then yellow_fabric_9")
    print("cotton_asset=canonical_blob_locked")
    print("cotton_postcheck=diagnostic_non_blocking")
    print("yellow_fabric_asset=production_vai_vang_only")
    print("yellow_fabric_asset_blob=canonical_locked")
    print("warehouse_yellow_fabric_asset_blob=distinct_canonical_locked")
    print("legacy_auto_pro=reference_only")
    print("stable_sale_and_clear_stall=untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
