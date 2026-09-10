from __future__ import annotations

"""Static guard for native-1000 AUTO Main VP sale fast-confidence paths."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SALE = ROOT / "components/clientjs-auto/kvtm_automation/actions/auto_main_selling.py"
RECOGNITION = ROOT / "components/clientjs-auto/kvtm_automation/actions/item_recognition.py"


def _read(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path))
    return text


def main() -> int:
    sale = _read(SALE)
    recognition = _read(RECOGNITION)

    required_sale = (
        "N1000_FAST_CONFIDENCE_THRESHOLD = 0.99",
        "N500_EXACT_TEN_THRESHOLD = 0.78",
        "N500_EXACT_TEN_SCALES = (0.75, 0.90, 1.00, 1.10, 1.25, 1.40, 1.55)",
        "N1000_EXACT_TEN_THRESHOLD = 0.95",
        "N1000_EXACT_TEN_SCALES = (1.00,)",
        "EXACT_TEN_REQUIRED_PASSES = 2",
        "if native == (1000, 1000):",
        "threshold=self.N1000_FAST_CONFIDENCE_THRESHOLD",
        "required_passes=2",
        "fast_confidence = (",
        "quantity_marker.score >= self.N1000_FAST_CONFIDENCE_THRESHOLD",
        "if fast_confidence or quantity_passes >= self.EXACT_TEN_REQUIRED_PASSES:",
    )
    for token in required_sale:
        if token not in sale:
            raise AssertionError(f"AUTO sale speed contract missing: {token}")

    if sale.count("self._wait_own_stall_ready_auto(") < 2:
        raise AssertionError("Pre-sale and POST_SALE must both use native1000 fast-confidence helper")
    if "N500_FAST" in sale:
        raise AssertionError("Native500 must not gain a fast-confidence bypass")

    required_recognition = (
        "N1000_FAST_PRIMARY_SCALE = (1.00,)",
        "N1000_FAST_PRIMARY_THRESHOLD = 0.82",
        "def _fast_candidate_from_frame(",
        "primary_template = spec.templates[0]",
        "scales=self.N1000_FAST_PRIMARY_SCALE",
        "threshold=self.N1000_FAST_PRIMARY_THRESHOLD",
        'if log_prefix == "AUTO SELL VP" and (frame_w, frame_h) == (1000, 1000):',
        "if fast is not None:",
        "return (fast,)",
        "for template in spec.templates:",
        "scales=self.RECOGNITION_SCALES",
    )
    for token in required_recognition:
        if token not in recognition:
            raise AssertionError(f"AUTO VP fast discovery contract missing: {token}")

    if "FUNCTION_1_ITEM_IDS = (\"tao_say\", \"vai_vang\")" not in recognition:
        raise AssertionError("Function 1 recognition policy changed")
    if "FUNCTION_2_ITEM_IDS = (\"tao_say\", \"vai_vang\", \"tinh_dau_hh\")" not in recognition:
        raise AssertionError("Function 2 recognition policy changed")

    print("AUTO MULTI DEV SALE SPEED STATIC CONTRACT VERIFIED")
    print("native1000=stall/x10-fast-confidence+primary-VP-scale1-fast-discovery")
    print("vp-fast-threshold=0.82;fallback=full-multiscale-scan")
    print("native500=unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
