from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "bridge-v3/native/kvtm_bridge_v3.cpp"
AUTOMATION = ROOT / "components/clientjs-auto/kvtm_automation/automation.py"
DEV_HOST = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_host.py"
PROFILE_SETTINGS = (
    ROOT
    / "source-archive/multi-current/kvtm_multi_tool/auto_main_profile_settings.py"
)


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def main() -> int:
    for path in (NATIVE, AUTOMATION, DEV_HOST, PROFILE_SETTINGS):
        if not path.is_file():
            raise AssertionError(f"Missing GPU policy source: {path}")

    native = NATIVE.read_text(encoding="utf-8")
    automation = AUTOMATION.read_text(encoding="utf-8")
    host = DEV_HOST.read_text(encoding="utf-8")
    profile_settings = PROFILE_SETTINGS.read_text(encoding="utf-8")
    ast.parse(automation, filename=str(AUTOMATION))
    ast.parse(host, filename=str(DEV_HOST))
    ast.parse(profile_settings, filename=str(PROFILE_SETTINGS))

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
        '_AUTO_MULTI_DEV_FPS_ENV = "KVTM_MULTI_DEV_RENDER_FPS"',
        "def _auto_multi_dev_fps_limit() -> int:",
        "fps = _auto_multi_dev_fps_limit()",
        'pipe(f"FPS {fps}\\n", 1000)',
        "target kế thừa từ Multi DEV",
        "AUTO capture giữ nguyên native size",
        "_apply_auto_multi_dev_fps_governor(self.driver, context)",
    ):
        require(automation, token, f"AUTO MULTI DEV GPU policy missing: {token}")
    if "_AUTO_MULTI_DEV_FPS_LIMIT = 20" in automation:
        raise AssertionError("AUTO worker must not hard-code 20 FPS anymore")

    for token in (
        "def _install_gpu_runtime_policy(dev_entry) -> None:",
        "_MULTI_DEV_FPS_PRESETS = (10, 15, 20, 25, 30, 40, 60)",
        "_MULTI_DEV_FPS_DEFAULT = 20",
        '_MULTI_DEV_FPS_CAPABILITY = "FPS_LIMIT1"',
        'pipe_name = rf"\\\\.\\pipe\\KVTM-Cocos-{int(pid)}"',
        'response = bridge_command(pid, f"FPS {fps}")',
        'menubar.add_cascade(label="FPS", menu=fps_menu)',
        "fps_menu.add_radiobutton(",
        'if text == "Live View":',
        "app_cls.preview_selected = disabled_preview_selected",
        "app_cls._register_live_thumbnail = disabled_register_live_thumbnail",
        "app_cls._update_live_dwm = disabled_update_live_dwm",
        "app_cls._live_worker = disabled_live_worker",
        "app_cls._poll_live_results = disabled_poll_live_results",
        "_install_gpu_runtime_policy(kvtm_multi_dev_entry)",
        "Live View=REMOVED",
        "DWM Live View=OFF",
        "AUTO capture/native resolution=UNCHANGED",
    ):
        require(host, token, f"Multi DEV GPU/UI policy missing: {token}")

    for token in (
        '_RENDER_FPS_SETTINGS_KEY = "multi_dev_render_fps"',
        '_RENDER_FPS_ENV_KEY = "KVTM_MULTI_DEV_RENDER_FPS"',
        "_RENDER_FPS_PRESETS = (10, 15, 20, 25, 30, 40, 60)",
        "_RENDER_FPS_STARTUP_WINDOW_SECONDS = 60.0",
        "_RENDER_FPS_STARTUP_REASSERT_SECONDS = 2.0",
        "_RENDER_FPS_STEADY_REASSERT_SECONDS = 30.0",
        "def _prune_multi_dev_fps_state(",
        "def _apply_multi_dev_fps_pid(",
        "_multi_dev_fps_applied_at",
        "_multi_dev_fps_first_seen",
        "startup_age <= _RENDER_FPS_STARTUP_WINDOW_SECONDS",
        "now - previous_applied_at < reassert_seconds",
        'event = "REASSERT" if repeated else "APPLIED"',
        "def _schedule_multi_dev_fps_policy(",
        "def _set_persistent_multi_dev_render_fps(self, fps: int) -> None:",
        'source="bridge-ready"',
        'source="adopt"',
        'source="menu-change"',
        "os.environ[_RENDER_FPS_ENV_KEY] = str(fps)",
        "self._prune_multi_dev_fps_state(live_pids)",
        "app_class._adopt_running_clients = adopt_running_clients",
        "app_class._inject_bridge = inject_bridge",
        "app_class._set_multi_dev_render_fps = _set_persistent_multi_dev_render_fps",
        "FPS persistent policy READY",
    ):
        require(
            profile_settings,
            token,
            f"Persistent Multi DEV FPS lifecycle policy missing: {token}",
        )

    print("AUTO MULTI DEV GPU POLICY VERIFIED")
    print("live_view=removed-dev-ui-and-route")
    print("dwm_live_view=disabled-dev-only")
    print("fps_menu=10,15,20,25,30,40,60")
    print("fps_default=20")
    print("fps_persistence=settings+environment")
    print("fps_lifecycle=adopt+bridge-ready+menu")
    print("fps_reassert=2s-for-60s+30s-steady")
    print("fps_worker=inherits-host-target")
    print("fps_transport=Bridge-V3-FPS_LIMIT1")
    print("governor=Director::setAnimationInterval")
    print("sleep_throttle=false")
    print("capture_resolution=unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
