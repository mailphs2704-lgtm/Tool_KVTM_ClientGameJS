from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "components/clientjs-auto/kvtm_automation"
CONTEXT = CLEAN / "context.py"
POPUP = CLEAN / "actions/popup.py"
FUNCTION_NAV = CLEAN / "actions/function_one_navigation.py"
PASS_THREE_NAV = CLEAN / "actions/function_one_pass_three_navigation.py"
ACTIONS_INIT = CLEAN / "actions/__init__.py"
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
    function_nav = read(FUNCTION_NAV)
    pass_nav = read(PASS_THREE_NAV)
    actions_init = read(ACTIONS_INIT)
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

    # Every normal vertical gesture invalidates old proof; only deterministic
    # routes ending at main may mark it true again.
    require(function_nav, "self.context.invalidate_camera_main", "Vertical gesture does not invalidate camera proof")
    require(function_nav, 'mark_camera_exact_main("floor1-to-main deterministic route")', "Floor1→main runtime proof missing")
    require(function_nav, 'mark_camera_exact_main("floor6-to-main deterministic route")', "Floor6→main runtime proof missing")

    # Unknown-state recovery must use repeated no-motion goDown evidence. Values
    # are locked to the live 2026-09-09 separation: movement 15.74/71.06 versus
    # boundary noise 2.53..2.94. Two consecutive lows prevent a single stale frame.
    require(pass_nav, "MAIN_BOUNDARY_MAX_CHANGE = 6.0", "Main-boundary change threshold changed")
    require(pass_nav, "MAIN_BOUNDARY_STABLE_REQUIRED = 2", "Main-boundary stable evidence count changed")
    require(pass_nav, "self.context.observe_camera_down_boundary(", "goDown boundary observer is not wired")
    require(pass_nav, "if exact and not was_exact:", "Boundary PASS transition guard missing")
    require(pass_nav, "không phụ thuộc background", "Background-independent policy marker missing")
    require(pass_nav, 'mark_camera_exact_main("floor2-to-main 1+3 deterministic route")', "Floor2→main deterministic proof missing")
    require(pass_nav, '"floor3-to-main-via-down-floor deterministic route"', "Floor3→main deterministic proof missing")

    # Initial AUTO VP sale is the first business action after game entry. It must
    # prove the lower boundary itself, then open the own stall from canonical
    # logical geometry. The account-specific quay_hang world artwork must not be
    # a pre-click gate; quay_hang_on remains the stable post-click panel proof.
    require(auto_vp_sale, "def _normalize_exact_main_for_sale", "Sale exact-main normalizer missing")
    require(auto_vp_sale, "go_down_one_toward_main(", "Sale does not behaviorally prove exact-main")
    require(auto_vp_sale, "self.auto.popup.is_own_exact_main_screen()", "Sale does not consume runtime exact-main proof")
    require(auto_vp_sale, "def _open_own_stall_from_exact_main", "Background-independent own-stall entry missing")
    require(auto_vp_sale, "stall.OWN_STALL_ENTRY_POINT", "Sale does not use canonical own-stall entry geometry")
    require(auto_vp_sale, '"quay_hang_on", threshold=0.80', "Own-stall active panel postcheck missing")
    require(auto_vp_sale, "background_gate=disabled", "Own-stall background-exclusion marker missing")
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

    # The two live shortage popups supplied at native 500 are now one typed
    # production boundary. Product context selects the crop: Táo sấy/Nước táo ->
    # cay_tao, Vải vàng -> cay_bong. LOW_STOCK may have already accepted the drag,
    # so a fresh empty-slot delta must decide whether ordinal N is complete.
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
    require(material_actions, "def replenish_27_cotton_from_floor_1", "Cotton replenisher missing")
    require(actions_init, "MaterialAwareProductionActions as ProductionActions", "Dried-apple shortage guard not wired")
    require(actions_init, "MaterialAwareAppleJuiceProductionActions as AppleJuiceProductionActions", "Apple-juice shortage guard not wired")
    require(actions_init, "MaterialAwareYellowFabricProductionActions as YellowFabricProductionActions", "Yellow-fabric shortage guard not wired")
    require(actions_init, "MaterialAwareCottonPlantingActions as CottonPlantingActions", "Cotton replenisher not wired")
    require(actions_init, "MaterialAwareMachineRepairActions as MachineRepairActions", "Recovered production handoff not wired")

    # Recovery must route through exact-main, replenish only the crop carried by
    # MaterialShortage, then return to the same production floor. Apple policy is
    # locked to the requested three passes of the already-proven five-floor
    # harvest/replant routine; its internal per-pass tree count remains owned by
    # AppleSupplyActions rather than fabricated here.
    require(recovery_events, 'MATERIAL_SHORTAGE = "material_shortage"', "Material recovery event kind missing")
    require(recovery_init, "MaterialAwareRecoveryManager as RecoveryManager", "Material-aware RecoveryManager not wired")
    require(material_recovery, "APPLE_FIVE_FLOOR_ROUNDS = 3", "Apple shortage recovery is not three five-floor passes")
    require(material_recovery, 'if material == "cay_tao":', "Apple dispatcher branch missing")
    require(material_recovery, 'if material == "cay_bong":', "Cotton dispatcher branch missing")
    require(material_recovery, "wait_until_floor_1_ripe()", "Apple recovery does not wait for ripe crop")
    require(material_recovery, "harvest_and_replant_five_floors()", "Apple five-floor harvest/replant call missing")
    require(material_recovery, "replenish_27_cotton_from_floor_1()", "Cotton harvest/replant call missing")
    require(material_recovery, "self.navigation.to_main_from_floor(", "Material recovery does not return machine floor to main")
    require(material_recovery, "self.navigation.from_main_to_floor(", "Material recovery does not re-enter target floor")
    require(material_recovery, "chỉ xếp tiếp còn=", "Resume-only-remaining log marker missing")

    # Existing worker/function recovery paths may keep calling the exact-main
    # predicate because that predicate is now runtime-proof based; ensure they do
    # not bypass it with the legacy quay_hang world anchor.
    require(worker, "_recover_auto_main_to_main_screen", "AUTO Main recovery helper missing")
    require(worker, "automation.popup.is_own_exact_main_screen()", "Worker no longer consumes runtime exact-main proof")
    require(function_one, "self.auto.popup.is_own_exact_main_screen()", "Function transitions no longer require exact-main proof")
    require(warehouse, "self.auto.popup.is_own_exact_main_screen()", "Warehouse recovery no longer requires exact-main proof")

    print("AUTO MULTI DEV MAIN BOUNDARY CONTRACT VERIFIED")
    print("own_farm=fixed_hud")
    print("exact_main=runtime_navigation_proof")
    print("unknown_camera=bounded_godown_until_two_low_change_frames")
    print("sale_entry=exact-main-proof->fixed-own-stall-point->quay_hang_on")
    print("sale_dialog=native500:dat_ban|orange;native1000:dat_ban-strict")
    print("sale_x10=native500-multiscale-two-pass|native1000-strict-two-pass")
    print("sale_postcheck=destructive-screen-change")
    print("popup_blocker=proportional-500-or-1000")
    print("material_shortage=NOT_ENOUGH+LOW_STOCK->typed-crop-recovery")
    print("material_dispatch=cay_tao|cay_bong")
    print("apple_shortage=main->floor1->five-floor-harvest-replant-x3->main")
    print("production_resume=verified-progress->remaining-only")
    print("background_world_anchor=forbidden_as_runtime_gate")
    print("boundary_change_max=6.0")
    print("boundary_stable_required=2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
