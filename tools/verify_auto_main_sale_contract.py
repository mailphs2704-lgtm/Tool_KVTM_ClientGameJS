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

FILE_FUNCTIONS = (
    "Đọc và parse các file AUTO Main bắt buộc",
    "Khóa đúng ba VP được phép",
    "Khóa thứ tự thu vàng, treo VP và hai swipe",
    "Khóa xác minh giao dịch trước khi ghi nhận",
    "Khóa wiring resident runtime và nút bán riêng",
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

    for token in ('"tao_say"', '"vai_vang"', '"tinh_dau_hh"'):
        require(recognition, token, f"Missing allowed AUTO VP: {token}")

    require(action, "class AutoMainSellingActions", "Isolated sale action missing")
    require(action, "if not self.selling._find_empty_slot()", "Empty-slot gate missing")
    require(action, "self.recognition.scan_samples(", "Allowed-item scan missing")
    require(action, "max(recognized", "Best recognized VP selection missing")
    require(action, "self.selling._finish_batch_from_match(", "Verified listing gate missing")
    require(action, 'status="NO_ALLOWED_ITEM"', "No-item safe stop missing")

    require(workflow, "collect_own_stall_gold(maximum=8)", "Gold-before-sale order missing")
    require(workflow, "attempt = self.sale.sell_next_allowed", "Per-view sale missing")
    require(workflow, "self.auto.stall.next_view()", "Two-swipe next-view step missing")
    require(workflow, "finally:", "Own-stall cleanup guard missing")
    require(workflow, "self.auto.stall.close_own_stall()", "Own-stall close missing")
    if workflow.index("collected += self.auto.stall.collect_own_stall_gold") > workflow.index("attempt = self.sale.sell_next_allowed"):
        raise AssertionError("AUTO Main must collect gold before listing VP")

    require(gui, 'text="▶ Bán VP AUTO"', "AUTO sale button missing")
    require(gui, "command=self._start_clean_vp_sale", "AUTO sale button wiring missing")
    require(entry, "def _start_clean_vp_sale", "AUTO sale launcher missing")
    require(entry, "AutoVpSaleWorkflow(automation).run", "Resident sale workflow missing")
    require(entry, 'outcome = "sale_finished"', "AUTO sale result handling missing")

    for text in (action, workflow):
        forbid(text, ".pyc", "AUTO Main sale must not load legacy pyc")
        forbid(text, "clear_stall_probe_runtime", "AUTO Main sale must not call Dọn quầy runtime")
        require(text, "FILE_FUNCTIONS", "Every new AUTO Main module needs FILE_FUNCTIONS")

    print("AUTO MULTI DEV VP SALE STATIC CONTRACT VERIFIED")
    print("runtime=resident")
    print("flow=home_open_stall_collect_gold_sell_two_swipes_repeat")
    print("allowed_items=tao_say,vai_vang,tinh_dau_hh")
    print("clear_stall_runtime=untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
