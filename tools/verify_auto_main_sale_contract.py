from __future__ import annotations

"""Static contract for the standardized AUTO MULTI DEV VP sale flow."""

import ast
from pathlib import Path

from verify_auto_builder_contract import main as verify_auto_builder_contract


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "components/clientjs-auto/kvtm_automation"
BASE_ACTION = CLEAN / "actions/auto_main_selling.py"
SALE_FACADE = CLEAN / "actions/vp_sale_transaction.py"
SELLING = CLEAN / "actions/selling.py"
INVENTORY = CLEAN / "actions/inventory.py"
WORKFLOW = CLEAN / "workflows/auto_vp_sale/workflow.py"
RECOGNITION = CLEAN / "actions/item_recognition.py"
ERRORS = CLEAN / "errors.py"
AUTO_MAIN = CLEAN / "workflows/auto_main/workflow.py"
FRIEND_REFRESH = CLEAN / "workflows/auto_main/friend_refresh.py"
AUTO_MULTI_WORKER = ROOT / "components/clientjs-auto/worker/auto_multi_dev_worker.py"
CATALOG = CLEAN / "workflows/auto_builder/catalog.py"
CORE_GUI = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi.py"
INTEGRATION = ROOT / "source-archive/multi-current/kvtm_multi_tool/auto_builder_integration.py"
DEV_ENTRY = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_entry.py"
PROFILE_SETTINGS = ROOT / "source-archive/multi-current/kvtm_multi_tool/auto_main_profile_settings.py"
UI_REFINEMENT = ROOT / "source-archive/multi-current/kvtm_multi_tool/auto_multi_dev_ui_refinement.py"


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing AUTO Main sale file: {path}")
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
    action = read(BASE_ACTION)
    facade = read(SALE_FACADE)
    selling = read(SELLING)
    inventory = read(INVENTORY)
    workflow = read(WORKFLOW)
    recognition = read(RECOGNITION)
    errors = read(ERRORS)
    auto_main = read(AUTO_MAIN)
    friend_refresh = read(FRIEND_REFRESH)
    worker = read(AUTO_MULTI_WORKER)
    catalog = read(CATALOG)
    gui = read(CORE_GUI)
    integration = read(INTEGRATION)
    entry = read(DEV_ENTRY)
    profile_settings = read(PROFILE_SETTINGS)
    refinement = read(UI_REFINEMENT)

    # Neutral transaction facade owns one listing; view/scheduler semantics stay
    # outside it. Historical AutoMainSellingActions remains implementation/base.
    require(facade, "class VpSaleTransactionActions(AutoMainSellingActions):", "Neutral VP sale transaction facade missing")
    require(workflow, "VpSaleTransactionActions(", "Sale workflow does not use neutral transaction facade")
    require(action, 'ITEM_ORDER = ("tao_say", "vai_vang")', "Function-1 default sale order missing")
    require(action, "item_order: tuple[str, ...] | None = None", "Function-specific sale policy input missing")
    require(action, "self.ITEM_ORDER = requested", "Function sale order not installed")
    require(action, "SELECTED_ITEM_TEMPLATES", "Selected-item proof map missing")
    require(action, '"tra_da": ("kho_tra_da",)', "Trà đá dialog fallback proof missing")
    require(action, "SELECTED_ITEM_THRESHOLD = 0.78", "Selected-item safety threshold changed")
    require(action, "SELECTED_ITEM_REQUIRED_PASSES = 2", "Selected-item stable proof missing")
    require(action, "SELECTED_ITEM_SCAN_ATTEMPTS = 3", "Selected-item bounded retry missing")
    require(action, "selected-item STABLE READY", "Selected-item stable PASS marker missing")

    # Parent-state -> click-once -> destination-state transaction.
    require(action, "self.selling.wait_own_stall_ready(", "OWN_STALL pre-click proof missing")
    require(action, "empty = self.selling.find_empty_slot(click=False)", "Empty slot must be recognized read-only")
    require(action, "EMPTY_SLOT click-once", "Empty-slot click-once marker missing")
    require(action, "self.selling.vision.driver.click(*empty.center)", "Verified empty slot is not clicked")
    require(action, "self.selling.inventory.wait_storage_picker_ready(", "Picker destination proof missing")
    require(action, "select_storage_after_picker_ready(2)", "Storage2 selector missing")
    require(action, "không click lần hai", "No-second-click policy marker missing")
    forbid(action, "SALE_PICKER_OPEN_ATTEMPTS", "Retry-click state machine returned")

    # Native-resolution sale proof remains table-driven.
    require(inventory, "N500_STORAGE2_ACTIVE_THRESHOLD = 0.46", "Native500 storage2 proof changed")
    require(inventory, "N500_STORAGE2_ACTIVE_PASSES = 2", "Native500 storage2 stable proof changed")
    require(inventory, "contract=1000-baseline", "Native1000 storage baseline missing")
    require(selling, "N500_SALE_DIALOG_THRESHOLD = 0.68", "Native500 sale dialog calibration missing")
    require(selling, "N1000_SALE_DIALOG_THRESHOLD = 0.78", "Native1000 sale dialog baseline missing")
    require(action, "N500_EXACT_TEN_THRESHOLD = 0.78", "Native500 exact-ten threshold missing")
    require(action, "N1000_EXACT_TEN_THRESHOLD = 0.95", "Native1000 exact-ten threshold missing")
    require(action, "EXACT_TEN_REQUIRED_PASSES = 2", "Exact-ten stable proof missing")
    require(action, "sale dialog READY + x10 PASS", "Pre-place proof log missing")
    require(action, "POST_SALE_OWN_STALL_TIMEOUT = 5.0", "Post-sale own-stall timeout missing")
    require(action, "POST_SALE OWN_STALL READY", "Post-sale own-stall proof missing")
    require(selling, "def wait_own_stall_ready(", "Own-stall stable proof helper missing")

    # Allowed Function items and safe insufficient-item exclusions remain intact.
    for token in (
        '"tao_say"', '"vai_vang"', '"tinh_dau_hh"',
        '"nuoc_hoa_hong"', '"tra_da"',
    ):
        require(recognition, token, f"Missing allowed AUTO VP: {token}")
    require(action, 'status="NO_ALLOWED_ITEM"', "No-item safe stop missing")
    require(action, 'status="NO_SAFE_EXACT_TEN_ITEMS"', "Unsafe/all-short safe stop missing")
    require(action, "self._insufficient_item_ids.add(selected.item_id)", "Below-ten exclusion missing")

    # Approved Module flow: exact-main handoff, five views, each view gold -> QC
    # -> listing work, then two-swipe transition. Sale returns caller, not Scheduler.
    require(workflow, "VIEW_COUNT = 5", "Sale no longer scans five views")
    require(workflow, "def _require_sale_entry_main", "Sale exact-main entry gate missing")
    require(workflow, "Sale không tự goDown(1) để sửa camera", "Sale hidden-navigation prohibition missing")
    forbid(workflow, "go_down_one_toward_main(", "Sale regressed to hidden camera normalization")
    require(workflow, "collect_own_stall_gold(maximum=8)", "Gold collection missing")
    require(workflow, "self._check_advertisement_checkpoint(view)", "QC checkpoint missing")
    require(workflow, "attempt = self.sale.sell_next_allowed", "Per-view listing transaction missing")
    require(workflow, "self.auto.stall.next_view()", "Two-swipe view transition missing")
    require(workflow, "FINAL BOUNDARY CHECK", "View-5 final boundary marker missing")
    require(workflow, '"auto-vp-sale-inventory-depleted-return-caller"', "Depleted inventory caller-return marker missing")
    require(workflow, "finally:", "Own-stall cleanup guard missing")
    require(workflow, "self.auto.stall.close_own_stall()", "Own-stall close missing")
    gold = workflow.index("collected += self.auto.stall.collect_own_stall_gold")
    qc = workflow.index("self._check_advertisement_checkpoint(view)")
    listing = workflow.index("attempt = self.sale.sell_next_allowed")
    if not gold < qc < listing:
        raise AssertionError("Sale view order must be gold -> QC -> list VP")

    # AUTO Main scheduler is Function-bound. ClientJS restart is blocked;
    # registered errors retain typed checkpoint recovery and only unknown errors
    # enter the bounded ESC/stay/exact-main/friend refresh fallback.
    require(catalog, 'sale_item_ids=("tao_say", "vai_vang")', "Function-1 sale ownership missing")
    require(catalog, 'sale_item_ids=("tao_say", "vai_vang", "tinh_dau_hh")', "Function-2 sale ownership missing")
    require(catalog, 'sale_item_ids=("nuoc_hoa_hong", "tra_da", "vai_vang")',
            "Function-3 sale ownership missing")
    require(action, '"nuoc_hoa_hong": "nuoc_hoa_hong"',
            "Function-3 Nước hoa hồng dialog proof missing")
    require(action, '"tra_da": "tra_da"',
            "Function-3 Trà đá primary dialog proof missing")
    require(action, 'self.SELECTED_ITEM_FALLBACK_TEMPLATES.get(item.item_id, ())',
            "Function-3 Trà đá fallback is not wired into dialog proof")
    require(auto_main, "CLIENT_RESTART_INTERVAL_SECONDS = 0.0", "Scheduler restart is not blocked")
    require(auto_main, "GLOBAL_RECOVERY_LIMIT = 3", "Unknown-error fallback bound missing")
    require(auto_main, "escape_three_then_stay(", "ESC x3 / Ở lại fallback missing")
    require(auto_main, "self.friend_refresh.run(", "Unknown-error friend refresh missing")
    forbid(auto_main, "ClientRestartRequested", "Scheduler restart request returned")
    require(integration, "_CLIENT_RESTART_INTERVAL_SECONDS = 0.0", "Integration restart is not blocked")
    require(integration, "scheduled_restart = False", "Supervisor restart branch is not blocked")
    forbid(worker, "ClientRestartRequested", "Worker restart lifecycle branch returned")
    require(worker, "client_restart=BLOCK", "Worker blocked-restart marker missing")

    # Periodic Friend refresh remains independent from sale/restart business work.
    require(friend_refresh, "class FriendRefreshWorkflow:", "FriendRefreshWorkflow missing")
    require(friend_refresh, "self.auto.navigation.go_to_friend(", "Friend navigation missing")
    require(friend_refresh, "self.auto.navigation.return_home(", "Return-home navigation missing")
    forbid(friend_refresh, "AutoVpSaleWorkflow", "Friend maintenance must not trigger sale")

    # GUI/worker entry stays isolated V3 and selected-Function driven.
    require(gui, 'text="▶ Bắt đầu AUTO MULTI DEV"', "AUTO start button missing")
    require(integration, '_AUTO_MAIN_FUNCTION_OPTIONS = (', "Function menu source missing")
    require(integration, 'start_button.configure(command=self._start_configured_auto_main)', "AUTO Start is not bound to configured Function")
    for ordinal in ("01.", "02.", "03."):
        require(integration, ordinal, f"Function menu is missing visible ID {ordinal}")
    require(profile_settings, '"function_id": "function_1"', "Per-profile Function default missing")
    require(profile_settings, 'active.get("function_id", "")', "Running account Function is not authoritative")
    require(profile_settings, 'self._select_auto_multi_dev_function(function_id)', "Account selection does not refresh Function menu")
    require(profile_settings, 'saved["function_id"] = function_id', "Multi-account start does not persist each account Function")
    require(refinement, 'button.configure(text="Auto")', "AUTO MULTI DEV tab was not renamed Auto")
    for hidden_key in (
        '"auto_builder"', '"delete_items"', '"upgrade_storage"',
        '"deliver_sheep"', '"produce_gems"', '"clear_stall"',
    ):
        require(refinement, hidden_key, f"Legacy tab is not hidden: {hidden_key}")
    require(refinement, 'function_button.configure(width=24, anchor="w")', "Function menu was not reduced to half width")
    require(refinement, 'stop_button.pack_forget()', "Separate Stop button remains visible")
    require(refinement, 'text="■ Dừng" if running else "▶ Bắt đầu"', "Start/Stop toggle label missing")
    require(refinement, 'command=self._toggle_auto_multi_dev_selected', "Start/Stop toggle command missing")
    require(refinement, 'state="disabled" if running or not selected else "normal"', "Running account Function menu is not locked")
    require(refinement, 'app_class._poll_clear_stall_schedule = _detached_clear_stall_poll', "Integrated clear-stall scheduler is still active")
    require(refinement, 'app_class._poll_clear_stall_workers = _detached_clear_stall_poll', "Integrated clear-stall worker polling is still active")
    require(entry, 'worker_root / "auto_multi_dev_worker.py"', "Worker launch wiring missing")
    require(entry, 'text="▶ Test Function 3 - Step 1"',
            "Function 3 Step 1 test button missing")
    require(entry, "command=self._start_clean_function_3_step_1",
            "Function 3 Step 1 button wiring missing")
    require(entry, '"function-3-step-1" if run_function_3_step_1 else "main"',
            "Function 3 Step 1 worker mode dispatch missing")
    forbid(entry, "Demo Auto Pro tới tầng 6", "Removed floor demo button returned")

    for text in (action, workflow, friend_refresh):
        forbid(text, ".pyc", "AUTO Main runtime must not load legacy pyc")
        forbid(text, "clear_stall_probe_runtime", "AUTO Main must not call Dọn quầy runtime")

    if verify_auto_builder_contract() != 0:
        raise AssertionError("AUTO Builder static contract failed")

    print("AUTO MULTI DEV VP SALE STATIC CONTRACT VERIFIED")
    print("transaction=empty-click-once->storage2->exact-x10->post-sale-own-stall")
    print("views=5;order=gold->QC->listing;return=caller")
    print("resolution=native500-or-native1000-static-tables")
    print("client_restart=blocked-3h-and-error")
    print("auto_builder=verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
