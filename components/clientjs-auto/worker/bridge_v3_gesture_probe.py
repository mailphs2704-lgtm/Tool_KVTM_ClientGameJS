from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import traceback


def configure_utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


configure_utf8_console()


def emit(event: str, **data) -> None:
    print(json.dumps({"event": event, **data}, ensure_ascii=False), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto-root", required=True)
    parser.add_argument("--duration", type=float, default=0.50)
    args = parser.parse_args()
    auto_root = Path(args.auto_root).resolve()

    try:
        from clear_stall_step1_probe import discover_dev_game_targets
        targets = discover_dev_game_targets(auto_root)
        if len(targets) != 1:
            raise RuntimeError(
                f"Probe gesture yêu cầu đúng 1 ClientJS DEV; hiện có {len(targets)}"
            )
        target = targets[0]
        pid = int(target["pid"])
        emit(
            "v3_gesture_progress",
            stage="target-verified",
            pid=pid,
            profile_id=target["profile_id"],
            profile_name=target["profile_name"],
        )

        from auto_worker import install_clientjs_runtime
        install_clientjs_runtime(auto_root)
        import uiautomator2 as u2

        driver = u2.connect(f"PC:{pid}")
        before = driver.screenshot(format="opencv")
        if before is None or tuple(before.shape[:2]) != (1000, 1000):
            raise RuntimeError("Capture V3 trước gesture không phải 1000x1000")

        timing = driver.swipe_points(
            [(500.0, 540.0), (500.0, 460.0)],
            duration=max(0.02, float(args.duration)),
        )
        if not isinstance(timing, dict):
            raise RuntimeError("EngineDriver không trả timing evidence V3")

        after = driver.screenshot(format="opencv")
        if after is None or tuple(after.shape[:2]) != (1000, 1000):
            raise RuntimeError("Capture V3 sau gesture không phải 1000x1000")

        requested = float(timing["requested_seconds"])
        actual = float(timing["actual_seconds"])
        error_ms = float(timing["timing_error_ms"])
        tolerance_ms = max(80.0, requested * 200.0)
        if abs(error_ms) > tolerance_ms:
            raise RuntimeError(
                f"Timing ngoài ngưỡng: error_ms={error_ms:.3f}, "
                f"tolerance_ms={tolerance_ms:.3f}"
            )

        emit(
            "v3_gesture_pass",
            stage="production-engine-driver-pass",
            pid=pid,
            driver_type=type(driver).__name__,
            capture_before="PASS",
            capture_after="PASS",
            requested_seconds=requested,
            actual_seconds=actual,
            timing_error_ms=error_ms,
            point_count=int(timing["point_count"]),
            tolerance_ms=tolerance_ms,
            gesture="center_vertical_80px",
        )
        return 0
    except Exception as exc:
        emit(
            "v3_gesture_error",
            stage="production-engine-driver-failed",
            error=repr(exc),
            traceback=traceback.format_exc(),
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
