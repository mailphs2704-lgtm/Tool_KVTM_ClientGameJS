from __future__ import annotations

import argparse
import hashlib
import importlib.util
from pathlib import Path
import sys
import time


def load_client(root: Path):
    path = root / "python" / "kvtm_bridge_v3.py"
    spec = importlib.util.spec_from_file_location("kvtm_bridge_v3", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load V3 client")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BridgeV3Client


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--output", required=True)
    parser.add_argument("--swipe-test", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    Client = load_client(root)
    client = Client(args.pid)
    protocol = client.verify_protocol()
    raw1, width1, height1, frame1 = client.capture_bgra()
    time.sleep(0.10)
    raw2, width2, height2, frame2 = client.capture_bgra()
    if (width1, height1) != (width2, height2):
        raise RuntimeError("capture dimensions changed during probe")
    if frame2 <= frame1:
        raise RuntimeError("frame id did not advance")
    timing = None
    if args.swipe_test:
        # Short center gesture. It is only executed after explicit BAT consent.
        timing = client.swipe([(500, 540), (500, 460)], duration_s=0.50)
    lines = [
        "KVTM BRIDGE V3 LIVE PROBE",
        f"pid={args.pid}",
        f"protocol={protocol}",
        f"size={width2}x{height2}",
        f"frame_before={frame1}",
        f"frame_after={frame2}",
        f"frame_sha256={hashlib.sha256(raw2).hexdigest()}",
        f"capture=PASS",
        f"swipe_test={'PASS' if timing else 'SKIPPED'}",
    ]
    if timing:
        lines.extend(
            f"{key}={value}" for key, value in timing.items()
        )
        tolerance_ms = max(80.0, timing["requested_seconds"] * 200.0)
        if abs(timing["timing_error_ms"]) > tolerance_ms:
            lines.append("timing=FAIL")
            (output / "LATEST.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
            raise RuntimeError("swipe timing outside tolerance")
        lines.append("timing=PASS")
    else:
        lines.append("timing=NOT_TESTED")
    (output / "LATEST.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
