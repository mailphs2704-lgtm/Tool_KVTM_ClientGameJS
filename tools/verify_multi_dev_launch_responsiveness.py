from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi.py"
POSITION = ROOT / "source-archive/multi-current/kvtm_multi_tool/clear_stall_window_position.py"


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def main() -> int:
    text = SOURCE.read_text(encoding="utf-8")
    position = POSITION.read_text(encoding="utf-8")
    ast.parse(text, filename=str(SOURCE))
    ast.parse(position, filename=str(POSITION))
    launch_many = text.split("    def _launch_many", 1)[1].split(
        "    def stop_selected", 1
    )[0]
    display_apply = text.split("    def _apply_display_to_process", 1)[1].split(
        "    def configure_display", 1
    )[0]
    bridge_inject = text.split("    def _inject_bridge", 1)[1].split(
        "    def _bridge_monitor", 1
    )[0]

    require(text, "LAUNCH_STAGGER_MS = 4000", "Client launch stagger missing")
    require(launch_many, "self.after(", "Launch queue must yield to Tk event loop")
    if "time.sleep(" in launch_many:
        raise AssertionError("Launch queue must not sleep on Tk event loop")
    require(display_apply, "threading.Thread(", "Bridge attach must leave Tk thread")
    require(display_apply, "target=attach_bridge", "Bridge background target missing")
    require(bridge_inject, "_bridge_injecting_pids", "Concurrent injection guard missing")
    require(bridge_inject, "finally:", "Injection guard cleanup missing")
    if "_POLL_MS = 50" in position or "pin_when_window_exists" in position:
        raise AssertionError("Top-right position must not poll every 50ms during loading")
    require(
        position,
        "one-shot after display-ready",
        "Display-ready one-shot position policy missing",
    )
    print("AUTO MULTI DEV LAUNCH RESPONSIVENESS VERIFIED")
    print("launch=staggered-4000ms+nonblocking-tk")
    print("bridge=background-attach+per-pid-inflight-guard")
    print("position=one-shot-after-display-ready+no-50ms-poll")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
