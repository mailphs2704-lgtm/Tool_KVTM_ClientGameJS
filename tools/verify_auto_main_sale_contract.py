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
CORE_GUI = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi.py"
INTEGRATION = ROOT / "source-archive/multi-current/kvtm_multi_tool/auto_builder_integration.py"
DEV_ENTRY = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_entry.py"
AUTO_MAIN = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_main/workflow.py"
AUTO_MULTI_WORKER = ROOT / "components/clientjs-auto/worker/auto_multi_dev_worker.py"
CATALOG = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_builder/catalog.py"

FILE_FUNCTIONS = (
    "Đọc và parse các file AUTO Main bắt buộc",
    "Khóa đúng VP mặc định của Function 1 và sale policy theo Function catalog",
    "Khóa thứ tự thu vàng, treo VP và hai swipe",
    "Khóa xác minh giao dịch trước khi ghi nhận",
    "Khóa GUI chọn Function + số vòng giữa hai lần bán + chờ giữa vòng Function",
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
    gui = read(CORE_GUI)
    integration = read(INTEGRATION)
    entry = read(DEV_ENTRY)
    auto_main = read(AUTO_MAIN)
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
    require(action, "threshold=0.95", "Exact-ten threshold must reject 1..9")
    require(action, "quantity_passes >= 2", "Exact-ten result must be stable on two frames")
    require(action, "for quantity_attempt in range(1, 4):", "Bounded x10 render retries missing")
    require(action, "if quantity_passes < 2:", "Below-x10 branch missing")
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
    require(auto_main, "self._sale_once(ordinal=1)", "Mandatory sale #1 missing")
    require(auto_main, "while True:", "AUTO Main is not continuous until Stop")
    require(auto_main, "loops_since_sale += 1", "Function loop accounting missing")
    require(auto_main, "if loops_since_sale >= self.sale_every_loops:", "Sale #2..N is not gated by configured Function loop count")
    require(auto_main, "self._wait_before_next_function_loop()", "Between-Function loop wait call missing")
    require(auto_main, "self.auto.wait.sleep(delay)", "Function loop delay must be stop-aware")
    require(auto_main, "allowed_item_ids=self.spec.sale_item_ids", "AUTO Main sale is not bound to selected Function VP policy")
    require(auto_main, "self.context.ensure_running()", "AUTO Main stop checkpoints missing")
    require(auto_main, 'self.spec.runner_key == "function_1"', "Function-1 completion contract missing")

    require(auto_multi_worker, 'marker = Path(args.work_dir).resolve() / "auto-main-config.json"', "Worker AUTO Main per-run config loader missing")
    require(auto_multi_worker, 'function_id = str(auto_main_config["function_id"])', "Worker does not load selected Function")
    require(auto_multi_worker, 'sale_every = int(auto_main_config["sale_every_loops"])', "Worker does not load sale interval")
    require(auto_multi_worker, 'loop_delay = float(auto_main_config["function_loop_delay_seconds"])', "Worker does not load Function loop delay")

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
    if auto_main_runtime.index(game_session_call) > auto_main_runtime.index(scheduler_call):
        raise AssertionError("AUTO Main Function must enter game/close popup before scheduler starts")
    require(auto_multi_worker, "runtime_error_policy=recover-main-restart", "AUTO Main runtime recovery policy marker missing")
    require(auto_multi_worker, "_recover_auto_main_to_main_screen", "AUTO Main exact-main recovery helper missing")
    require(auto_multi_worker, "same_error_count", "AUTO Main repeated-error circuit breaker missing")
    require(auto_multi_worker, 'outcome="auto_main_ready"', "Worker AUTO Main result marker missing")
    require(entry, 'worker_root / "auto_multi_dev_worker.py"', "GUI isolated-worker launch wiring missing")
    require(entry, 'outcome = str(event.pop("outcome", "auto_main_ready"))', "GUI AUTO Main result handling missing")

    for text in (action, workflow):
        forbid(text, ".pyc", "AUTO Main sale must not load legacy pyc")
        forbid(text, "clear_stall_probe_runtime", "AUTO Main sale must not call Dọn quầy runtime")
        require(text, "FILE_FUNCTIONS", "Every new AUTO Main module needs FILE_FUNCTIONS")

    if verify_auto_builder_contract() != 0:
        raise AssertionError("AUTO Builder static contract failed")

    print("AUTO MULTI DEV VP SALE STATIC CONTRACT VERIFIED")
    print("runtime=isolated_worker_v3")
    print("flow=game-session+sale1+selected-function-loop+sale-every-n-loops")
    print("function_loop_delay=visible+between-loops-only+stop-aware")
    print("function_select=verified-complete-functions-only")
    print("allowed_items=function-bound-catalog")
    print("runtime_error_policy=recover-main-restart")
    print("auto_builder=verified")
    print("clear_stall_runtime=untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
