from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "components/clientjs-auto/kvtm_automation"
CONTEXT = CLEAN / "context.py"
POPUP = CLEAN / "actions/popup.py"
FLOOR_NAV = CLEAN / "actions/floor_navigation.py"
FARM_ROUTES = CLEAN / "actions/farm_routes.py"
FUNCTION_NAV = CLEAN / "actions/function_one_navigation.py"
PASS_THREE_NAV = CLEAN / "actions/function_one_pass_three_navigation.py"
ACTIONS_INIT = CLEAN / "actions/__init__.py"
COTTON_ACTIONS = CLEAN / "actions/cotton_planting.py"
SELLING = CLEAN / "actions/selling.py"
AUTO_MAIN_SELLING = CLEAN / "actions/auto_main_selling.py"
MATERIAL_SIGNAL = CLEAN / "material_shortage.py"
MATERIAL_ACTIONS = CLEAN / "actions/material_shortage_production.py"
RECOVERY_INIT = CLEAN / "recovery/__init__.py"
RECOVERY_EVENTS = CLEAN / "recovery/events.py"
MATERIAL_RECOVERY = CLEAN / "recovery/material_shortage.py"
WORKER = ROOT / "components/clientjs-auto/worker/auto_multi_dev_worker.py"
FUNCTION_ONE = CLEAN / "workflows/auto_function_one/workflow.py"
AUTO_VP_SALE = CLEAN / "workflows/auto_vp_sale/workflow.py"
WAREHOUSE = CLEAN / "workflows/production_warehouse_recovery.py"


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing main-boundary contract file: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(text, filename=str(path))
    return text


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def forbid(text: str, token: str, message: str) -> None:
    if token in text:
        raise AssertionError(message)


def main() -> int:
    context = read(CONTEXT)
    popup = read(POPUP)
    floor_nav = read(FLOOR_NAV)
    farm_routes = read(FARM_ROUTES)
    function_nav = read(FUNCTION_NAV)
    pass_nav = read(PASS_THREE_NAV)
    actions_init = read(ACTIONS_INIT)
    cotton_actions = read(COTTON_ACTIONS)
    selling = read(SELLING)
    auto_main_selling = read(AUTO_MAIN_SELLING)
    material_signal = read(MATERIAL_SIGNAL)
    material_actions = read(MATERIAL_ACTIONS)
    recovery_init = read(RECOVERY_INIT)
    recovery_events = read(RECOVERY_EVENTS)
    material_recovery = read(MATERIAL_RECOVERY)
    worker = read(WORKER)
    function_one = read(FUNCTION_ONE)
    auto_vp_sale = read(AUTO_VP_SALE)
    warehouse = read(WAREHOUSE)

    # Exact-main is runtime state, not a world/background image classifier.
    require(context, "camera_exact_main_proven", "Runtime exact-main proof state missing")
    require(context, "camera_main_boundary_streak", "Main-boundary stable streak missing")
    require(context, "def invalidate_camera_main", "Camera proof invalidation API missing")
    require(context, "def mark_camera_exact_main", "Deterministic route proof API missing")
    require(context, "def observe_camera_down_boundary", "Behavioral boundary observer missing")

    require(popup, "def is_own_exact_main_screen", "Exact-main compatibility predicate missing")
    require(popup, "self.context.camera_exact_main_proven", "Exact-main predicate is not runtime-proof based")
    require(popup, "return self.is_own_main_screen()", "Exact-main must still require own-farm HUD")
    require(popup, 'invalidate_camera_main("ensure-farm-hud-camera-unknown")', "Farm recovery can carry stale camera proof")
    forbid(popup, "stall = self.vision.find(", "World-space stall image returned as exact-main runtime gate")
    forbid(popup, "return stall is not None", "Exact-main still depends on account background artwork")

    # Popup geometry must remain proportional so both supported native tables
    # (500x500 and 1000x1000) can use the same logical contract safely.
    require(popup, "if width < 200 or height < 200:", "Popup blocker detector does not accept supported native frames")
    require(popup, "int(height * 0.28):int(height * 0.72)", "Popup center geometry is no longer proportional")
    forbid(popup, "if width < 900 or height < 900:", "Popup blocker detector still rejects native 500 capture")

    # Vertical primitive ownership was standardized into FloorNavigationActions.
    # Every primitive invalidates stale exact-main proof before input; deterministic
    # route composers in farm_routes.py are the only normal routes allowed to
    # mark exact-main true again.
    require(floor_nav, "def _prepare_camera_input", "Shared floor primitive preparation missing")
    require(floor_nav, "self.context.invalidate_camera_main", "Vertical primitive does not invalidate camera proof")
    require(farm_routes, 'mark_camera_exact_main(\n            "floor1-to-main deterministic route"', "Floor1→main runtime proof missing")
    require(farm_routes, 'mark_camera_exact_main(\n            "floor6-to-main deterministic route"', "Floor6→main runtime proof missing")

    # Historical Function 1 navigation files are compatibility wrappers only.
    require(function_nav, "class FunctionOneNavigationActions(FarmRouteActions):", "Function 1 navigation is not a thin FarmRouteActions wrapper")
    require(pass_nav, "class FunctionOnePassThreeNavigationActions(FarmBoundaryRouteActions):", "Function 1 boundary navigation is not a thin FarmBoundaryRouteActions wrapper")
    forbid(function_nav, "def floor_1_to_main", "Function 1 wrapper regained route implementation")
    forbid(pass_nav, "def floor_2_to_main", "Function 1 boundary wrapper regained route implementation")

    # Unknown-state recovery must use repeated no-motion goDown evidence. Values
    # are locked to the live 2026-09-09 separation: movement 15.74/71.06 versus
    # boundary noise 2.53..2.94. Two consecutive lows prevent a single stale frame.
    require(farm_routes, "MAIN_BOUNDARY_MAX_CHANGE = 6.0", "Main-boundary change threshold changed")
    require(farm_routes, "MAIN_BOUNDARY_STABLE_REQUIRED = 2", "Main-boundary stable evidence count changed")
    require(farm_routes, "self.context.observe_camera_down_boundary(", "goDown boundary observer is not wired")
    require(farm_routes, "if exact and not was_exact:", "Boundary PASS transition guard missing")
    require(farm_routes, 'mark_camera_exact_main(\n            "floor2-to-main 1+3 deterministic route"', "Floor2→main deterministic proof missing")

    # Known upper floors now share one deterministic goDown(1)+XUỐNG route.
    # The live Step-3 regression showed that template-only proof could miss the
    # bottom button, so the shared route must retain the operator-point fallback
    # and require visible frame response before marking exact MAIN.
    require(farm_routes, "def known_upper_floor_to_main_via_down_floor", "Shared upper-floor→MAIN route missing")
    require(farm_routes, "DOWN_FLOOR_POINT = (497, 978)", "Operator down-floor fallback point changed")
    require(farm_routes, 'f"{label} via goDown(1)+down-floor deterministic route"', "Shared upper-floor deterministic proof missing")
    require(farm_routes, "fallback operator point=", "Down-floor template-miss fallback audit missing")
    require(farm_routes, "self.vision.driver.click(*self.DOWN_FLOOR_POINT)", "Down-floor fixed fallback click missing")
    require(farm_routes, "if click_change < self.MIN_CHANGE:", "Down-floor fallback response guard missing")
    require(farm_routes, 'known_upper_floor_to_main_via_down_floor(\n            "tầng 3 → MAIN"', "Floor3→MAIN does not use shared down-floor route")
    require(farm_routes, 'known_upper_floor_to_main_via_down_floor(\n            "tầng 5 → MAIN"', "Floor5→MAIN does not use shared down-floor route")
    require(farm_routes, 'known_upper_floor_to_main_via_down_floor(\n            "tầng 6 → MAIN"', "Floor6→MAIN does not use shared down-floor route")

    # Sale consumes an exact-main handoff from Startup/Function boundary. It must
    # not manufacture exact-main by sending hidden goDown gestures. Own-stall entry
    # remains fixed logical geometry with quay_hang_on as the post-click proof.
    require(auto_vp_sale, "def _require_sale_entry_main", "Sale exact-main entry gate missing")
    require(auto_vp_sale, "self.auto.popup.is_own_exact_main_screen()", "Sale does not consume runtime exact-main proof")
    require(auto_vp_sale, "Sale không tự goDown(1) để sửa camera", "Sale hidden-navigation prohibition marker missing")
    forbid(auto_vp_sale, "go_down_one_toward_main(", "Sale regressed to hidden goDown exact-main recovery")
    require(auto_vp_sale, "def _open_own_stall_from_exact_main", "Background-independent own-stall entry missing")
    require(auto_vp_sale, "stall.OWN_STALL_ENTRY_POINT", "Sale does not use canonical own-stall entry geometry")
    require(auto_vp_sale, '"quay_hang_on", threshold=0.80', "Own-stall active panel postcheck missing")
    forbid(auto_vp_sale, "self.auto.stall.open_own_stall()", "Sale returned to legacy quay_hang-gated stall entry")

    # Sale dialog proof is selected from the ClientJS native size without
    # resizing the client. Native500 keeps the calibrated tolerant dat_ban +
    # orange-button fallback. Native1000 keeps the recovered strict dat_ban
    # baseline and must never inherit the 500-only orange fallback.
    require(selling, "PLACE_BUTTON = (771, 692)", "Canonical sale click point changed")
    require(selling, "PLACE_BUTTON_ZONE = (700, 650, 180, 90)", "Native sale-button geometry zone missing")
    require(selling, "N500_SALE_DIALOG_THRESHOLD = 0.68", "Native500 sale dialog threshold changed")
    require(selling, "N500_SALE_DIALOG_SCALES = (0.85, 1.00, 1.15, 1.30, 1.45, 1.60, 1.75)", "Native500 sale dialog scales changed")
    require(selling, "N500_SALE_BUTTON_ORANGE_MIN = 0.08", "Native500 orange sale-button threshold changed")
    require(selling, "N1000_SALE_DIALOG_THRESHOLD = 0.78", "Native1000 sale dialog baseline changed")
    require(selling, "N1000_SALE_DIALOG_SCALES = (1.00,)", "Native1000 sale dialog scale changed")
    require(selling, "def _sale_dialog_profile", "Resolution-specific sale dialog table missing")
    require(selling, "self.N500_SALE_DIALOG_THRESHOLD", "Native500 sale table not selected")
    require(selling, "self.N1000_SALE_DIALOG_THRESHOLD", "Native1000 sale table not selected")
    require(selling, "def _sale_button_orange_ratio", "Native500 sale-button color proof missing")
    require(selling, "def is_sale_dialog_ready", "Sale dialog resolution proof missing")
    require(selling, "source=native-500-orange-button", "Native500 sale-button runtime evidence missing")
    require(selling, "if allow_orange:", "Native500-only orange fallback guard missing")
    require(selling, "def wait_sale_dialog_ready", "Bounded sale-dialog waiter missing")
    require(selling, "self.vision.driver.click(*self.PLACE_BUTTON)", "Sale no longer clicks canonical logical place button")
    require(selling, "best_change >= self.minimum_screen_change", "Destructive sale screen-change postcheck missing")
    forbid(selling, "SALE_DIALOG_TEMPLATE_THRESHOLD = 0.68", "Legacy single-resolution sale dialog constant returned")

    # Exact-x10 is also a static resolution table selected from the current
    # native ClientJS. Native500 keeps the calibrated multiscale two-pass proof;
    # native1000 keeps the recovered strict 0.95 / scale-1 baseline. The call
    # site must use the selected table rather than hardcoding either resolution.
    require(auto_main_selling, "N500_EXACT_TEN_THRESHOLD = 0.78", "Native500 AUTO Main x10 threshold changed")
    require(auto_main_selling, "N500_EXACT_TEN_SCALES = (0.75, 0.90, 1.00, 1.10, 1.25, 1.40, 1.55)", "Native500 AUTO Main x10 scales changed")
    require(auto_main_selling, "N1000_EXACT_TEN_THRESHOLD = 0.95", "Native1000 AUTO Main x10 threshold changed")
    require(auto_main_selling, "N1000_EXACT_TEN_SCALES = (1.00,)", "Native1000 AUTO Main x10 scale changed")
    require(auto_main_selling, "EXACT_TEN_REQUIRED_PASSES = 2", "AUTO Main x10 two-frame proof missing")
    require(auto_main_selling, "def _exact_ten_profile", "AUTO Main x10 resolution table selector missing")
    require(auto_main_selling, "exact_threshold, exact_scales, table_name = self._exact_ten_profile()", "AUTO Main x10 table selection not wired")
    require(auto_main_selling, "self.selling.wait_sale_dialog_ready(", "AUTO Main still requires direct dat_ban-only gate")
    require(auto_main_selling, "threshold=exact_threshold", "AUTO Main x10 proof does not use selected threshold")
    require(auto_main_selling, "scales=exact_scales", "AUTO Main x10 proof does not use selected scales")
    require(auto_main_selling, "sale dialog READY + x10 PASS", "AUTO Main pre-click proof log missing")
    require(auto_main_selling, "best_change >= self.selling.minimum_screen_change", "AUTO Main destructive screen-change postcheck missing")
    forbid(auto_main_selling, '"sl10",\n                threshold=0.95', "Hardcoded native1000 x10 call returned")

    # The two live shortage popups supplied at native 500 are one typed production
    # boundary. Product context selects the crop and resume-state keeps accepted
    # queue gestures. Crop replenishment itself is a neutral Action; Recovery owns
    # why it is called and the route back to the interrupted machine.
    require(material_signal, "class MaterialShortage(ScreenTimeout)", "Typed material shortage signal missing")
    require(material_signal, "def remaining_count", "Material shortage does not preserve remaining count")
    require(material_signal, "drag_consumed_slot", "Shortage evidence does not record accepted drag")
    require(material_actions, 'kind = "NOT_ENOUGH"', "NOT_ENOUGH popup variant missing")
    require(material_actions, 'else "LOW_STOCK"', "LOW_STOCK popup variant missing")
    require(material_actions, "SHORTAGE_MODAL_ZONE", "Shortage modal geometry guard missing")
    require(material_actions, "SHORTAGE_GREEN_RATIO_MIN = 0.55", "Shortage green-geometry threshold changed")
    require(material_actions, "consumed = current_empty < int(empty_before)", "Shortage does not postcheck current drag")
    require(material_actions, 'MATERIAL_TEMPLATE = "cay_tao"', "Apple material mapping missing")
    require(material_actions, 'MATERIAL_TEMPLATE = "cay_bong"', "Cotton material mapping missing")
    require(material_actions, "verified_queue_events=self.REQUIRED_COUNT", "Cross-recovery queue proof missing")
    require(cotton_actions, "def wait_harvest_and_replant_27_cotton", "Neutral 27-cotton batch Action missing")
    require(actions_init, "MaterialAwareProductionActions as ProductionActions", "Dried-apple shortage guard not wired")
    require(actions_init, "MaterialAwareAppleJuiceProductionActions as AppleJuiceProductionActions", "Apple-juice shortage guard not wired")
    require(actions_init, "MaterialAwareYellowFabricProductionActions as YellowFabricProductionActions", "Yellow-fabric shortage guard not wired")
    require(actions_init, "MaterialAwareCottonPlantingActions as CottonPlantingActions", "Cotton replenisher compatibility layer not wired")
    require(actions_init, "MaterialAwareMachineRepairActions as MachineRepairActions", "Recovered production handoff not wired")

    # Recovery routes through exact-main, chooses crop by the typed signal, calls
    # the neutral crop Action, returns to the same machine floor and lets producer
    # resume only the still-unverified remainder.
    require(recovery_events, 'MATERIAL_SHORTAGE = "material_shortage"', "Material recovery event kind missing")
    require(recovery_init, "MaterialAwareRecoveryManager as RecoveryManager", "Material-aware RecoveryManager not wired")
    require(material_recovery, "APPLE_FIVE_FLOOR_ROUNDS = 3", "Apple shortage recovery is not three five-floor passes")
    require(material_recovery, 'if material == "cay_tao":', "Apple dispatcher branch missing")
    require(material_recovery, 'if material == "cay_bong":', "Cotton dispatcher branch missing")
    require(material_recovery, "wait_until_floor_1_ripe()", "Apple recovery does not wait for ripe crop")
    require(material_recovery, "harvest_and_replant_five_floors()", "Apple five-floor harvest/replant call missing")
    require(material_recovery, "wait_harvest_and_replant_27_cotton()", "Cotton recovery does not use neutral crop batch Action")
    forbid(material_recovery, "replenish_27_cotton_from_floor_1()", "Recovery regressed to recovery-named crop Action")
    require(material_recovery, "self.navigation.to_main_from_floor(", "Material recovery does not return machine floor to main")
    require(material_recovery, "self.navigation.from_main_to_floor(", "Material recovery does not re-enter target floor")
    require(material_recovery, "chỉ xếp tiếp còn=", "Resume-only-remaining log marker missing")

    # Worker is a lifecycle host, not a second recovery engine. Startup hands it
    # exact-main; registered typed recovery stays below in RecoveryManager and any
    # unregistered exception must fail-close without MAIN-normalize/rerun.
    require(worker, "GameSessionWorkflow(automation).run(timeout=args.timeout)", "Worker startup session gate missing")
    require(worker, "automation.popup.is_own_exact_main_screen()", "Worker no longer consumes startup exact-main proof")
    require(worker, "ClientRestartRequested", "Scheduled restart lifecycle signal missing")
    require(worker, "unregistered_runtime_error; recovery=fail-close", "Worker fail-close marker missing")
    forbid(worker, "_recover_auto_main_to_main_screen", "Worker catch-all MAIN recovery helper returned")
    require(function_one, "self.auto.popup.is_own_exact_main_screen()", "Function transitions no longer require exact-main proof")
    require(warehouse, "self.auto.popup.is_own_exact_main_screen()", "Warehouse compatibility recovery no longer requires exact-main proof")

    print("AUTO MULTI DEV MAIN BOUNDARY CONTRACT VERIFIED")
    print("own_farm=fixed_hud")
    print("exact_main=runtime_navigation_proof")
    print("navigation_owner=floor_navigation+farm_routes")
    print("function_navigation=compatibility-wrappers-only")
    print("unknown_camera=bounded_godown_until_two_low_change_frames")
    print("known_upper_floor=shared-godown1+down-button-template-or-operator-point+frame-response")
    print("sale_entry=caller-exact-main->fixed-own-stall-point->quay_hang_on")
    print("sale_hidden_navigation=forbidden")
    print("sale_dialog=native500:dat_ban|orange;native1000:dat_ban-strict")
    print("sale_x10=native500-multiscale-two-pass|native1000-strict-two-pass")
    print("sale_postcheck=destructive-screen-change")
    print("popup_blocker=proportional-500-or-1000")
    print("material_shortage=NOT_ENOUGH+LOW_STOCK->typed-crop-recovery")
    print("material_dispatch=cay_tao|cay_bong")
    print("cotton_replenishment=neutral-crop-action")
    print("apple_shortage=main->floor1->five-floor-harvest-replant-x3->main")
    print("production_resume=verified-progress->remaining-only")
    print("worker_unregistered_error=fail-close")
    print("background_world_anchor=forbidden_as_runtime_gate")
    print("boundary_change_max=6.0")
    print("boundary_stable_required=2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
