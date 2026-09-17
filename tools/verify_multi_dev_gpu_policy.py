from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "bridge-v3/native/kvtm_bridge_v3.cpp"
BASE = ROOT / "bridge-v3/native/kvtm_bridge_v3_base.cpp"
AUTOMATION = ROOT / "components/clientjs-auto/kvtm_automation/automation.py"
DEV_HOST = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_host.py"
OWNED_HOST = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_owned_host.py"
PROFILE_SETTINGS = ROOT / "source-archive/multi-current/kvtm_multi_tool/auto_main_profile_settings.py"
HARD_CAP = ROOT / "source-archive/multi-current/kvtm_multi_tool/fps_hardcap_integration.py"


def require(text: str, token: str, label: str) -> None:
    if token not in text:
        raise AssertionError(f"{label}: missing {token}")


def main() -> int:
    for path in (
        WRAPPER, BASE, AUTOMATION, DEV_HOST, OWNED_HOST,
        PROFILE_SETTINGS, HARD_CAP,
    ):
        if not path.is_file():
            raise AssertionError(f"Missing GPU policy source: {path}")

    wrapper = WRAPPER.read_text(encoding="utf-8")
    base = BASE.read_text(encoding="utf-8")
    automation = AUTOMATION.read_text(encoding="utf-8")
    host = DEV_HOST.read_text(encoding="utf-8")
    owned = OWNED_HOST.read_text(encoding="utf-8")
    profile = PROFILE_SETTINGS.read_text(encoding="utf-8")
    hardcap = HARD_CAP.read_text(encoding="utf-8")
    for path, text in (
        (AUTOMATION, automation), (DEV_HOST, host), (OWNED_HOST, owned),
        (PROFILE_SETTINGS, profile), (HARD_CAP, hardcap),
    ):
        ast.parse(text, filename=str(path))

    for token in (
        "hooked_swap_buffers",
        "hooked_wgl_swap_layer_buffers",
        "CreateWaitableTimerExW",
        "SetWaitableTimer",
        "WaitForSingleObject(timer, INFINITE)",
        "patch_iat_target",
        "kvtm_hardcap::set_target",
    ):
        require(wrapper, token, "native hard-cap")
    native_governor = wrapper.split("namespace kvtm_hardcap", 1)[1]
    if "Sleep(" in native_governor:
        raise AssertionError("Native FPS hard-cap must not throttle with Sleep()")

    for token in (
        "CAPTURE3",
        "INPUT4",
        "FPS_LIMIT1",
        "dispatch_capture",
        "dispatch_touch",
        "dispatch_fps",
    ):
        require(base, token, "preserved Bridge V3 base")

    for token in (
        '_RENDER_FPS_PRESETS = (10, 15, 20, 25, 30, 40, 60)',
        'pipe_name = rf"\\\\.\\pipe\\KVTM-CocosV3-{int(pid)}"',
        "def _ensure_fps_v3_bridge(self, pid: int) -> bool:",
        "def _apply_fps_hardcap_pid(",
        "def _schedule_fps_hardcap_policy(",
        "def _set_fps_hardcap_target(self, fps: int) -> None:",
        'governor=OpenGL-present/waitable-timer',
        "no persistent Python polling",
        "app_class._apply_multi_dev_fps_pid = _apply_fps_hardcap_pid",
        "app_class._schedule_multi_dev_fps_policy = _schedule_fps_hardcap_policy",
        "app_class._set_multi_dev_render_fps = _set_fps_hardcap_target",
        "app_class._inject_bridge = inject_bridge_with_hardcap",
        "loading=uncapped",
        "apply=menu-or-auto-worker",
    ):
        require(hardcap, token, "Multi DEV hard-cap integration")

    hardcap_inject = hardcap.split("def inject_bridge_with_hardcap", 1)[1].split(
        "app_class._fps_v3_files", 1
    )[0]
    if "_schedule_multi_dev_fps_policy" in hardcap_inject:
        raise AssertionError("Bridge attach must not apply FPS during ZingPlay loading")

    profile_adopt = profile.split("def adopt_running_clients", 1)[1].split(
        "def inject_bridge", 1
    )[0]
    profile_inject = profile.split("def inject_bridge", 1)[1].split(
        "def build_auto_panel", 1
    )[0]
    if "_schedule_multi_dev_fps_policy" in profile_adopt + profile_inject:
        raise AssertionError("Profile lifecycle must not reassert FPS during loading")
    require(profile, "loading=uncapped", "Persistent FPS loading deferral missing")

    for token in (
        "import fps_hardcap_integration",
        "fps_hardcap_integration.install_fps_hardcap_integration(app_cls, core)",
    ):
        require(owned, token, "owned DEV host")

    for token in (
        "_MULTI_DEV_FPS_PRESETS = (10, 15, 20, 25, 30, 40, 60)",
        'menubar.add_cascade(label="FPS", menu=fps_menu)',
        'if text == "Live View":',
        "app_cls.preview_selected = disabled_preview_selected",
        "Live View=REMOVED",
        "DWM Live View=OFF",
        "AUTO capture/native resolution=UNCHANGED",
    ):
        require(host, token, "DEV GPU/UI policy")

    require(
        automation,
        '_AUTO_MULTI_DEV_FPS_ENV = "KVTM_MULTI_DEV_RENDER_FPS"',
        "AUTO worker target inheritance",
    )
    require(
        profile,
        '_RENDER_FPS_SETTINGS_KEY = "multi_dev_render_fps"',
        "persistent FPS setting",
    )

    print("AUTO MULTI DEV GPU HARD-CAP POLICY VERIFIED")
    print("live_view=removed")
    print("dwm_live_view=off")
    print("fps_menu=10,15,20,25,30,40,60")
    print("fps_transport=Bridge-V3")
    print("fps_governor=OpenGL-present-hard-cap")
    print("wait=kernel-waitable-timer")
    print("persistent_python_polling=false")
    print("sleep_throttle=false")
    print("capture_resolution=unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
