from __future__ import annotations

"""Static contract for the isolated AUTO MULTI DEV VP sale flow."""

import ast
from pathlib import Path

from verify_auto_builder_contract import main as verify_auto_builder_contract


ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "components/clientjs-auto/kvtm_automation/actions/auto_main_selling.py"
SELLING = ROOT / "components/clientjs-auto/kvtm_automation/actions/selling.py"
INVENTORY = ROOT / "components/clientjs-auto/kvtm_automation/actions/inventory.py"
WORKFLOW = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_vp_sale/workflow.py"
RECOGNITION = ROOT / "components/clientjs-auto/kvtm_automation/actions/item_recognition.py"
ERRORS = ROOT / "components/clientjs-auto/kvtm_automation/errors.py"
CORE_GUI = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi.py"
INTEGRATION = ROOT / "source-archive/multi-current/kvtm_multi_tool/auto_builder_integration.py"
DEV_ENTRY = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_entry.py"
AUTO_MAIN = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_main/workflow.py"
FRIEND_REFRESH = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_main/friend_refresh.py"
AUTO_MULTI_WORKER = ROOT / "components/clientjs-auto/worker/auto_multi_dev_worker.py"
CATALOG = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_builder/catalog.py"

FILE_FUNCTIONS = (
    "Khóa sale state-machine OWN_STALL->EMPTY_SLOT->PICKER->STORAGE2",
    "Khóa click ô trống/storage2 tối đa một lần cho mỗi transition",
    "Khóa native-500 và native-1000 x10/sale-dialog table riêng",
    "Khóa POST_SALE OWN_STALL trước listing tiếp theo",
    "Khóa Function sale policy, scheduler, maintenance và restart safe boundary",
)


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing AUTO Main file: {path}")
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
    action = read(ACTION)
    selling = read(SELLING)
    inventory = read(INVENTORY)
    workflow = read(WORKFLOW)
    recognition = read(RECOGNITION)
    errors = read(ERRORS)
    gui = read(CORE_GUI)
    integration = read(INTEGRATION)
    entry = read(DEV_ENTRY)
    auto_main = read(AUTO_MAIN)
    friend_refresh = read(FRIEND_REFRESH)
    auto_multi_worker = read(AUTO_MULTI_WORKER)
    catalog = read(CATALOG)

    for token in ('"tao_say"', '"vai_vang"', '"tinh_dau_hh"'):
        require(recognition, token, f"Missing allowed AUTO VP: {token}")

    require(action, "class AutoMainSellingActions", "Isolated sale action missing")
    require(action, 'ITEM_ORDER = ("tao_say", "vai_vang")',
            "Function-1 sale order missing")
    require(action, "item_order: tuple[str, ...] | None = None",
            "Function-specific sale policy input missing")
    require(action, "self.ITEM_ORDER = requested", "Function sale order not installed")
    require(action, "SELECTED_ITEM_TEMPLATES", "Selected-item proof map missing")
    require(action, "basket_button = (450, 442)", "Recovered storage2 reference missing")

    # State machine: prove parent state, find without click, click once, then wait.
    require(action, "self.selling.wait_own_stall_ready(",
            "OWN_STALL pre-click proof missing")
    require(action, "empty = self.selling.find_empty_slot(click=False)",
            "Empty slot must be recognized READ-ONLY before click")
    require(action, "EMPTY_SLOT click-once", "Empty-slot click-once runtime marker missing")
    require(action, "self.selling.vision.driver.click(*empty.center)",
            "Verified empty-slot center is not clicked")
    require(action, "self.selling.inventory.wait_storage_picker_ready(",
            "PICKER destination-state proof missing")
    require(action, "không click lần hai", "No-second-click recovery marker missing")
    forbid(action, "SALE_PICKER_OPEN_ATTEMPTS",
           "Retry-click state machine returned")
    forbid(action, "POST_SALE_STALL_SETTLE",
           "Fixed post-sale sleep must not be a readiness gate")
    forbid(action, "self.selling._find_empty_slot()",
           "AUTO Main must not use find+click combined helper")

    # Storage2 proof is target-specific on 500 and baseline-table on 1000.
    require(action, "select_storage_after_picker_ready(2)",
            "Verified storage2 selector missing")
    require(inventory, "N500_STORAGE2_ACTIVE_THRESHOLD = 0.46",
            "Native500 target-specific storage2 proof missing")
    require(inventory, "N500_STORAGE2_ACTIVE_PASSES = 2",
            "Native500 storage2 proof must be stable")
    require(inventory, "STORAGE2_ACTIVE_ZONE = (398, 395, 100, 96)",
            "Native500 storage2 row gate missing")
    require(inventory, "N500_PICKER_VISIBLE_REQUIRED_MARKERS = 2",
            "Active-style picker visibility proof missing")
    require(inventory, "generic storage icons cannot authorize it",
            "Storage2 proof semantics marker missing")
    require(inventory, "STORAGE2 click-once", "Storage2 click-once marker missing")
    require(inventory, "contract=1000-baseline",
            "Native1000 storage baseline contract missing")
    forbid(inventory, "STORAGE_SELECT_ATTEMPTS",
           "Repeated storage-tab click loop must stay removed")

    # Resolution-specific dialog and exact-x10 tables.
    require(selling, "N500_SALE_DIALOG_THRESHOLD = 0.68",
            "Native500 sale dialog calibration missing")
    require(selling, "N1000_SALE_DIALOG_THRESHOLD = 0.78",
            "Native1000 sale dialog baseline missing")
    require(selling, "N1000_SALE_DIALOG_SCALES = (1.00,)",
            "Native1000 dialog must use 1000 baseline scale")
    require(action, "N500_EXACT_TEN_THRESHOLD = 0.78",
            "Native500 exact-ten threshold missing")
    require(action, "N500_EXACT_TEN_SCALES = (0.75, 0.90, 1.00, 1.10, 1.25, 1.40, 1.55)",
            "Native500 exact-ten multiscale missing")
    require(action, "N1000_EXACT_TEN_THRESHOLD = 0.95",
            "Native1000 exact-ten baseline missing")
    require(action, "N1000_EXACT_TEN_SCALES = (1.00,)",
            "Native1000 exact-ten baseline scale missing")
    require(action, "EXACT_TEN_REQUIRED_PASSES = 2",
            "Exact-ten proof must remain stable across two passes")
    require(action, "exact_threshold, exact_scales, table_name = self._exact_ten_profile()",
            "x10 does not select table from native resolution")
    require(action, "threshold=exact_threshold", "x10 dynamic threshold missing")
    require(action, "scales=exact_scales", "x10 dynamic scales missing")
    require(action, "sale dialog READY + x10 PASS", "Pre-place proof log missing")

    require(action, "def _cancel_selected_item", "Verified cancel path missing")
    require(action, "self.selling.inventory.is_storage_picker_ready()",
            "Cancel recovery still guesses picker from storage2 icon")
    require(action, "CANCEL recovery EMPTY_SLOT click-once",
            "Cancel fallback must use one verified slot click")
    require(action, 'return "WRONG_ITEM"', "Wrong-item safe cancel missing")
    require(action, "self._unsafe_item_ids.add", "Wrong-item exclusion missing")
    require(action, "self._insufficient_item_ids.add(selected.item_id)",
            "Below-ten exclusion missing")

    # Destructive result proof is not enough: own stall must be stable again.
    require(action, "_mean_difference(before, after)", "Sale screen-change proof missing")
    require(action, "POST_SALE_OWN_STALL_TIMEOUT = 5.0",
            "Post-sale own-stall timeout missing")
    require(action, "description=\"POST_SALE OWN_STALL\"",
            "Post-sale own-stall state proof missing")
    require(action, "POST_SALE OWN_STALL READY",
            "Post-sale safe-next-listing marker missing")
    require(selling, "def wait_own_stall_ready(", "Own-stall stable proof helper missing")
    require(selling, "required_passes: int = 2", "Own-stall must be stable by default")
    require(selling, "def find_empty_slot(self, *, click: bool = False)",
            "Read-only empty-slot helper missing")

    require(action, 'for checked_count in range(1, len(self.ITEM_ORDER) + 1):',
            "Every Function item must be checked in same operation")
    require(action, 'status="NO_ALLOWED_ITEM"', "No-item safe stop missing")
    require(action, 'status="NO_SAFE_EXACT_TEN_ITEMS"', "Unsafe/all-short stop missing")
    forbid(action, "self.selling._finish_batch_from_match(",
           "AUTO exact-x10 must stay isolated from clear-stall placement policy")

    # Workflow ordering/accounting remains intact.
    require(workflow, "collect_own_stall_gold(maximum=8)", "Gold-before-sale order missing")
    require(workflow, "attempt = self.sale.sell_next_allowed", "Per-view sale missing")
    require(workflow, "self.auto.stall.next_view()", "Next-view step missing")
    require(workflow, "sold_by_item[attempt.item_id] += 1", "Per-item accounting missing")
    require(workflow, '"NO_SAFE_EXACT_TEN_ITEMS"', "Workflow safe stop missing")
    require(workflow, "finally:", "Own-stall cleanup guard missing")
    require(workflow, "self.auto.stall.close_own_stall()", "Own-stall close missing")
    if workflow.index("collected += self.auto.stall.collect_own_stall_gold") > workflow.index("attempt = self.sale.sell_next_allowed"):
        raise AssertionError("AUTO Main must collect gold before listing VP")

    # GUI/function/restart contracts remain unchanged by sale repair.
    require(gui, 'text="▶ Bắt đầu AUTO MULTI DEV"', "AUTO start button missing")
    require(integration, '_AUTO_MAIN_FUNCTION_OPTIONS = (', "Function menu source missing")
    require(integration, '("function_1", "9 Táo sấy - 9 Vải vàng")',
            "Function 1 not exposed")
    require(integration, '_CLIENT_RESTART_INTERVAL_SECONDS = 7200.0',
            "ClientJS restart interval changed")
    require(integration, '_CLIENT_RESTART_REQUEST_PREFIX = "CLIENT_RESTART_REQUESTED"',
            "Restart handoff prefix missing")
    require(integration, 'resume["skip_initial_sale_once"] = True',
            "Post-restart duplicate-sale guard missing")
    require(integration, "self._start_clean_auto_profile_only(profile_id)",
            "Safe restart does not relaunch requesting profile")
    require(integration, 'start_button.configure(command=self._start_configured_auto_main)',
            "AUTO Start is not bound to selected Function config")
    require(catalog, '"function_1": FunctionSpec(', "Function-1 catalog missing")
    require(catalog, 'sale_item_ids=("tao_say", "vai_vang")',
            "Function-1 sale ownership missing")

    require(auto_main, "get_function_spec(function_id)", "Function catalog resolution missing")
    require(auto_main, "FunctionModule(automation)", "Function dispatcher missing")
    require(auto_main, "CLIENT_RESTART_INTERVAL_SECONDS = 7200.0",
            "Scheduler restart interval changed")
    require(auto_main, "raise ClientRestartRequested(", "Restart signal missing")
    require(auto_main, "self._request_client_restart_after_sale()",
            "Restart safe-boundary call missing")
    require(errors, "class ClientRestartRequested(AutomationStopped):",
            "Restart must remain cooperative stop")
    require(auto_main, "self._sale_once(ordinal=1)", "Mandatory sale #1 missing")
    require(auto_main, "if loops_since_sale >= self.sale_every_loops:",
            "Periodic sale gate missing")

    require(friend_refresh, "class FriendRefreshWorkflow:", "FriendRefreshWorkflow missing")
    require(friend_refresh, "self.auto.navigation.go_to_friend(", "Friend navigation missing")
    require(friend_refresh, "self.auto.navigation.return_home(", "Return-home navigation missing")
    forbid(friend_refresh, "open_friend_stall", "Maintenance must not open friend stall")
    forbid(friend_refresh, "AutoVpSaleWorkflow", "Maintenance must not trigger sale")

    require(auto_multi_worker, 'marker = Path(args.work_dir).resolve() / "auto-main-config.json"',
            "Worker config loader missing")
    require(auto_multi_worker, "except AutomationStopped as exc:",
            "Worker restart/stop handoff missing")
    require(entry, 'worker_root / "auto_multi_dev_worker.py"', "Worker launch wiring missing")

    for text in (action, workflow, friend_refresh):
        forbid(text, ".pyc", "AUTO Main runtime must not load legacy pyc")
        forbid(text, "clear_stall_probe_runtime", "AUTO Main must not call Dọn quầy runtime")
        require(text, "FILE_FUNCTIONS", "AUTO Main module needs FILE_FUNCTIONS")

    if verify_auto_builder_contract() != 0:
        raise AssertionError("AUTO Builder static contract failed")

    print("AUTO MULTI DEV VP SALE STATIC CONTRACT VERIFIED")
    print("sale_state=own-stall->empty-click-once->picker->storage2->dialog->post-sale-own-stall")
    print("resolution=500-table-or-1000-table-from-native-client")
    print("storage2=native500-target-specific+native1000-baseline")
    print("x10=native500-multiscale+native1000-baseline+two-pass")
    print("next_listing=blocked-until-own-stall-stable")
    print("client_restart=2h+safe-sale-boundary+same-profile-relaunch")
    print("auto_builder=verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
