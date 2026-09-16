from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "bridge-v3/native/kvtm_bridge_v3.cpp"
BASE = ROOT / "bridge-v3/native/kvtm_bridge_v3_base.cpp"
ENGINE = ROOT / "test-candidates/auto-pro-clientjs-temp/engine_driver.py"
MULTI = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi.py"
DEV_ENTRY = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_entry.py"


def require(text: str, token: str, label: str) -> None:
    if token not in text:
        raise AssertionError(f"{label}: missing {token}")


def main() -> int:
    for path in (WRAPPER, BASE, ENGINE, MULTI, DEV_ENTRY):
        if not path.is_file():
            raise AssertionError(f"Missing Bridge V3 contract file: {path}")

    wrapper = WRAPPER.read_text(encoding="utf-8")
    base = BASE.read_text(encoding="utf-8")
    engine = ENGINE.read_text(encoding="utf-8")
    multi = MULTI.read_text(encoding="utf-8")
    dev_entry = DEV_ENTRY.read_text(encoding="utf-8")
    ast.parse(multi, filename=str(MULTI))
    ast.parse(dev_entry, filename=str(DEV_ENTRY))

    for token in (
        "KVTM_BRIDGE_V3",
        "CAPTURE3",
        "INPUT4",
        "BATCH_SWIPE",
        "NO_LAYOUT",
        "CAPTURE3_SYNC2",
        "CAPTURE3_FIXEDMAP",
        "CAPTURE3_WRITERMAP2",
        "CAPTURE3_WRITERMSG1",
        "FPS_LIMIT1",
        "dispatch_capture",
        "dispatch_touch",
        "dispatch_fps",
        "claim_bridge_owner",
        "KVTM-BridgeV3-Owner-",
        "KVTM-CocosV3-",
    ):
        require(base, token, "Bridge V3 base")

    for token in (
        'include "kvtm_bridge_v3_base.cpp"',
        "KvtmBridgeBaseSendMessageW",
        "WM_KVTM_FPS",
        "hooked_swap_buffers",
        "patch_iat_target",
        "CreateWaitableTimerExW",
        "WaitForSingleObject(timer, INFINITE)",
    ):
        require(wrapper, token, "Bridge V3 hard-cap wrapper")

    if "Sleep(" in wrapper.split("namespace kvtm_hardcap", 1)[1]:
        raise AssertionError("Hard-cap present path must not use Sleep()")

    for token in (
        "KVTM-CocosV3-",
        'self._pipe("CAPTURE',
        "CAPTURE3",
    ):
        require(engine, token, "AUTO Multi DEV V3 driver")

    for token in (
        "self._bridge_inflight_pids: set[int] = set()",
        "def _request_bridge_injection",
        "target=self._inject_bridge",
        "self._bridge_inflight_pids.add(pid)",
        "self._bridge_inflight_pids.discard(pid)",
        "self._request_bridge_injection(int(proc.pid))",
        "- self._bridged_pids",
        "- self._bridge_inflight_pids",
        "if self._window_for_pid(pid):",
    ):
        require(multi, token, "Non-blocking single-owner Bridge injection")
    apply_display = multi.split(
        "def _apply_display_to_process", 1
    )[1].split("def configure_display", 1)[0]
    if "self._inject_bridge(" in apply_display:
        raise AssertionError("Tk display callback still runs blocking Bridge loader")
    require(
        dev_entry,
        "self._bridged_pids.add(int(new_pid))",
        "Restarted PID ready-Bridge adoption",
    )

    print("AUTO MULTI DEV BRIDGE V3 CONTRACT VERIFIED")
    print("capture=CAPTURE3")
    print("input=INPUT4")
    print("fps=hard-cap-present")
    print("no-layout=true")
    print("sleep-throttle=false")
    print("loader=background+single-inflight-per-pid+hwnd-ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
