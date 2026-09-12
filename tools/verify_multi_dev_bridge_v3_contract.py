from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "bridge-v3/native/kvtm_bridge_v3.cpp"
BASE = ROOT / "bridge-v3/native/kvtm_bridge_v3_base.cpp"
ENGINE = ROOT / "test-candidates/auto-pro-clientjs-temp/engine_driver.py"


def require(text: str, token: str, label: str) -> None:
    if token not in text:
        raise AssertionError(f"{label}: missing {token}")


def main() -> int:
    for path in (WRAPPER, BASE, ENGINE):
        if not path.is_file():
            raise AssertionError(f"Missing Bridge V3 contract file: {path}")

    wrapper = WRAPPER.read_text(encoding="utf-8")
    base = BASE.read_text(encoding="utf-8")
    engine = ENGINE.read_text(encoding="utf-8")

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
        "CAPTURE3",
        "CAPTUREW",
    ):
        require(engine, token, "AUTO Multi DEV V3 driver")

    print("AUTO MULTI DEV BRIDGE V3 CONTRACT VERIFIED")
    print("capture=CAPTURE3")
    print("input=INPUT4")
    print("fps=hard-cap-present")
    print("no-layout=true")
    print("sleep-throttle=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
