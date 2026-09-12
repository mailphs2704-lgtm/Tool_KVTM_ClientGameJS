from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "bridge-v3/native/kvtm_bridge_v3.cpp"
AUTOMATION = ROOT / "components/clientjs-auto/kvtm_automation/automation.py"
DEV_HOST = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_host.py"


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def main() -> int:
    for path in (NATIVE, AUTOMATION, DEV_HOST):
        if not path.is_file():
            raise AssertionError(f"Missing GPU policy source: {path}")

    native = NATIVE.read_text(encoding="utf-8")
    automation = AUTOMATION.read_text(encoding="utf-8")
    host = DEV_HOST.read_text(encoding="utf-8")
    ast.parse(automation, filename=str(AUTOMATION))
    ast.parse(host, filename=str(DEV_HOST))

    for token in (
        "WM_KVTM_FPS",
        "FPS_LIMIT1",
        "?setAnimationInterval@Director@cocos2d@@QAEXN@Z",
        "?setAnimationInterval@Director@cocos2d@@QAEXM@Z",
        'std::strncmp(input, "FPS ", 4)',
        'sprintf_s(output, "OK FPS %d\\n", command.fps)',
    ):
        require(native, token, f"Bridge V3 GPU governor missing: {token}")

    fps_body = native.split("LONG dispatch_fps", 1)[1].split(
        "LONG dispatch_touch", 1
    )[0]
    if "Sleep(" in fps_body:
        raise AssertionError("FPS governor must not throttle with Sleep()")
    require(
        fps_body,
        "1.0 / static_cast<double>(command->fps)",
        "FPS governor must translate FPS to Director animation interval",
    )

    for token in (
        "_AUTO_MULTI_DEV_FPS_LIMIT = 20",
        '_AUTO_MULTI_DEV_FPS_CAPABILITY = "FPS_LIMIT1"',
        'pipe(f"FPS {_AUTO_MULTI_DEV_FPS_LIMIT}\\n", 1000)',
        "AUTO capture giữ nguyên native size",
        "_apply_auto_multi_dev_fps_governor(self.driver, context)",
    ):
        require(automation, token, f"AUTO MULTI DEV GPU policy missing: {token}")

    for token in (
        "def _install_gpu_runtime_policy(dev_entry) -> None:",
        "app_cls._register_live_thumbnail = disabled_register_live_thumbnail",
        "app_cls._update_live_dwm = disabled_update_live_dwm",
        "app_cls._live_worker = disabled_live_worker",
        "app_cls._poll_live_results = disabled_poll_live_results",
        "_install_gpu_runtime_policy(kvtm_multi_dev_entry)",
        "DWM Live View=OFF",
    ):
        require(host, token, f"Multi DEV DWM policy missing: {token}")

    print("AUTO MULTI DEV GPU POLICY VERIFIED")
    print("dwm_live_view=disabled-dev-only")
    print("client_fps=20-when-FPS_LIMIT1")
    print("governor=Director::setAnimationInterval")
    print("sleep_throttle=false")
    print("capture_resolution=unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
