from __future__ import annotations

"""Static contract for the isolated AUTO MULTI DEV VP sale flow."""

import ast
from pathlib import Path

from verify_auto_builder_contract import main as verify_auto_builder_contract


ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "components/clientjs-auto/kvtm_automation/actions/auto_main_selling.py"
WORKFLOW = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_vp_sale/workflow.py"
INIT = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_vp_sale/__init__.py"
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
    "Đọc và parse các file AUTO Main bắt buộc",
    "Khóa đúng VP mặc định của Function 1 và sale policy theo Function catalog",
    "Khóa thứ tự thu vàng, treo VP và hai swipe",
    "Khóa xác minh giao dịch trước khi ghi nhận",
    "Khóa x10 native-500 bằng multi-scale + hai frame liên tiếp, cấm quay lại threshold 0.95",
    "Khóa GUI chọn Function + số vòng giữa hai lần bán + chờ giữa vòng Function",
    "Khóa công tắc qua nhà bạn #1 sau mỗi ba vòng Function và handoff tới worker",
    "Khóa maintenance dùng navigation Dọn-quầy đã prove nhưng không chạy business Dọn quầy",
    "Khóa restart ClientJS 2 giờ chỉ tại safe boundary sau Function đủ vòng + sale hoàn tất",
    "Khóa relaunch đúng profile và resume worker mà không sale lặp ngay sau restart",
    "Khóa vào game/đóng popup trước sale lần 1 và Function loop",
    "Khóa sale lần 2..N chỉ sau đủ số vòng cấu hình",
    "Khóa thời gian chờ chỉ giữa các vòng Function",
    "Khóa recovery restart: exact-main trước khi chạy lại scheduler",
    "Chạy thêm static contract AUTO Builder",
    "Cấm phụ thuộc pyc và gọi workflow Dọn quầy",
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
    workflow = read(WORKFLOW)
    read(INIT)
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
    require(action, "if not self.selling._find_empty_slot()", "Empty-slot gate missing")
    require(action, "basket_button = (450, 442)", "Exact basket-tab point missing")
    require(action, "for attempt in range(1, 4):", "Bounded storage render retries missing")
    require(action, 'log_prefix="AUTO SELL VP"', "Sale recognition log label missing")
    require(action, "self.recognition.scan_samples(", "Allowed-item scan missing")
    forbid(action, "self.inventory.select_storage(", "AUTO sale must not trust unverified shared storage selection")
    require(action, 'ITEM_ORDER = ("tao_say", "vai_vang")', "Function-1 two-item round-robin default order missing")
    require(action, "item_order: tuple[str, ...] | None = None", "Function-specific sale policy input missing")
    require(action, "self.ITEM_ORDER = requested", "Function-specific sale order not installed per action instance")
    require(action, "self._next_item_index", "Round-robin cursor missing")
    require(action, "SELECTED_ITEM_TEMPLATES", "Post-selection item map missing")
    require(action, "SELECTED_ITEM_ZONE", "Post-selection item verification zone missing")
    require(action, 'return "WRONG_ITEM"', "Wrong-item safe cancel missing")
    require(action, "self._unsafe_item_ids.add", "Wrong-item exclusion missing")
    require(action, '"sl10"', "Exact x10 quantity gate missing")
    require(action, "EXACT_TEN_THRESHOLD = 0.78", "Native-500 exact-ten threshold changed")
    require(action, "EXACT_TEN_SCALES = (0.75, 0.90, 1.00, 1.10, 1.25, 1.40, 1.55)", "Native-500 exact-ten scales changed")
    require(action, "EXACT_TEN_REQUIRED_PASSES = 2", "Exact-ten must require two stable frames")
    require(action, "threshold=self.EXACT_TEN_THRESHOLD", "Exact-ten match does not use calibrated threshold")
    require(action, "scales=self.EXACT_TEN_SCALES", "Exact-ten match does not use native multi-scale proof")
    require(action, "quantity_passes >= self.EXACT_TEN_REQUIRED_PASSES", "Exact-ten result must be stable on configured frames")
    require(action, "for quantity_attempt in range(1, 4):", "Bounded x10 render retries missing")
    require(action, "if quantity_passes < self.EXACT_TEN_REQUIRED_PASSES:", "Below-x10 branch missing")
    require(action, "self.selling.wait_sale_dialog_ready(", "AUTO Main does not use native-500 sale dialog proof")
    require(action, "sale dialog READY + x10 PASS", "Pre-click sale proof log missing")
    forbid(action, "threshold=0.95", "Legacy exact-ten 0.95 threshold returned")
    require(action, "def _cancel_selected_item", "Verified dialog cancel missing")
    require(action, "zone=(930, 0, 70, 70)", "Visible top-right dialog close gate missing")
    require(action, "if inventory_open is None:", "Closed-inventory recovery branch missing")
    require(action, "if not self.selling._find_empty_slot():", "Inventory picker recovery gate missing")
    require(action, '"Không hủy và khôi phục được kho bán VP; dừng trước khi thao tác tiếp"', "Unsafe cancel recovery stop missing")
    require(action, 'for checked_count in range(1, len(self.ITEM_ORDER) + 1):', "Every Function-allowed item must be checked in the same inventory operation")
    if action.count("self.selling._find_empty_slot()") != 2:
        raise AssertionError("Empty-slot calls must be limited to initial selection plus verified recovery")
    require(action, "self._insufficient_item_ids.add(selected.item_id)", "Insufficient item exclusion missing")
    require(action, "_mean_difference(before, after)", "Screen-change verification missing")
    forbid(action, "self.selling._finish_batch_from_match(", "AUTO Main exact-x10 flow must not use Dọn quầy placement wording/policy")
    require(action, 'status="NO_ALLOWED_ITEM"', "No-item safe stop missing")

    require(workflow, "collect_own_stall_gold(maximum=8)", "Gold-before-sale order missing")
    require(workflow, "attempt = self.sale.sell_next_allowed", "Per-view sale missing")
    require(workflow, "self.auto.stall.next_view()", "Two-swipe next-view step missing")
    require(workflow, "sold_by_item[attempt.item_id] += 1", "Per-item accounting missing")
    require(workflow, 'function_id: str = "function_1"', "Sale callable Function identity missing")
    require(workflow, "allowed_item_ids: tuple[str, ...] | None = None", "Sale callable Function VP policy missing")
    require(workflow, '"NO_SAFE_EXACT_TEN_ITEMS"', "Wrong-item/all-short workflow stop missing")
    require(workflow, '"AUTO bán VP • tổng kết x10 | "', "Per-item summary log missing")
    require(workflow, "finally:", "Own-stall cleanup guard missing")
    require(workflow, "self.auto.stall.close_own_stall()", "Own-stall close missing")
    if workflow.index("collected += self.auto.stall.collect_own_stall_gold") > workflow.index("attempt = self.sale.sell_next_allowed"):
        raise AssertionError("AUTO Main must collect gold before listing VP")

    require(gui, 'text="▶ Bắt đầu AUTO MULTI DEV"', "Consolidated AUTO Multi DEV start button missing")
    require(gui, 'text="⚙ Cấu hình tốc độ"', "AUTO Multi DEV speed settings button missing")
    if "▶ Bán VP AUTO" in gui:
        raise AssertionError("Passed standalone VP sale button must stay removed")
    require(integration, '_AUTO_MAIN_FUNCTION_OPTIONS = (', "AUTO Main Function menu source missing")
    require(integration, '("function_1", "9 Táo sấy - 9 Vải vàng")', "Verified Function 1 is not exposed in AUTO Main menu")
    require(integration, 'text="CHỨC NĂNG"', "AUTO Main Function menu label missing")
    require(integration, 'text="SỐ VÒNG GIỮA 2 LẦN BÁN"', "AUTO Main sale interval input missing")
    require(integration, 'text="CHỜ GIỮA VÒNG FUNCTION (GIÂY)"', "Visible Function loop delay input missing")
    require(integration, "self.auto_multi_dev_function_loop_delay", "Function loop delay variable missing")
    require(integration, 'text="LÀM MỚI ITEM TREO"', "Friend-refresh GUI label missing")
    require(integration, '"Qua bạn #1 / 3 vòng"', "Friend-refresh toggle button missing")
    require(integration, '_FRIEND_REFRESH_SETTING_KEY = "auto_multi_dev_friend_refresh_enabled"',
            "Friend-refresh persistent GUI key missing")
    require(integration, "self.auto_multi_dev_friend_refresh_enabled", "Friend-refresh BooleanVar missing")
    require(integration, "self._save_auto_multi_dev_friend_refresh", "Friend-refresh toggle save hook missing")
    require(integration, '"friend_refresh_enabled": friend_refresh_enabled',
            "GUI does not persist friend-refresh into per-run marker")
    require(integration, '_CLIENT_RESTART_INTERVAL_SECONDS = 7200.0',
            "ClientJS production restart interval must remain 2 hours")
    require(integration, '_CLIENT_RESTART_REQUEST_PREFIX = "CLIENT_RESTART_REQUESTED"',
            "ClientJS restart handoff prefix missing")
    require(integration, '"client_restart_interval_seconds": _CLIENT_RESTART_INTERVAL_SECONDS',
            "GUI run marker does not carry ClientJS restart interval")
    require(integration, '"skip_initial_sale_once": False',
            "Initial AUTO run must keep sale #1")
    require(integration, 'resume["skip_initial_sale_once"] = True',
            "Post-restart AUTO must suppress duplicate immediate sale")
    require(integration, "self._auto_main_active_config", "Active AUTO config is not retained across ClientJS restart")
    require(integration, "self._auto_main_restart_pending", "Pending ClientJS restart ownership state missing")
    require(integration, 'outcome == "stopped" and reason.startswith(_CLIENT_RESTART_REQUEST_PREFIX)',
            "Multi does not intercept cooperative restart handoff")
    require(integration, "proc.terminate()", "Multi does not terminate old ClientJS at safe restart")
    require(integration, "old_thread.is_alive()", "Relaunch does not wait for old AUTO supervisor to exit")
    require(integration, "self._start_clean_auto_profile_only(profile_id)",
            "ClientJS restart does not relaunch only the requesting profile")
    require(integration, "original_stop_clean_session(self)",
            "Operator Stop no longer reaches proven worker stop lifecycle")
    require(integration, 'start_button.configure(command=self._start_configured_auto_main)', "AUTO Main Start button is not bound to selected Function config")
    require(integration, 'work_dir / "auto-main-config.json"', "Per-run AUTO Main config marker missing")
    require(integration, '"function_id": function_id', "GUI does not persist selected Function id")
    require(integration, '"sale_every_loops": sale_every', "GUI does not persist sale interval")
    require(integration, '"function_loop_delay_seconds": loop_delay', "GUI does not persist Function loop delay")
    require(integration, 'designer_button = tab_buttons.get("clear_stall_designer")', "Legacy Designer tab is not hidden by its real key")

    require(catalog, '"function_1": FunctionSpec(', "Function-1 catalog entry missing")
    require(catalog, 'sale_item_ids=("tao_say", "vai_vang")', "Function-1 sale ownership missing")
    require(auto_main, "get_function_spec(function_id)", "AUTO Main does not resolve selected Function through catalog")
    require(auto_main, "FunctionModule(automation)", "AUTO Main Function dispatcher missing")
    require(auto_main, "sale_every_loops: int = 1", "AUTO Main sale interval input missing")
    require(auto_main, "function_loop_delay_seconds: float = 0.0", "AUTO Main Function loop delay input missing")
    require(auto_main, "friend_refresh_enabled: bool = False", "AUTO Main friend-refresh input missing")
    require(auto_main, "FRIEND_REFRESH_EVERY_LOOPS = 3", "Friend-refresh interval must remain exactly three loops")
    require(auto_main, "self.friend_refresh = FriendRefreshWorkflow(", "Common friend-refresh workflow not wired")
    require(auto_main, "CLIENT_RESTART_INTERVAL_SECONDS = 7200.0",
            "Scheduler ClientJS restart interval must remain 2 hours")
    require(auto_main, "CLIENT_RESTART_REQUEST_PREFIX = \"CLIENT_RESTART_REQUESTED\"",
            "Scheduler restart request prefix missing")
    require(auto_main, "self._load_runtime_maintenance_config()",
            "Scheduler does not read per-run restart/resume marker")
    require(auto_main, "self.skip_initial_sale_once", "Post-restart duplicate-sale guard missing")
    require(auto_main, "raise ClientRestartRequested(", "Scheduler does not emit cooperative ClientJS restart signal")
    require(auto_main, "self._announce_client_restart_deferred(",
            "Restart deadline is not deferred while Function cycle is incomplete")
    require(auto_main, "self._request_client_restart_after_sale()",
            "Safe restart request after sale missing")
    require(errors, "class ClientRestartRequested(AutomationStopped):",
            "Client restart must remain a cooperative stop signal")
    require(auto_main, "self._sale_once(ordinal=1)", "Mandatory sale #1 missing")
    require(auto_main, "while True:", "AUTO Main is not continuous until Stop")
    require(auto_main, "loops_since_sale += 1", "Function loop accounting missing")
    require(auto_main, "if loops_since_sale >= self.sale_every_loops:", "Sale #2..N is not gated by configured Function loop count")
    sale_boundary = auto_main.index("if loops_since_sale >= self.sale_every_loops:")
    sale_call = auto_main.index("self._sale_once(ordinal=self.sale_calls + 1)", sale_boundary)
    restart_call = auto_main.index("self._request_client_restart_after_sale()", sale_boundary)
    if restart_call <= sale_call:
        raise AssertionError("ClientJS restart must happen only after the periodic sale returns")
    require(auto_main, "self.function_loops % self.FRIEND_REFRESH_EVERY_LOOPS != 0",
            "Friend refresh is not gated by 3 completed Function loops")
    require(auto_main, "self._friend_refresh_if_due()", "Friend refresh scheduler call missing")
    require(auto_main, "self._wait_before_next_function_loop()", "Between-Function loop wait call missing")
    require(auto_main, "self.auto.wait.sleep(delay)", "Function loop delay must be stop-aware")
    require(auto_main, "allowed_item_ids=self.spec.sale_item_ids", "AUTO Main sale is not bound to selected Function VP policy")
    require(auto_main, "self.context.ensure_running()", "AUTO Main stop checkpoints missing")
    require(auto_main, 'self.spec.runner_key == "function_1"', "Function-1 completion contract missing")

    # Maintenance must reuse the already-proven Dọn-quầy navigation primitives,
    # but it must never open a friend stall or buy/sell anything.
    require(friend_refresh, "class FriendRefreshWorkflow:", "FriendRefreshWorkflow missing")
    require(friend_refresh, "FRIEND_ORDINAL = 1", "Maintenance must use first visible friend")
    require(friend_refresh, "self.auto.navigation.go_to_friend(", "Friend navigation primitive not reused")
    require(friend_refresh, "self.auto.navigation.return_home(", "Return-home primitive not reused")
    require(friend_refresh, "self.context.invalidate_camera_main(", "Leaving home must invalidate exact-main proof")
    require(friend_refresh, "self.context.mark_camera_exact_main(", "Return-home route does not re-prove exact-main")
    require(friend_refresh, "self.recovery.recover_unknown_to_main(", "Maintenance recovery does not use central RecoveryManager")
    forbid(friend_refresh, "open_friend_stall", "Maintenance must not open friend stall")
    forbid(friend_refresh, "buy_from_listing", "Maintenance must not purchase VP")
    forbid(friend_refresh, "AutoVpSaleWorkflow", "Maintenance must not trigger sale")
    forbid(friend_refresh, "clear_stall", "Maintenance must not call Dọn-quầy workflow")

    require(auto_multi_worker, 'marker = Path(args.work_dir).resolve() / "auto-main-config.json"', "Worker AUTO Main per-run config loader missing")
    require(auto_multi_worker, 'function_id = str(auto_main_config["function_id"])', "Worker does not load selected Function")
    require(auto_multi_worker, 'sale_every = int(auto_main_config["sale_every_loops"])', "Worker does not load sale interval")
    require(auto_multi_worker, 'loop_delay = float(auto_main_config["function_loop_delay_seconds"])', "Worker does not load Function loop delay")
    require(auto_multi_worker, 'friend_refresh_enabled = bool(auto_main_config["friend_refresh_enabled"])',
            "Worker does not load friend-refresh toggle")
    require(auto_multi_worker, '"friend_refresh_enabled": False', "Worker default friend-refresh must be off")
    require(auto_multi_worker, "except AutomationStopped as exc:",
            "Worker does not preserve cooperative stop/restart handoff")
    require(auto_multi_worker, "reason=str(exc)",
            "Worker does not return cooperative restart reason to Multi")

    # The recovery worker now owns two GameSession calls (floor-demo + resilient
    # AUTO Main). Inspect only the continuous AUTO Main segment so the contract
    # verifies the actual restart loop rather than matching the earlier demo call.
    require(auto_multi_worker, 'last_error_signature = ""', "AUTO Main recovery loop marker missing")
    auto_main_runtime = auto_multi_worker.split('last_error_signature = ""', 1)[1]
    game_session_call = "GameSessionWorkflow(automation).run(timeout=args.timeout)"
    scheduler_call = "result = AutoMainWorkflow("
    require(auto_main_runtime, game_session_call, "Mandatory enter-game/close-popup prefix missing from resilient AUTO Main loop")
    require(auto_main_runtime, scheduler_call, "Worker AUTO Main scheduler call missing")
    require(auto_main_runtime, "function_id=function_id", "Worker does not pass selected Function to AUTO Main")
    require(auto_main_runtime, "sale_every_loops=sale_every", "Worker does not pass sale interval to AUTO Main")
    require(auto_main_runtime, "function_loop_delay_seconds=loop_delay", "Worker does not pass Function loop delay")
    require(auto_main_runtime, "friend_refresh_enabled=friend_refresh_enabled", "Worker does not pass friend-refresh to AUTO Main")
    if auto_main_runtime.index(game_session_call) > auto_main_runtime.index(scheduler_call):
        raise AssertionError("AUTO Main Function must enter game/close popup before scheduler starts")
    require(auto_multi_worker, "runtime_error_policy=recover-main-restart", "AUTO Main runtime recovery policy marker missing")
    require(auto_multi_worker, "_recover_auto_main_to_main_screen", "AUTO Main exact-main recovery helper missing")
    require(auto_multi_worker, "same_error_count", "AUTO Main repeated-error circuit breaker missing")
    require(auto_multi_worker, 'outcome="auto_main_ready"', "Worker AUTO Main result marker missing")
    require(entry, 'worker_root / "auto_multi_dev_worker.py"', "GUI isolated-worker launch wiring missing")
    require(entry, 'outcome = str(event.pop("outcome", "auto_main_ready"))', "GUI AUTO Main result handling missing")

    for text in (action, workflow, friend_refresh):
        forbid(text, ".pyc", "AUTO Main runtime must not load legacy pyc")
        forbid(text, "clear_stall_probe_runtime", "AUTO Main must not call Dọn quầy runtime")
        require(text, "FILE_FUNCTIONS", "Every new AUTO Main module needs FILE_FUNCTIONS")

    if verify_auto_builder_contract() != 0:
        raise AssertionError("AUTO Builder static contract failed")

    print("AUTO MULTI DEV VP SALE STATIC CONTRACT VERIFIED")
    print("runtime=isolated_worker_v3")
    print("flow=game-session+sale1+selected-function-loop+sale-every-n-loops")
    print("sale_dialog=native500-dual-proof")
    print("sale_x10=multi-scale-two-frame-proof")
    print("friend_refresh=gui-toggle+every3-function-loops+friend1-return-home")
    print("friend_refresh_navigation=reuse-clean-navigation-assets-no-friend-stall")
    print("client_restart=2h+defer-until-function-sale-boundary+same-profile-relaunch")
    print("client_restart_resume=skip-duplicate-initial-sale+new-worker+new-bridge-generation")
    print("function_loop_delay=visible+between-loops-only+stop-aware")
    print("function_select=verified-complete-functions-only")
    print("allowed_items=function-bound-catalog")
    print("runtime_error_policy=recover-main-restart")
    print("auto_builder=verified")
    print("clear_stall_runtime=untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())