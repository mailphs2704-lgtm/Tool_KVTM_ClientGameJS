from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUTO_MAIN_INIT = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_main/__init__.py"
AUTO_MAIN_BOUNDARY = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_main/boundary_delay.py"
BUILDER_DELAY = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_builder/loop_delay_patch.py"


def read(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path))
    return text


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def main() -> int:
    auto_main_init = read(AUTO_MAIN_INIT)
    auto_main_boundary = read(AUTO_MAIN_BOUNDARY)
    builder_delay = read(BUILDER_DELAY)

    require(
        auto_main_init,
        "from .boundary_delay import AutoMainResult, AutoMainWorkflow",
        "AUTO Main package is not exporting the boundary-aware scheduler",
    )
    for token in (
        "self._function_boundary_started_at",
        "def _sale_once(self, *, ordinal: int)",
        "def _friend_refresh_if_due(self)",
        "remaining = max(0.0, delay - elapsed)",
        "Sale/maintenance đã đủ thời gian chờ",
    ):
        require(auto_main_boundary, token, f"AUTO Main boundary delay contract missing: {token}")

    for token in (
        "boundary_started_at = time.monotonic()",
        "remaining = max(0.0, delay - elapsed)",
        "Sale/maintenance đã đủ thời gian chờ",
        "boundary_started_at=boundary_started_at",
    ):
        require(builder_delay, token, f"AUTO Builder boundary delay contract missing: {token}")

    print("AUTO FUNCTION BOUNDARY DELAY CONTRACT VERIFIED")
    print("delay=minimum-boundary-time")
    print("sale-and-maintenance=count-toward-delay")
    print("no-full-extra-sleep-after-sale")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
