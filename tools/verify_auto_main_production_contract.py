from __future__ import annotations

import ast
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "components/clientjs-auto/kvtm_automation"
ACTION = CLEAN / "actions/production.py"
FLOOR_ACTION = CLEAN / "actions/floor_navigation.py"
AUTOMATION = CLEAN / "automation.py"
WORKFLOW = CLEAN / "workflows/auto_apple_dryer/workflow.py"
GAME_SESSION = CLEAN / "workflows/game_session/workflow.py"
AUTO_MAIN = CLEAN / "workflows/auto_main/workflow.py"
FUNCTION_ONE = CLEAN / "workflows/auto_function_one/workflow.py"
FUNCTION_NAV = CLEAN / "actions/function_one_navigation.py"
WAREHOUSE_RECOVERY = CLEAN / "workflows/production_warehouse_recovery.py"
APPLE_JUICE = CLEAN / "actions/apple_juice_production.py"
COTTON = CLEAN / "actions/cotton_planting.py"
PASS_THREE_NAV = CLEAN / "actions/function_one_pass_three_navigation.py"
DOWN_FLOOR_DETECTOR = CLEAN / "runtime/down_floor_button.py"
YELLOW_FABRIC = CLEAN / "actions/yellow_fabric_production.py"
MACHINE_REPAIR = CLEAN / "actions/machine_repair.py"
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


def forbid(text: str, token: str, message: str) -> None:
    if token in text:
        raise AssertionError(message)


def read_python(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing production contract file: {path}")
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path))
    return text


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def main() -> int:
    sources = {
        path: read_python(path)
        for path in (
            ACTION, FLOOR_ACTION, AUTOMATION, WORKFLOW, GAME_SESSION, AUTO_MAIN,
            FUNCTION_ONE, FUNCTION_NAV, WAREHOUSE_RECOVERY, APPLE_JUICE, COTTON,
            PASS_THREE_NAV, DOWN_FLOOR_DETECTOR, YELLOW_FABRIC, MACHINE_REPAIR,
            DEV_ENTRY, AUTO_MULTI_WORKER,
        )
    }
    action = sources[ACTION]
    floor_action = sources[FLOOR_ACTION]
    automation = sources[AUTOMATION]
    workflow = sources[WORKFLOW]
    game_session = sources[GAME_SESSION]
    auto_main = sources[AUTO_MAIN]
    function_one = sources[FUNCTION_ONE]
    function_nav = sources[FUNCTION_NAV]
    warehouse_recovery = sources[WAREHOUSE_RECOVERY]
    apple_juice = sources[APPLE_JUICE]
    cotton = sources[COTTON]
    pass_three_nav = sources[PASS_THREE_NAV]
    down_floor_detector = sources[DOWN_FLOOR_DETECTOR]
    yellow_fabric = sources[YELLOW_FABRIC]
    machine_repair = sources[MACHINE_REPAIR]
    dev = sources[DEV_ENTRY]
    auto_multi_worker = sources[AUTO_MULTI_WORKER]

    for asset in (
        MULTI_DEV_DRIED_APPLE, MULTI_DEV_EMPTY_SLOT, MULTI_DEV_COTTON,
        MULTI_DEV_YELLOW_FABRIC, MULTI_DEV_WAREHOUSE_YELLOW_FABRIC,
    ):
        if not asset.is_file():
            raise AssertionError(f"Multi Dev production asset missing: {asset.name}")
    for asset, expected_sha in (
        (MULTI_DEV_COTTON, EXPECTED_COTTON_BLOB_SHA),
        (MULTI_DEV_YELLOW_FABRIC, EXPECTED_YELLOW_FABRIC_BLOB_SHA),
        (MULTI_DEV_WAREHOUSE_YELLOW_FABRIC, EXPECTED_WAREHOUSE_YELLOW_FABRIC_BLOB_SHA),
    ):
        actual = git_blob_sha(asset)
        if actual != expected_sha:
            raise AssertionError(
                f"Canonical asset blob changed: {asset.name} expected={expected_sha} actual={actual}"
            )
    if EXPECTED_YELLOW_FABRIC_BLOB_SHA == EXPECTED_WAREHOUSE_YELLOW_FABRIC_BLOB_SHA:
        raise AssertionError("Production and warehouse yellow-fabric assets must remain distinct")

    # Startup owns portal/account entry + popup cleanup only. No floor/camera
    # navigation is allowed here; exact business navigation stays in Function flows.
    require(game_session, "self.auto.ensure_main_screen(timeout=float(timeout))",
            "GameSession enter-game/popup transaction missing")
    require(game_session, "startup không thực hiện goDown(1)",
            "Startup no-goDown policy marker missing")
    forbid(game_session, "DOWN_ONE =", "Startup goDown geometry must be removed")
    forbid(game_session, "_startup_go_down_one", "Startup goDown helper must be removed")
    forbid(game_session, "_recover_floor_1_or_2_start", "Startup low-floor recovery must be removed")
    forbid(workflow, "self.auto.ensure_main_screen(timeout=timeout)", "AppleDryer duplicated startup main gate")
    require(function_one, "def _require_main_transition", "Inter-stage exact-main helper missing")
    require(function_one, 'self._require_main_transition("sau trồng Táo tầng 6 → trước SX Nước táo")', "Apple→juice main gate missing")
    require(function_one, 'self._require_main_transition("sau SX Nước táo → trước trồng Bông")', "Juice→cotton main gate missing")

    # Shared production opening: true five-click bursts continue until the exact
    # requested item appears in the proven panel library zone. Empty-slot imagery
    # is diagnostic only because it can false-positive before the panel opens.
    require(action, "DRYER_POINT = (262, 917)", "Dryer coordinate changed")
    require(action, 'DRIED_APPLE_PRODUCTION_TEMPLATE = "tao_say"', "Dried-apple production template missing")
    forbid(action, 'DRIED_APPLE_PRODUCTION_TEMPLATE = "kho_tao_say"', "Warehouse dried-apple template drives production")
    require(action, "PRODUCT_SEARCH_ZONE = (420, 550, 170, 120)", "Panel product-library zone changed")
    require(action, "zone=self.PRODUCT_SEARCH_ZONE", "Product matching is not restricted to panel library zone")
    require(action, "DRIED_APPLE_GUARD_THRESHOLD = 0.70", "Dried-apple guard threshold changed")
    require(action, "REQUIRED_COUNT = 9", "Exactly nine dried apples required")
    require(action, "COLLECT_CLICK_BURST = 5", "VP collect must use five-click bursts")
    require(action, "def _send_collect_burst(", "Raw five-click VP burst helper missing")
    require(action, "for _ in range(self.COLLECT_CLICK_BURST):", "Five-click burst loop missing")
    require(action, "self.vision.driver.click(*machine_point)", "Raw VP machine click missing")
    require(action, "def _click_until_panel_open", "Shared five-click panel opener missing")
    require(action, "click_count += self._send_collect_burst(machine_point=machine_point)", "Five-click panel opener does not call raw burst helper")
    forbid(action, "panel_ready = empty_ready or product_ready", "Empty-slot false positive may stop VP collection early")
    require(action, "if product is not None:", "Panel opening is not gated by requested product anchor")
    require(action, "KHÔNG coi panel đã mở", "Empty-slot diagnostic cannot prove panel-open policy")
    require(action, "return click_count", "Five-click panel opener does not return on verified panel")
    require(action, "self.context.ensure_running()", "Five-click/recheck loops are not stop-aware")
    require(action, "self.speed_config.vp_collect_delay", "Dried-apple collect speed binding missing")
    require(action, "self.speed_config.vp_production_delay", "Dried-apple production speed binding missing")
    require(action, "def _wait_for_idle_open_panel", "Open-panel busy wait missing")
    require(action, "empty == self.REQUIRED_COUNT", "Production must wait for exact 9/9 empty slots")
    require(action, "self.waiter.sleep(self.PANEL_RECHECK_SECONDS)", "Open-panel cooperative recheck missing")
    require(action, "KHÔNG dừng AUTO", "Temporary product-image miss must be explicitly nonfatal")
    forbid(action, "PANEL_PRODUCT_MISS_LIMIT", "Product-image miss limit must not stop AUTO")
    forbid(action, "panel đang chờ bị mất ảnh sản phẩm đúng", "Old panel-miss ScreenTimeout returned")
    require(action, "current_empty >= empty_after", "Dried-apple per-drag gate missing")
    require(action, "consumed != self.REQUIRED_COUNT", "Dried-apple exact post-accounting missing")
    require(action, "close_after_success: bool = True", "Production panel handoff switch missing")

    # Warehouse-full is still a distinct recoverable business signal.
    require(action, '"full_kho"', "Full warehouse guard missing")
    require(action, "raise InventoryFull(", "Full warehouse must emit InventoryFull")
    require(action, "def _raise_inventory_full", "Shared full-warehouse signal helper missing")
    require(action, "def _find_top_empty_slot(self):", "Reusable top-slot detector missing")

    # Floor 2/3 must delegate collection to the same five-click helper; no local
    # bounded click loops may reintroduce stop-on-open-timeout behavior.
    require(apple_juice, 'PRODUCT_TEMPLATE = "nuoc_tao"', "Apple-juice production template missing")
    require(apple_juice, "self.slots._click_until_panel_open(", "Apple-juice does not use shared five-click opener")
    require(apple_juice, "product_template=self.PRODUCT_TEMPLATE", "Apple-juice product guard missing from opener")
    require(apple_juice, "self.slots._wait_for_idle_open_panel(", "Apple-juice open-panel wait missing")
    require(apple_juice, "ProductionActions(context, vision, waiter, self.speed_config)", "Apple-juice collect speed is not handed to shared opener")
    require(apple_juice, "current >= empty_after", "Apple-juice per-drag gate missing")
    require(apple_juice, "self.speed_config.vp_production_delay", "Apple-juice production speed binding missing")
    require(apple_juice, "close_after_success: bool = True", "Apple-juice panel handoff switch missing")

    require(yellow_fabric, 'PRODUCT_TEMPLATE = "vai_vang"', "Yellow-fabric production template missing")
    forbid(yellow_fabric, "kho_vai_vang", "Warehouse yellow-fabric template referenced by production")
    require(yellow_fabric, "REQUIRED_COUNT = 9", "Exactly nine yellow fabrics required")
    require(yellow_fabric, "self.slots._click_until_panel_open(", "Yellow-fabric does not use shared five-click opener")
    require(yellow_fabric, "product_template=self.PRODUCT_TEMPLATE", "Yellow-fabric product guard missing from opener")
    require(yellow_fabric, "self.slots._wait_for_idle_open_panel(", "Yellow-fabric open-panel wait missing")
    require(yellow_fabric, "ProductionActions(context, vision, waiter, self.speed_config)", "Yellow-fabric collect speed is not handed to shared opener")
    forbid(yellow_fabric, "MAX_OPEN_CLICKS", "Yellow-fabric click-until-panel must not have an arbitrary open limit")
    require(yellow_fabric, "current >= empty_after", "Yellow-fabric per-drag gate missing")
    require(yellow_fabric, "empty_before - empty_after != self.REQUIRED_COUNT", "Yellow-fabric post-accounting missing")
    require(yellow_fabric, "self.speed_config.vp_production_delay", "Yellow-fabric production speed binding missing")
    require(yellow_fabric, "close_after_success: bool = True", "Yellow-fabric panel handoff switch missing")

    # Warehouse-full recovery is a Function-level business transition, not a
    # generic retry of image failures. It sells Function-owned VP and returns to
    # the exact production floor before retrying only that production call.
    require(warehouse_recovery, "except InventoryFull as exc:", "Warehouse recovery must catch only InventoryFull")
    forbid(warehouse_recovery, "except ScreenTimeout", "Warehouse recovery must not swallow visual failures")
    require(warehouse_recovery, "AutoVpSaleWorkflow(", "Warehouse recovery sale module missing")
    require(warehouse_recovery, "allowed_item_ids=self.spec.sale_item_ids", "Warehouse recovery sale is not Function-bound")
    require(warehouse_recovery, "if int(sale.sold_listings) <= 0:", "Warehouse recovery infinite-loop guard missing")
    require(warehouse_recovery, "self._to_main(floor, label)", "Warehouse recovery does not descend before sale")
    require(warehouse_recovery, "self._back_to_floor(floor, label)", "Warehouse recovery does not return to production floor")
    require(function_nav, "def floor_1_to_main", "Floor-1 warehouse recovery route missing")
    require(function_nav, "def main_to_floor_1", "Main-to-floor-1 recovery route missing")
    require(warehouse_recovery, "self.auto.function_one_pass_three_navigation.floor_2_to_main()", "Floor-2 warehouse recovery descent missing")
    require(warehouse_recovery, "self.auto.function_one_pass_three_navigation.floor_3_to_main_via_down_floor()", "Floor-3 warehouse recovery descent missing")

    # Machine repair is allowed only from a fully verified, still-open panel.
    require(automation, "self.machine_repair = MachineRepairActions(", "Resident machine repair wiring missing")
    require(machine_repair, "def repair_after_production", "Production→repair handoff API missing")
    require(machine_repair, "queued != requested or consumed != requested", "Repair handoff exact accounting gate missing")
    require(machine_repair, "OPEN_REPAIR_POINT = (165, 856)", "Repair ? coordinate changed")
    require(machine_repair, "REPAIR_BUTTON_POINT = (730, 596)", "Repair button coordinate changed")
    require(machine_repair, "CLOSE_MODAL_POINT = (652, 284)", "Repair modal close coordinate changed")
    require(machine_repair, "MIN_MODAL_CHANGE", "Repair modal-open visual gate missing")
    require(machine_repair, "MIN_REPAIR_CHANGE", "Repair response visual gate missing")
    require(machine_repair, "MIN_CLOSE_CHANGE", "Repair modal-close visual gate missing")
    forbid(machine_repair, "OCR", "Repair runtime must never depend on OCR price")

    require(workflow, "self.warehouse_recovery.run_production(", "Dried-apple warehouse recovery wrapper missing")
    require(workflow, "floor=1", "Dried-apple warehouse recovery floor binding missing")
    require(workflow, "producer=lambda: self.auto.production.produce_9_dried_apples(", "Dried-apple recovery does not retry only production")
    require(workflow, "close_after_success=False", "Dried-apple production does not keep panel open for repair")
    require(workflow, "self.auto.machine_repair.repair_after_production(produced)", "Dried-apple machine repair missing")
    require(function_one, "self.warehouse_recovery.run_production(", "Function-1 warehouse recovery wrapper missing")
    require(function_one, "floor=2", "Apple-juice warehouse recovery floor binding missing")
    require(function_one, "producer=lambda: self.auto.apple_juice_production.produce_9_apple_juices(", "Apple-juice recovery does not retry only production")
    require(function_one, "self.auto.machine_repair.repair_after_production(juice)", "Apple-juice machine repair missing")
    require(function_one, "floor=3", "Yellow-fabric warehouse recovery floor binding missing")
    require(function_one, "producer=lambda: self.auto.yellow_fabric_production.produce_9_yellow_fabrics(", "Yellow-fabric recovery does not retry only production")
    require(function_one, "self.auto.machine_repair.repair_after_production(fabric)", "Yellow-fabric machine repair missing")

    require(cotton, 'COTTON_TEMPLATE = "cay_bong"', "Cotton template id changed")
    require(cotton, "if not self.vision.assets.has(self.COTTON_TEMPLATE):", "Cotton asset fail-close missing")
    require(cotton, "path = (seed.center,) + self.rose_path()[1:]", "Cotton 27-pot geometry changed")
    require(cotton, "non_blocking=true", "Cotton postcheck must remain diagnostic")
    forbid(cotton, "if changed != self.TREE_COUNT:", "Cotton diagnostic became blocking")
    require(pass_three_nav, "def floor_2_to_main", "Post-juice main route missing")
    require(pass_three_nav, '"post-juice-goDown(1)-probe-1-of-4"', "Post-juice first down probe missing")
    require(pass_three_nav, '"post-juice-goDown(1)-settle-4-of-4"', "Post-juice settling route incomplete")
    require(pass_three_nav, "def floor_1_to_floor_3", "Floor1→floor3 route missing")

    # End-loop and unknown-floor recovery must consume the transient XUỐNG control
    # by visual proof. The historical (497,978) coordinate may remain documented,
    # but it must never be used as a blind runtime click.
    require(pass_three_nav, "from ..runtime.down_floor_button import find_down_floor_button", "Down-floor detector wiring missing")
    require(pass_three_nav, "DOWN_FLOOR_BUTTON_THRESHOLD = 0.78", "Down-floor detector threshold changed")
    require(pass_three_nav, "def _click_down_floor_if_visible", "Visual down-floor click helper missing")
    require(pass_three_nav, "match = find_down_floor_button(", "Down-floor visual probe missing")
    require(pass_three_nav, "self.vision.driver.click(*match.center)", "Detected down-floor center is not clicked")
    forbid(pass_three_nav, "self.vision.driver.click(*self.DOWN_FLOOR_POINT)", "Blind fixed-coordinate down-floor click returned")
    require(pass_three_nav, "if click_change < self.MIN_CHANGE:", "Down-floor fresh-frame fail-close missing")
    require(pass_three_nav, "RECOVERY_DOWN_CHAIN_LIMIT = 10", "Upper-floor recovery chain limit changed")
    require(pass_three_nav, "for step in range(1, self.RECOVERY_DOWN_CHAIN_LIMIT + 1):", "Upper-floor down-button chain missing")
    require(pass_three_nav, "def floor_3_to_main_via_down_floor", "End-loop down-floor route missing")
    require(pass_three_nav, '"function1-end-loop-floor3-goDown(1)"', "End-loop exactly-one goDown(1) missing")

    require(down_floor_detector, "def find_down_floor_button(", "Down-floor detector implementation missing")
    require(down_floor_detector, "_TEMPLATE_PNG_B64", "Embedded down-floor template missing")
    require(down_floor_detector, "width * 0.38", "Down-floor detector left search bound changed")
    require(down_floor_detector, "width * 0.62", "Down-floor detector right search bound changed")
    require(down_floor_detector, "height * 0.935", "Down-floor detector bottom-strip search bound changed")
    require(down_floor_detector, "cv2.TM_CCOEFF_NORMED", "Down-floor normalized matching missing")

    require(function_one, "self.auto.function_one_pass_three_navigation.floor_3_to_main_via_down_floor()", "Function-1 does not use down-floor route")
    require(function_one, 'self._require_main_transition("cuối vòng Function 1 tầng 3 → main")', "End-loop exact-main gate missing")
    require(function_one, "self._normalize_end_of_loop_to_main()", "Function-1 does not normalize before loop completion")
    forbid(function_one, "open_own_stall", "End-loop must not use stall/quầy")
    forbid(function_one, "END_LOOP_MAIN_MAX_SWIPES", "Obsolete six-goDown end-loop route returned")

    require(function_one, "progress_steps=3", "Function 1 result progress changed")
    require(function_one, "total_steps=3", "Function 1 result total changed")

    require(auto_main, "FunctionModule(automation)", "Selected Function dispatcher missing")
    require(auto_main, 'self.spec.runner_key == "function_1"', "Function-1 completion branch missing")
    require(auto_main, 'payload.get("progress_steps"', "Function-1 progress guard missing")
    require(auto_main, 'payload.get("yellow_fabrics"', "Function-1 yellow-fabric guard missing")
    require(auto_main, 'payload.get("cotton_planted"', "Function-1 cotton guard missing")
    require(auto_main, "self._validate_function_result(payload)", "Scheduler Function validation missing")
    require(auto_main, "function_loop_delay_seconds: float = 0.0", "AUTO Main Function loop delay input missing")
    require(auto_main, "self._wait_before_next_function_loop()", "AUTO Main between-loop wait missing")
    require(auto_main, "while True:", "AUTO Main recurring loop missing")
    require(auto_main, "self.context.ensure_running()", "AUTO Main stop checkpoints missing")

    require(automation, "self.production = ProductionActions(", "Resident production wiring missing")
    require(automation, "self.cotton_planting = CottonPlantingActions(", "Resident cotton wiring missing")
    require(automation, "self.yellow_fabric_production = YellowFabricProductionActions(", "Resident yellow-fabric wiring missing")
    require(automation, "self.function_one_pass_three_navigation = FunctionOnePassThreeNavigationActions(", "Resident pass-3 navigation wiring missing")
    require(dev, 'text="↟ Demo Auto Pro tới tầng 6"', "Dedicated floor demo button missing")
    require(auto_multi_worker, "automation.floors.reference_main_to_floor_6()", "Floor demo target-6 state machine missing")
    require(auto_multi_worker, "function_id=function_id", "Worker selected Function handoff missing")
    require(auto_multi_worker, "sale_every_loops=sale_every", "Worker recurring sale handoff missing")
    require(auto_multi_worker, "function_loop_delay_seconds=loop_delay", "Worker Function loop delay handoff missing")
    require(floor_action, "AUTO_PRO_GO_UP_4_SWIPE = (387, 69, 387, 918)", "Auto Pro goUp(4) geometry missing")

    for token in ("clear_stall_probe_runtime", "adb_controller.pyc"):
        for text in (
            action, workflow, function_one, function_nav, warehouse_recovery,
            yellow_fabric, cotton, pass_three_nav,
        ):
            forbid(text, token, f"Production path touches stable/legacy path: {token}")

    print("AUTO MULTI DEV FUNCTION ONE STATIC CONTRACT VERIFIED")
    print("runtime=isolated_worker_v3")
    print("startup=enter-game-popup-only-no-godown")
    print("production=five-click-collect-until-product-anchor-panel+keep-open-wait-9-of-9+repair-after-each")
    print("panel_open_gate=product-library-zone-only;empty-slot-diagnostic-only")
    print("panel_product_miss=nonfatal-recheck-no-auto-stop")
    print("warehouse_full=InventoryFull->exact-main->function-vp-sale->same-floor-retry")
    print("machine_repair=verified_handoff+no_price_ocr")
    print("vp_collect_speed=independent")
    print("function_loop_delay=visible-main-control+between-loops-only")
    print("post_juice_navigation=1_plus_3_godown1_boundary_non_blocking_exact_main_gate")
    print("end_loop_navigation=floor3_one_godown1+visual_down_button+fresh_frame+exact_main")
    print("upper_floor_recovery=godown1+visual_down_button_chain_up_to_10+boundary_fallback")
    print("next_loop=main_required_before_restart")
    print("stable_sale_and_clear_stall=untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())