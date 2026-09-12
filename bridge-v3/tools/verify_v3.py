from __future__ import annotations

import argparse
from pathlib import Path


def require(text: str, token: str, label: str) -> None:
    if token not in text:
        raise AssertionError(f"{label}: missing {token}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.root).resolve()
    wrapper = root / "native" / "kvtm_bridge_v3.cpp"
    base = root / "native" / "kvtm_bridge_v3_base.cpp"
    loader = root / "native" / "kvtm_loader_v3.cpp"
    for path in (wrapper, base, loader):
        if not path.is_file():
            raise AssertionError(f"Missing Bridge V3 source: {path}")

    hardcap = wrapper.read_text(encoding="utf-8")
    legacy = base.read_text(encoding="utf-8")

    for token in (
        'include "kvtm_bridge_v3_base.cpp"',
        "KvtmBridgeBaseSendMessageW",
        "hooked_swap_buffers",
        "hooked_wgl_swap_layer_buffers",
        "patch_iat_target",
        "CreateWaitableTimerExW",
        "CREATE_WAITABLE_TIMER_HIGH_RESOLUTION",
        "SetWaitableTimer",
        "WaitForSingleObject(timer, INFINITE)",
        "pace_after_present",
        "WM_KVTM_FPS",
        "kvtm_hardcap::set_target",
    ):
        require(hardcap, token, "hard-cap wrapper")

    hardcap_body = hardcap.split("namespace kvtm_hardcap", 1)[1]
    if "while (" in hardcap_body and "while (time.monotonic" not in hardcap_body:
        # Native governor must wait in the kernel, never spin until a deadline.
        raise AssertionError("Hard-cap wrapper contains a native busy-spin loop")
    if "Sleep(" in hardcap_body:
        raise AssertionError("Hard-cap governor must not use Sleep() throttling")

    for token in (
        "KVTM_BRIDGE_V3",
        "CAPTURE3",
        "INPUT4",
        "BATCH_SWIPE",
        "FPS_LIMIT1",
        "dispatch_capture",
        "dispatch_touch",
        "dispatch_fps",
        'std::strncmp(input, "FPS ", 4)',
        'sprintf_s(output, "OK FPS %d\\n", command.fps)',
    ):
        require(legacy, token, "Bridge V3 base contract")

    print("KVTM BRIDGE V3 HARD-CAP SOURCE VERIFIED")
    print("capture=CAPTURE3-unchanged")
    print("input=INPUT4-unchanged")
    print("fps=OpenGL-present-hard-cap")
    print("wait=kernel-waitable-timer")
    print("busy_spin=false")
    print("sleep_throttle=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
