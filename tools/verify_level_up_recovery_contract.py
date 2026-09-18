from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTEXT = ROOT / "components/clientjs-auto/kvtm_automation/context.py"
ERRORS = ROOT / "components/clientjs-auto/kvtm_automation/errors.py"
VISION = ROOT / "components/clientjs-auto/kvtm_automation/runtime/vision.py"
POPUP = ROOT / "components/clientjs-auto/kvtm_automation/actions/popup.py"
MAIN = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_main/workflow.py"
ASSET = ROOT / "components/clientjs-auto/assets/items/lv_up.png"


def text(path: Path) -> str:
    value = path.read_text(encoding="utf-8")
    ast.parse(value, filename=str(path))
    return value


def require(value: str, marker: str, message: str) -> None:
    if marker not in value:
        raise AssertionError(message)


def main() -> int:
    context = text(CONTEXT)
    errors = text(ERRORS)
    vision = text(VISION)
    popup = text(POPUP)
    auto_main = text(MAIN)

    if not ASSET.is_file():
        raise AssertionError("Thiếu template lv_up.png")

    require(context, "def install_runtime_guard(", "Thiếu cooperative runtime guard")
    require(context, "def runtime_guard_paused(", "Thiếu guard recursion pause")
    require(errors, "class LevelUpPopupDetected(", "Thiếu typed level-up signal")
    require(vision, "trace: bool = True", "Guard không có quiet vision mode")
    require(popup, "def claim_level_up_reward(", "Thiếu exact reward claim")
    require(popup, "claim_point = (500, 688)", "Sai điểm Nhận đã được operator chứng minh")
    require(popup, "popup Lên cấp biến mất", "Thiếu hậu kiểm popup đóng")
    require(auto_main, "self.context.install_runtime_guard(", "Guard chưa cài vào AUTO Main")
    require(auto_main, "except LevelUpPopupDetected as exc:", "AUTO Main chưa bắt typed signal")
    require(auto_main, "recover_unknown_to_main(", "Recovery chưa về exact MAIN")
    require(auto_main, "không tăng counter", "Thiếu checkpoint restart invariant")

    print("PASS: level-up popup recovery contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
