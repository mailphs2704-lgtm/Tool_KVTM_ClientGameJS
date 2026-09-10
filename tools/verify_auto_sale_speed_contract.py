from __future__ import annotations

"""Static guard for native-1000 AUTO Main VP sale fast-confidence path."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SALE = ROOT / "components/clientjs-auto/kvtm_automation/actions/auto_main_selling.py"


def main() -> int:
    text = SALE.read_text(encoding="utf-8")
    ast.parse(text, filename=str(SALE))

    required = (
        "N1000_FAST_CONFIDENCE_THRESHOLD = 0.99",
        "N500_EXACT_TEN_THRESHOLD = 0.78",
        "N500_EXACT_TEN_SCALES = (0.75, 0.90, 1.00, 1.10, 1.25, 1.40, 1.55)",
        "N1000_EXACT_TEN_THRESHOLD = 0.95",
        "N1000_EXACT_TEN_SCALES = (1.00,)",
        "EXACT_TEN_REQUIRED_PASSES = 2",
        "if native == (1000, 1000):",
        'threshold=self.N1000_FAST_CONFIDENCE_THRESHOLD',
        "required_passes=2",
        "fast_confidence = (",
        "quantity_marker.score >= self.N1000_FAST_CONFIDENCE_THRESHOLD",
        "if fast_confidence or quantity_passes >= self.EXACT_TEN_REQUIRED_PASSES:",
    )
    for token in required:
        if token not in text:
            raise AssertionError(f"AUTO sale speed contract missing: {token}")

    if text.count("self._wait_own_stall_ready_auto(") < 2:
        raise AssertionError("Pre-sale and POST_SALE must both use native1000 fast-confidence helper")

    if "N500_FAST" in text:
        raise AssertionError("Native500 must not gain a fast-confidence bypass")

    print("AUTO MULTI DEV SALE SPEED STATIC CONTRACT VERIFIED")
    print("native1000=confidence>=0.99-one-pass;fallback=existing-two-pass")
    print("native500=unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
