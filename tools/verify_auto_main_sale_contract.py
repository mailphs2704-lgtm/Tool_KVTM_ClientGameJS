from __future__ import annotations

"""Static contract for the isolated AUTO MULTI DEV VP sale flow."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "components/clientjs-auto/kvtm_automation/actions/auto_main_selling.py"
WORKFLOW = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_vp_sale/workflow.py"
INIT = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_vp_sale/__init__.py"
RECOGNITION = ROOT / "components/clientjs-auto/kvtm_automation/actions/item_recognition.py"
CORE_GUI = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi.py"
DEV_ENTRY = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_entry.py"
AUTO_MAIN = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_main/workflow.py"
AUTO_MULTI_WORKER = ROOT / "components/clientjs-auto/worker/auto_multi_dev_worker.py"

FILE_FUNCTIONS = (
    "Đọc và parse các file AUTO Main bắt buộc",
    "Khóa đúng hai VP của chức năng 1",
    "Khóa thứ tự thu vàng, treo VP và hai swipe",
    "Khóa xác minh giao dịch trước khi ghi nhận",
    "Khóa wiring isolated worker và nút bán riêng",
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
    entry = read(DEV_ENTRY)
    auto_main = read(AUTO_MAIN)
    auto_multi_worker = read(AUTO_MULTI_WORKER)

    for token in ('"tao_say"', '"vai_vang"', '"tinh_dau_hh"'):
        require(recognition, token, f"Missing allowed AUTO VP: {token}")

    require(action, "class AutoMainSellingActions", "Isolated sale action missing")
    require(action, "if not self.selling._find_empty_slot()", "Empty-slot gate missing")
    require(action, "basket_button = (450, 442)", "Exact basket-tab point missing")
    require(action, "for attempt in range(1, 4):", "Bounded storage render retries missing")
    require(action, 'log_prefix="AUTO SELL VP"', "Sale recognition log label missing")
    require(action, "self.recognition.scan_samples(", "Allowed-item scan missing")
    forbid(action, "self.inventory.select_storage(", "AUTO sale must not trust unverified shared storage selection")
    require(
        action,
        'ITEM_ORDER = ("tao_say", "vai_vang")',
        "Function-1 two-item round-robin order missing",
    )
    require(action, "self._next_item_index", "Round-robin cursor missing")
    require(action, "SELECTED_ITEM_TEMPLATES", "Post-selection item map missing")
    require(action, "SELECTED_ITEM_ZONE", "Post-selection item verification zone missing")
    require(action, 'return "WRONG_ITEM"', "Wrong-item safe cancel missing")
    require(action, "self._unsafe_item_ids.add", "Wrong-item exclusion missing")
    require(action, '"sl10"', "Exact x10 quantity gate missing")
    require(action, "threshold=0.95", "Exact-ten threshold must reject 1..9")
    require(action, "quantity_passes >= 2", "Exact-ten result must be stable on two frames")
    require(
        action,
        "for quantity_attempt in range(1, 4):",
        "Bounded x10 render retries missing",
    )
    require(action, "if quantity_passes < 2:", "Below-x10 branch missing")
    require(action, "def _cancel_selected_item", "Verified dialog cancel missing")
    require(
        action,
        "zone=(930, 0, 70, 70)",
        "Visible top-right dialog close gate missing",
    )
    require(
        action,
        "if inventory_open is None:",
        "Closed-inventory recovery branch missing",
    )
    require(
        action,
        "if not self.selling._find_empty_slot():",
        "Inventory picker recovery gate missing",
    )
    require(
        action,
        '"Không hủy và khôi phục được kho bán VP; dừng trước khi thao tác tiếp"',
        "Unsafe cancel recovery stop missing",
    )
    require(
        action,
        'for checked_count in range(1, len(self.ITEM_ORDER) + 1):',
        "Both Function-1 items must be checked in the same inventory operation",
    )
    if action.count("self.selling._find_empty_slot()") != 2:
        raise AssertionError(
            "Empty-slot calls must be limited to initial selection plus verified recovery"
        )
    require(
        action,
        "self._insufficient_item_ids.add(selected.item_id)",
        "Insufficient item exclusion missing",
    )
    require(action, "_mean_difference(before, after)", "Screen-change verification missing")
    forbid(
        action,
        "self.selling._finish_batch_from_match(",
        "AUTO Main exact-x10 flow must not use Dọn quầy placement wording/policy",
    )
    require(action, 'status="NO_ALLOWED_ITEM"', "No-item safe stop missing")

    require(workflow, "collect_own_stall_gold(maximum=8)", "Gold-before-sale order missing")
    require(workflow, "attempt = self.sale.sell_next_allowed", "Per-view sale missing")
    require(workflow, "self.auto.stall.next_view()", "Two-swipe next-view step missing")
    require(workflow, "sold_by_item[attempt.item_id] += 1", "Per-item accounting missing")
    require(
        workflow,
        '"NO_SAFE_EXACT_TEN_ITEMS"',
        "Wrong-item/all-short workflow stop missing",
    )
    require(workflow, '"AUTO bán VP • tổng kết x10 | "', "Per-item summary log missing")
    require(workflow, "finally:", "Own-stall cleanup guard missing")
    require(workflow, "self.auto.stall.close_own_stall()", "Own-stall close missing")
    if workflow.index("collected += self.auto.stall.collect_own_stall_gold") > workflow.index("attempt = self.sale.sell_next_allowed"):
        raise AssertionError("AUTO Main must collect gold before listing VP")

    require(gui, 'text="▶ Bắt đầu AUTO MULTI DEV"', "Consolidated AUTO Multi DEV start button missing")
    require(gui, 'text="⚙ Cấu hình tốc độ"', "AUTO Multi DEV speed settings button missing")
    if "▶ Bán VP AUTO" in gui:
        raise AssertionError("Passed standalone VP sale button must stay removed")
    require(auto_main, "AutoVpSaleWorkflow(self.auto).run",
            "Consolidated start must execute the stable sale workflow")
    require(auto_multi_worker, "AutoMainWorkflow(automation).run",
            "Consolidated isolated-worker workflow wiring missing")
    require(auto_multi_worker, 'outcome="auto_main_ready"',
            "Worker AUTO Main result marker missing")
    require(entry, 'worker_root / "auto_multi_dev_worker.py"',
            "GUI isolated-worker launch wiring missing")
    require(entry, 'outcome = str(event.pop("outcome", "auto_main_ready"))',
            "GUI AUTO Main result handling missing")

    for text in (action, workflow):
        forbid(text, ".pyc", "AUTO Main sale must not load legacy pyc")
        forbid(text, "clear_stall_probe_runtime", "AUTO Main sale must not call Dọn quầy runtime")
        require(text, "FILE_FUNCTIONS", "Every new AUTO Main module needs FILE_FUNCTIONS")

    print("AUTO MULTI DEV VP SALE STATIC CONTRACT VERIFIED")
    print("runtime=isolated_worker_v3")
    print("flow=collect_gold_round_robin_exact_x10_two_swipes_repeat")
    print("allowed_items=tao_say,vai_vang")
    print("clear_stall_runtime=untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
