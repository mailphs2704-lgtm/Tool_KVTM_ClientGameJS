from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
import threading
import time

import auto_builder_integration as builder_integration


__all__ = ["install_auto_main_profile_settings"]
FILE_FUNCTIONS = (
    "Lưu ba cấu hình scheduler AUTO MULTI DEV riêng theo từng profile/acc",
    "Đổi acc sẽ nạp ngay số vòng bán, thời gian chờ và công tắc qua bạn của acc đó",
    "Start nhiều acc sẽ đóng băng snapshot scheduler riêng của từng profile",
    "Migrate công tắc qua bạn global cũ sang từng profile một lần để không mất hành vi hiện tại",
    "Giữ FPS render Multi DEV theo vòng đời ClientJS/Bridge thay vì chỉ khi Function bắt đầu",
    "Tái khẳng định FPS trong bootstrap và định kỳ để chống ClientJS ghi đè animation interval",
)

_PROFILE_SETTINGS_KEY = "auto_multi_dev_profiles"
_LEGACY_FRIEND_REFRESH_KEY = "auto_multi_dev_friend_refresh_enabled"
_RENDER_FPS_SETTINGS_KEY = "multi_dev_render_fps"
_RENDER_FPS_ENV_KEY = "KVTM_MULTI_DEV_RENDER_FPS"
_RENDER_FPS_PRESETS = (10, 15, 20, 25, 30, 40, 60)
_RENDER_FPS_DEFAULT = 20
_RENDER_FPS_CAPABILITY = "FPS_LIMIT1"
_RENDER_FPS_STARTUP_WINDOW_SECONDS = 60.0
_RENDER_FPS_STARTUP_REASSERT_SECONDS = 2.0
_RENDER_FPS_STEADY_REASSERT_SECONDS = 30.0
_RENDER_FPS_SUCCESS_LOG_SECONDS = 30.0
_DEFAULT_PROFILE_SETTINGS = {
    "sale_every_loops": 1,
    "function_loop_delay_seconds": 0.0,
    "friend_refresh_enabled": False,
}


def _normalize_profile_settings(raw) -> dict:
    current = raw if isinstance(raw, dict) else {}
    try:
        sale_every = int(current.get("sale_every_loops", 1))
    except (TypeError, ValueError):
        sale_every = 1
    if not 1 <= sale_every <= 999:
        sale_every = 1

    try:
        loop_delay = float(current.get("function_loop_delay_seconds", 0.0))
    except (TypeError, ValueError):
        loop_delay = 0.0
    if not 0.0 <= loop_delay <= 3600.0:
        loop_delay = 0.0

    return {
        "sale_every_loops": sale_every,
        "function_loop_delay_seconds": loop_delay,
        "friend_refresh_enabled": bool(
            current.get("friend_refresh_enabled", False)
        ),
    }


def _normalize_render_fps(raw) -> int:
    try:
        fps = int(raw)
    except (TypeError, ValueError):
        fps = _RENDER_FPS_DEFAULT
    return fps if fps in _RENDER_FPS_PRESETS else _RENDER_FPS_DEFAULT


def _fps_bridge_command(pid: int, command: str, timeout_ms: int = 1000) -> str:
    kernel32 = ctypes.windll.kernel32
    kernel32.CallNamedPipeW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.DWORD,
    ]
    kernel32.CallNamedPipeW.restype = wintypes.BOOL
    pipe_name = rf"\\.\pipe\KVTM-Cocos-{int(pid)}"
    payload = (str(command).rstrip("\r\n") + "\n").encode("ascii")
    output = ctypes.create_string_buffer(256)
    read = wintypes.DWORD()
    if not kernel32.CallNamedPipeW(
        pipe_name,
        ctypes.c_char_p(payload),
        len(payload),
        output,
        len(output),
        ctypes.byref(read),
        int(timeout_ms),
    ):
        raise ctypes.WinError()
    return output.raw[: read.value].decode("ascii", "replace").strip()


def install_auto_main_profile_settings(app_class, core) -> None:
    """Layer per-profile scheduler and persistent render-FPS policy on Multi DEV."""
    if getattr(app_class, "_kvtm_auto_main_profile_settings_installed", False):
        return

    original_build = app_class._build_auto_panel
    original_build_ui = app_class._build_ui
    original_account_click = app_class._on_account_click
    original_refresh = app_class.refresh
    original_adopt_running_clients = app_class._adopt_running_clients
    original_inject_bridge = app_class._inject_bridge
    original_set_render_fps = getattr(app_class, "_set_multi_dev_render_fps", None)

    def _load_auto_multi_dev_profile_store(self) -> None:
        raw = {}
        try:
            loaded = json.loads(core.SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                raw = loaded
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            raw = {}

        raw_store = raw.get(_PROFILE_SETTINGS_KEY, {})
        store = {}
        if isinstance(raw_store, dict):
            for profile_id, saved in raw_store.items():
                store[str(profile_id)] = _normalize_profile_settings(saved)

        migrated = False
        if not store and _LEGACY_FRIEND_REFRESH_KEY in raw:
            legacy_enabled = bool(raw.get(_LEGACY_FRIEND_REFRESH_KEY, False))
            for profile in self.profiles:
                profile_id = str(profile.get("id") or "")
                if not profile_id:
                    continue
                migrated_cfg = dict(_DEFAULT_PROFILE_SETTINGS)
                migrated_cfg["friend_refresh_enabled"] = legacy_enabled
                store[profile_id] = migrated_cfg
            migrated = True

        self.settings[_PROFILE_SETTINGS_KEY] = store
        self.settings.pop(_LEGACY_FRIEND_REFRESH_KEY, None)
        if migrated:
            core.save_settings(self.settings)

    def _auto_multi_dev_profile_id(self) -> str | None:
        profile_id = str(getattr(self, "_active_profile_id", "") or "")
        if profile_id:
            return profile_id
        selected = list(map(str, self.selected_ids()))
        return selected[0] if len(selected) == 1 else None

    def _auto_multi_dev_profile_settings(self, profile_id: str) -> dict:
        profile_id = str(profile_id or "")
        store = self.settings.setdefault(_PROFILE_SETTINGS_KEY, {})
        if not isinstance(store, dict):
            store = {}
            self.settings[_PROFILE_SETTINGS_KEY] = store
        saved = _normalize_profile_settings(store.get(profile_id, {}))
        store[profile_id] = saved
        return dict(saved)

    def _load_friend_refresh_setting(self) -> bool:
        profile_id = self._auto_multi_dev_profile_id()
        if not profile_id:
            return False
        return bool(
            self._auto_multi_dev_profile_settings(profile_id)[
                "friend_refresh_enabled"
            ]
        )

    def _refresh_auto_multi_dev_profile_settings(self) -> None:
        if not hasattr(self, "auto_multi_dev_sale_every_spin"):
            return

        self._auto_multi_dev_profile_refreshing = True
        try:
            profile_id = self._auto_multi_dev_profile_id()
            profile = next(
                (
                    item for item in self.profiles
                    if str(item.get("id") or "") == str(profile_id or "")
                ),
                None,
            )
            state = "normal" if profile else "disabled"
            self.auto_multi_dev_sale_every_spin.configure(state=state)
            self.auto_multi_dev_function_loop_delay_spin.configure(state=state)
            self.auto_multi_dev_friend_refresh_button.configure(state=state)

            if not profile_id or profile is None:
                self.auto_multi_dev_sale_every_loops.set(
                    _DEFAULT_PROFILE_SETTINGS["sale_every_loops"]
                )
                self.auto_multi_dev_function_loop_delay.set(
                    _DEFAULT_PROFILE_SETTINGS["function_loop_delay_seconds"]
                )
                self.auto_multi_dev_friend_refresh_enabled.set(
                    _DEFAULT_PROFILE_SETTINGS["friend_refresh_enabled"]
                )
                return

            saved = self._auto_multi_dev_profile_settings(profile_id)
            self.auto_multi_dev_sale_every_loops.set(saved["sale_every_loops"])
            self.auto_multi_dev_function_loop_delay.set(
                saved["function_loop_delay_seconds"]
            )
            self.auto_multi_dev_friend_refresh_enabled.set(
                saved["friend_refresh_enabled"]
            )
        finally:
            self._auto_multi_dev_profile_refreshing = False

    def _save_auto_multi_dev_profile_settings(self) -> None:
        if getattr(self, "_auto_multi_dev_profile_refreshing", False):
            return

        profile_id = self._auto_multi_dev_profile_id()
        if not profile_id:
            return
        profile = next(
            (
                item for item in self.profiles
                if str(item.get("id") or "") == profile_id
            ),
            None,
        )
        if profile is None:
            return

        previous = self._auto_multi_dev_profile_settings(profile_id)
        try:
            sale_every = int(self.auto_multi_dev_sale_every_loops.get())
        except (TypeError, ValueError, core.tk.TclError):
            sale_every = int(previous["sale_every_loops"])
        sale_every = max(1, min(999, sale_every))

        try:
            loop_delay = float(self.auto_multi_dev_function_loop_delay.get())
        except (TypeError, ValueError, core.tk.TclError):
            loop_delay = float(previous["function_loop_delay_seconds"])
        loop_delay = max(0.0, min(3600.0, loop_delay))

        friend_refresh_enabled = bool(
            self.auto_multi_dev_friend_refresh_enabled.get()
        )
        saved = {
            "sale_every_loops": sale_every,
            "function_loop_delay_seconds": loop_delay,
            "friend_refresh_enabled": friend_refresh_enabled,
        }
        self.settings.setdefault(_PROFILE_SETTINGS_KEY, {})[profile_id] = saved
        self.settings.pop(_LEGACY_FRIEND_REFRESH_KEY, None)

        self._auto_multi_dev_profile_refreshing = True
        try:
            self.auto_multi_dev_sale_every_loops.set(sale_every)
            self.auto_multi_dev_function_loop_delay.set(loop_delay)
            self.auto_multi_dev_friend_refresh_enabled.set(
                friend_refresh_enabled
            )
        finally:
            self._auto_multi_dev_profile_refreshing = False

        core.save_settings(self.settings)
        self.note.set(
            "AUTO MULTI DEV • đã lưu riêng cho "
            f"{profile.get('name') or profile_id} • bán/{sale_every} vòng • "
            f"chờ {loop_delay:g}s • qua bạn #1/3 vòng="
            f"{'BẬT' if friend_refresh_enabled else 'TẮT'}"
        )

    def _save_auto_multi_dev_friend_refresh(self) -> None:
        self._save_auto_multi_dev_profile_settings()

    def _multi_dev_render_fps_target(self) -> int:
        target = getattr(self, "_multi_dev_fps_target", None)
        if target is None:
            target = self.settings.get(_RENDER_FPS_SETTINGS_KEY, _RENDER_FPS_DEFAULT)
        target = _normalize_render_fps(target)
        self._multi_dev_fps_target = target
        return target

    def _live_client_pids(self) -> list[int]:
        live: list[int] = []
        for process in tuple(getattr(self, "processes", {}).values()):
            try:
                if process is not None and process.poll() is None:
                    pid = int(process.pid)
                    if pid > 0 and pid not in live:
                        live.append(pid)
            except Exception:
                continue
        return live

    def _prune_multi_dev_fps_state(self, live_pids) -> None:
        live = {int(pid) for pid in live_pids if int(pid) > 0}
        for attribute in (
            "_multi_dev_fps_applied",
            "_multi_dev_fps_retry_at",
            "_multi_dev_fps_applied_at",
            "_multi_dev_fps_first_seen",
            "_multi_dev_fps_log_at",
        ):
            state = getattr(self, attribute, None)
            if not isinstance(state, dict):
                continue
            for pid in tuple(state):
                if int(pid) not in live:
                    state.pop(pid, None)

    def _apply_multi_dev_fps_pid(
        self,
        pid: int,
        *,
        source: str,
        force: bool = False,
    ) -> bool:
        pid = int(pid)
        target = self._multi_dev_render_fps_target()
        applied = getattr(self, "_multi_dev_fps_applied", None)
        if not isinstance(applied, dict):
            applied = {}
            self._multi_dev_fps_applied = applied
        retry_at = getattr(self, "_multi_dev_fps_retry_at", None)
        if not isinstance(retry_at, dict):
            retry_at = {}
            self._multi_dev_fps_retry_at = retry_at
        applied_at = getattr(self, "_multi_dev_fps_applied_at", None)
        if not isinstance(applied_at, dict):
            applied_at = {}
            self._multi_dev_fps_applied_at = applied_at
        first_seen = getattr(self, "_multi_dev_fps_first_seen", None)
        if not isinstance(first_seen, dict):
            first_seen = {}
            self._multi_dev_fps_first_seen = first_seen
        log_at = getattr(self, "_multi_dev_fps_log_at", None)
        if not isinstance(log_at, dict):
            log_at = {}
            self._multi_dev_fps_log_at = log_at

        now = time.monotonic()
        first_seen.setdefault(pid, now)
        startup_age = max(0.0, now - float(first_seen.get(pid, now) or now))
        reassert_seconds = (
            _RENDER_FPS_STARTUP_REASSERT_SECONDS
            if startup_age <= _RENDER_FPS_STARTUP_WINDOW_SECONDS
            else _RENDER_FPS_STEADY_REASSERT_SECONDS
        )
        previous_target = applied.get(pid)
        previous_applied_at = float(applied_at.get(pid, 0.0) or 0.0)
        if (
            not force
            and previous_target == target
            and now - previous_applied_at < reassert_seconds
        ):
            return True
        if not force and now < float(retry_at.get(pid, 0.0) or 0.0):
            return False

        try:
            protocol = _fps_bridge_command(pid, "PING")
            if _RENDER_FPS_CAPABILITY not in protocol.split():
                retry_at[pid] = now + 5.0
                print(
                    "[KVTM DEV] FPS policy WAIT • "
                    f"pid={pid} • target={target} • source={source} • "
                    "Bridge chưa quảng bá FPS_LIMIT1",
                    flush=True,
                )
                return False
            response = _fps_bridge_command(pid, f"FPS {target}")
            expected = f"OK FPS {target}"
            if response != expected:
                raise RuntimeError(response or "empty Bridge response")
        except Exception as exc:
            retry_at[pid] = now + 1.0
            print(
                "[KVTM DEV] FPS policy RETRY • "
                f"pid={pid} • target={target} • source={source} • "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )
            return False

        applied[pid] = target
        applied_at[pid] = now
        retry_at.pop(pid, None)
        repeated = previous_target == target and previous_applied_at > 0.0
        should_log = (
            force
            or not repeated
            or source != "adopt"
            or now - float(log_at.get(pid, 0.0) or 0.0)
            >= _RENDER_FPS_SUCCESS_LOG_SECONDS
        )
        if should_log:
            event = "REASSERT" if repeated else "APPLIED"
            print(
                f"[KVTM DEV] FPS policy {event} • "
                f"pid={pid} • target={target} • source={source} • "
                f"startup_age={startup_age:.1f}s • lease={reassert_seconds:.1f}s • "
                "Director::setAnimationInterval • CAPTURE3 unchanged",
                flush=True,
            )
            log_at[pid] = now
        return True

    def _schedule_multi_dev_fps_policy(
        self,
        pids,
        *,
        source: str,
        force: bool = False,
    ) -> None:
        targets = []
        for raw_pid in pids:
            try:
                pid = int(raw_pid)
            except (TypeError, ValueError):
                continue
            if pid > 0 and pid not in targets:
                targets.append(pid)
        if not targets:
            return

        def worker() -> None:
            for pid in targets:
                self._apply_multi_dev_fps_pid(
                    pid,
                    source=source,
                    force=force,
                )

        threading.Thread(
            target=worker,
            name=f"kvtm-dev-fps-policy-{source}",
            daemon=True,
        ).start()

    def _set_persistent_multi_dev_render_fps(self, fps: int) -> None:
        fps = _normalize_render_fps(fps)
        self._multi_dev_fps_target = fps
        self.settings[_RENDER_FPS_SETTINGS_KEY] = fps
        os.environ[_RENDER_FPS_ENV_KEY] = str(fps)
        applied = getattr(self, "_multi_dev_fps_applied", None)
        if isinstance(applied, dict):
            applied.clear()
        applied_at = getattr(self, "_multi_dev_fps_applied_at", None)
        if isinstance(applied_at, dict):
            applied_at.clear()
        core.save_settings(self.settings)

        if callable(original_set_render_fps):
            original_set_render_fps(self, fps)
        else:
            try:
                self._multi_dev_fps_value.set(fps)
            except Exception:
                pass

        self._schedule_multi_dev_fps_policy(
            self._live_client_pids(),
            source="menu-change",
            force=True,
        )
        print(
            "[KVTM DEV] FPS policy SELECTED • "
            f"target={fps} • persisted=true • worker_env={_RENDER_FPS_ENV_KEY}",
            flush=True,
        )

    def build_ui_with_persistent_fps(self) -> None:
        target = _normalize_render_fps(
            self.settings.get(_RENDER_FPS_SETTINGS_KEY, _RENDER_FPS_DEFAULT)
        )
        self._multi_dev_fps_target = target
        self._multi_dev_fps_applied = {}
        self._multi_dev_fps_retry_at = {}
        self._multi_dev_fps_applied_at = {}
        self._multi_dev_fps_first_seen = {}
        self._multi_dev_fps_log_at = {}
        self.settings[_RENDER_FPS_SETTINGS_KEY] = target
        os.environ[_RENDER_FPS_ENV_KEY] = str(target)

        original_build_ui(self)

        try:
            self._multi_dev_fps_value.set(target)
        except Exception:
            pass
        fps_menu = getattr(self, "_multi_dev_fps_menu", None)
        if fps_menu is not None:
            for index, fps in enumerate(_RENDER_FPS_PRESETS):
                try:
                    fps_menu.entryconfigure(
                        index,
                        command=lambda value=fps: self._set_multi_dev_render_fps(value),
                    )
                except Exception as exc:
                    print(
                        "[KVTM DEV] WARN FPS menu rebind failed • "
                        f"index={index} • fps={fps} • {type(exc).__name__}: {exc}",
                        flush=True,
                    )

        print(
            "[KVTM DEV] FPS persistent policy READY • "
            f"target={target} • bootstrap reassert="
            f"{_RENDER_FPS_STARTUP_REASSERT_SECONDS:g}s/"
            f"{_RENDER_FPS_STARTUP_WINDOW_SECONDS:g}s • steady reassert="
            f"{_RENDER_FPS_STEADY_REASSERT_SECONDS:g}s • "
            "AUTO worker inherits same target",
            flush=True,
        )

    def adopt_running_clients(self, rows: list[dict]) -> None:
        result = original_adopt_running_clients(self, rows)
        live_pids = self._live_client_pids()
        self._prune_multi_dev_fps_state(live_pids)
        self._schedule_multi_dev_fps_policy(
            live_pids,
            source="adopt",
            force=False,
        )
        return result

    def inject_bridge(self, pid: int) -> bool:
        pid = int(pid)
        already_bridged = pid in set(getattr(self, "_bridged_pids", set()))
        ready = bool(original_inject_bridge(self, pid))
        if ready:
            self._schedule_multi_dev_fps_policy(
                (pid,),
                source="bridge-ready",
                force=not already_bridged,
            )
        return ready

    def build_auto_panel(self) -> None:
        self._auto_multi_dev_profile_refreshing = False
        self._load_auto_multi_dev_profile_store()
        original_build(self)

        self.auto_multi_dev_sale_every_spin.configure(
            command=self._save_auto_multi_dev_profile_settings
        )
        self.auto_multi_dev_function_loop_delay_spin.configure(
            command=self._save_auto_multi_dev_profile_settings
        )
        for widget in (
            self.auto_multi_dev_sale_every_spin,
            self.auto_multi_dev_function_loop_delay_spin,
        ):
            widget.bind(
                "<FocusOut>",
                lambda _event: self._save_auto_multi_dev_profile_settings(),
                add="+",
            )
            widget.bind(
                "<Return>",
                lambda _event: self._save_auto_multi_dev_profile_settings(),
                add="+",
            )
        self.after_idle(self._refresh_auto_multi_dev_profile_settings)

    def account_click(self, tree, event) -> None:
        # Flush the account currently shown before core changes active_profile_id.
        self._save_auto_multi_dev_profile_settings()
        result = original_account_click(self, tree, event)
        self._refresh_auto_multi_dev_profile_settings()
        return result

    def refresh(self) -> None:
        before = str(getattr(self, "_active_profile_id", "") or "")
        result = original_refresh(self)
        after = str(getattr(self, "_active_profile_id", "") or "")
        if before != after:
            self._refresh_auto_multi_dev_profile_settings()
        return result

    def start_configured_auto_main(self) -> None:
        selected = list(map(str, self.selected_ids()))
        if not selected:
            core.messagebox.showinfo(
                core.APP_NAME,
                "Hãy chọn ít nhất một tài khoản để chạy AUTO MULTI DEV.",
            )
            return

        # Flush the currently visible account before building per-profile
        # snapshots. Other checked accounts keep their own saved values.
        self._save_auto_multi_dev_profile_settings()

        function_id = str(
            getattr(self, "_auto_multi_dev_selected_function_id", "function_1")
        )
        options = dict(builder_integration._AUTO_MAIN_FUNCTION_OPTIONS)
        if function_id not in options:
            core.messagebox.showerror(
                core.APP_NAME, "Chức năng AUTO MULTI DEV chưa hợp lệ."
            )
            return

        per_profile = {}
        for profile_id in selected:
            saved = self._auto_multi_dev_profile_settings(profile_id)
            config = {
                "version": 1,
                "function_id": function_id,
                "sale_every_loops": int(saved["sale_every_loops"]),
                "function_loop_delay_seconds": float(
                    saved["function_loop_delay_seconds"]
                ),
                "friend_refresh_enabled": bool(
                    saved["friend_refresh_enabled"]
                ),
                "client_restart_interval_seconds":
                    builder_integration._CLIENT_RESTART_INTERVAL_SECONDS,
                "skip_initial_sale_once": False,
            }
            per_profile[profile_id] = config
            self._auto_main_pending_config[profile_id] = dict(config)
            self._auto_main_active_config[profile_id] = dict(config)
            self._auto_main_restart_pending.discard(profile_id)

        if len(selected) == 1:
            current = per_profile[selected[0]]
            self.note.set(
                f"AUTO MULTI DEV • {options[function_id]} • "
                f"bán lại sau {current['sale_every_loops']} vòng • "
                f"chờ giữa vòng {current['function_loop_delay_seconds']:g}s • "
                "qua bạn #1/3 vòng="
                f"{'BẬT' if current['friend_refresh_enabled'] else 'TẮT'} • "
                "restart ClientJS=BLOCK (3h + lỗi)"
            )
        else:
            self.note.set(
                f"AUTO MULTI DEV • {options[function_id]} • "
                f"{len(selected)} tài khoản dùng lịch riêng từng acc • "
                "restart ClientJS=BLOCK (3h + lỗi)"
            )

        self._start_clean_auto_session()

    app_class._build_ui = build_ui_with_persistent_fps
    app_class._build_auto_panel = build_auto_panel
    app_class._on_account_click = account_click
    app_class.refresh = refresh
    app_class._adopt_running_clients = adopt_running_clients
    app_class._inject_bridge = inject_bridge
    app_class._set_multi_dev_render_fps = _set_persistent_multi_dev_render_fps
    app_class._multi_dev_render_fps_target = _multi_dev_render_fps_target
    app_class._live_client_pids = _live_client_pids
    app_class._prune_multi_dev_fps_state = _prune_multi_dev_fps_state
    app_class._apply_multi_dev_fps_pid = _apply_multi_dev_fps_pid
    app_class._schedule_multi_dev_fps_policy = _schedule_multi_dev_fps_policy
    app_class._load_auto_multi_dev_profile_store = (
        _load_auto_multi_dev_profile_store
    )
    app_class._auto_multi_dev_profile_id = _auto_multi_dev_profile_id
    app_class._auto_multi_dev_profile_settings = (
        _auto_multi_dev_profile_settings
    )
    app_class._refresh_auto_multi_dev_profile_settings = (
        _refresh_auto_multi_dev_profile_settings
    )
    app_class._save_auto_multi_dev_profile_settings = (
        _save_auto_multi_dev_profile_settings
    )
    app_class._save_auto_multi_dev_friend_refresh = (
        _save_auto_multi_dev_friend_refresh
    )
    app_class._load_friend_refresh_setting = _load_friend_refresh_setting
    app_class._start_configured_auto_main = start_configured_auto_main
    app_class._kvtm_auto_main_profile_settings_installed = True