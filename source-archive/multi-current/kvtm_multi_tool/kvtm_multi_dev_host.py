from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import struct
import sys
import threading
import time
import traceback


_RUNTIME_TIMEOUT_SECONDS = 15.0
_MULTI_DEV_FPS_PRESETS = (10, 15, 20, 25, 30, 40, 60)
_MULTI_DEV_FPS_DEFAULT = 20
_MULTI_DEV_FPS_CAPABILITY = "FPS_LIMIT1"
_PINNED_MULTI_DEV_TUNING = {
    # Operator-verified Multi DEV values. These are the source fallback if a new
    # machine/profile has no settings.json yet; persistent saved values still win.
    "floor_swipe_duration": 0.350,
    "plant_harvest_duration": 0.035,
    "vp_production_delay": 0.070,
    "crop_check_interval": 0.100,
}
_PINNED_CLEAR_STALL_DEFAULTS = {
    # Stable Dọn quầy baseline. Existing per-profile settings are never replaced;
    # these values only self-heal fields that disappear after a schema/update.
    "schema_version": 2,
    "target_mode": "friend_ordinal",
    "target_friend_ordinal": 1,
    "target_stall_id": 2,
    "buy_quantity": 10,
    "max_scan_pages": 4,
    "interval_minutes": 65,
    "next_run_at": 0,
    "close_client_after_run": True,
    "enabled": False,
    "last_checkpoint": "WAITING",
}
_AUTO_MAIN_FRESH_MARKER = ".fresh-client-start.json"


def _roots() -> tuple[Path, Path, Path]:
    multi_root = Path(__file__).resolve().parent
    package_root = multi_root.parent
    component_root = package_root / "components" / "clientjs-auto"
    auto_root = package_root / "AUTO_PRO"
    return multi_root, component_root, auto_root


def _check_python() -> None:
    if tuple(sys.version_info[:2]) != (3, 11) or struct.calcsize("P") * 8 != 64:
        raise RuntimeError(
            "KVTM Multi DEV resident host yêu cầu CPython 3.11 x64; "
            f"đang chạy {sys.version.split()[0]} ({sys.executable})"
        )


def _load_resident_runtime(component_root: Path, auto_root: Path) -> None:
    component_text = str(component_root)
    if component_text not in sys.path:
        sys.path.insert(0, component_text)

    from kvtm_automation.runtime.bootstrap import install_binary_dependencies

    print(
        "[KVTM DEV] Resident host: loading image runtime BEFORE importing Multi UI...",
        flush=True,
    )
    started = time.monotonic()
    done = threading.Event()
    failure: list[BaseException] = []

    def log(message: str) -> None:
        print(f"[CLEAN RUNTIME] {message}", flush=True)

    def load() -> None:
        try:
            install_binary_dependencies(auto_root, logger=log)
        except BaseException as exc:
            failure.append(exc)
        finally:
            done.set()

    thread = threading.Thread(
        target=load,
        name="kvtm-dev-resident-host-image-runtime",
        daemon=True,
    )
    thread.start()

    next_heartbeat = 2.0
    while not done.wait(0.10):
        elapsed = time.monotonic() - started
        if elapsed >= _RUNTIME_TIMEOUT_SECONDS:
            raise RuntimeError(
                "Resident host image runtime không sẵn sàng sau "
                f"{_RUNTIME_TIMEOUT_SECONDS:.0f}s"
            )
        if elapsed >= next_heartbeat:
            print(f"[CLEAN RUNTIME] resident host import... {elapsed:.0f}s", flush=True)
            next_heartbeat += 2.0

    if failure:
        raise failure[0]

    import cv2
    import numpy
    from PIL import Image  # noqa: F401

    print(
        "[CLEAN RUNTIME] RESIDENT HOST READY "
        f"after {time.monotonic() - started:.2f}s | "
        f"cv2={cv2.__version__} | numpy={numpy.__version__}",
        flush=True,
    )


def _install_non_modal_error_ui(core) -> None:
    """Keep Multi DEV runtime errors in status/logs instead of modal dialogs."""

    def showerror_no_modal(title, message, *args, **kwargs):
        del args, kwargs
        text = str(message).replace("\n", " | ")
        print(f"[KVTM DEV] UI ERROR NON-MODAL | {title}: {text}", flush=True)
        return "ok"

    core.messagebox.showerror = showerror_no_modal
    print(
        "[KVTM DEV] Error UI: messagebox.showerror disabled; status/log recovery enabled",
        flush=True,
    )


def _install_pinned_dev_settings(core) -> None:
    """Pin proven DEV defaults and self-heal Dọn quầy profile settings."""
    core.DEFAULT_AUTO_TUNING.update(_PINNED_MULTI_DEV_TUNING)

    original_clear_stall_job = core.MultiApp._clear_stall_job

    def pinned_clear_stall_job(self, profile_id: str) -> dict:
        profile_id = str(profile_id)
        existing = original_clear_stall_job(self, profile_id)
        current = dict(existing) if isinstance(existing, dict) else {}
        defaults = dict(_PINNED_CLEAR_STALL_DEFAULTS)
        defaults.update({
            "job_id": f"clear-stall-{profile_id}",
            "clone_profile_id": profile_id,
            "allowed_item_ids": [
                item_id for item_id, _label in core.CLEAR_STALL_ITEM_OPTIONS
            ],
        })
        merged = dict(defaults)
        merged.update(current)
        if merged != current:
            self.settings.setdefault("clear_stall_jobs", {})[profile_id] = merged
            try:
                core.save_settings(self.settings)
            except Exception as exc:
                print(
                    "[KVTM DEV] WARN pinned Dọn quầy settings save failed: "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )
        return merged

    core.MultiApp._clear_stall_job = pinned_clear_stall_job
    print(
        "[KVTM DEV] Persistent settings READY | "
        "speed=0.350/0.035/0.070/0.100 | "
        "clear-stall defaults=friend1/storage2/x10/pages4/65m",
        flush=True,
    )


def _install_gpu_runtime_policy(dev_entry) -> None:
    """Remove Live View from Multi DEV and expose a Bridge V3 FPS menu."""
    app_cls = dev_entry.MultiDevApp
    if getattr(app_cls, "_gpu_runtime_policy_installed", False):
        return

    core = dev_entry.core
    original_unregister = app_cls._unregister_live_thumbnail
    original_build_ui = app_cls._build_ui

    def bridge_command(pid: int, command: str, timeout_ms: int = 1000) -> str:
        kernel32 = ctypes.windll.kernel32
        kernel32.CallNamedPipeW.argtypes = [
            wintypes.LPCWSTR, wintypes.LPVOID, wintypes.DWORD,
            wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
            wintypes.DWORD,
        ]
        kernel32.CallNamedPipeW.restype = wintypes.BOOL
        pipe_name = rf"\\.\pipe\KVTM-Cocos-{int(pid)}"
        payload = (str(command).rstrip("\r\n") + "\n").encode("ascii")
        output = ctypes.create_string_buffer(256)
        read = wintypes.DWORD()
        if not kernel32.CallNamedPipeW(
            pipe_name, ctypes.c_char_p(payload), len(payload), output,
            len(output), ctypes.byref(read), int(timeout_ms),
        ):
            raise ctypes.WinError()
        return output.raw[:read.value].decode("ascii", "replace").strip()

    def disabled_register_live_thumbnail(self, profile_id: str, source_hwnd: int) -> None:
        del source_hwnd
        profile_id = str(profile_id)
        self._live_enabled.discard(profile_id)

    def disabled_update_live_dwm(self) -> None:
        self._live_enabled.clear()
        for profile_id in tuple(getattr(self, "_live_thumbnails", {})):
            try:
                original_unregister(self, profile_id)
            except Exception:
                self._live_thumbnails.pop(profile_id, None)

    def disabled_live_worker(self) -> None:
        stop = getattr(self, "_bridge_stop", None)
        if stop is not None:
            stop.wait()

    def disabled_poll_live_results(self) -> None:
        return None

    def disabled_preview_selected(self) -> None:
        # DEV deliberately has no Preview/Live View route. AUTO owns native
        # Bridge V3 CAPTURE3 independently at the physical ClientJS resolution.
        self.note.set(
            "MULTI DEV: Live View đã được loại bỏ • "
            "AUTO CAPTURE3 giữ nguyên độ phân giải native"
        )

    def remove_live_view_widgets(widget) -> None:
        for child in tuple(widget.winfo_children()):
            try:
                text = str(child.cget("text")).strip()
            except Exception:
                text = ""
            if text == "Live View":
                child.destroy()
                continue
            remove_live_view_widgets(child)

    def apply_render_fps(self, fps: int) -> None:
        fps = int(fps)
        if fps not in _MULTI_DEV_FPS_PRESETS:
            self.note.set(f"FPS không hợp lệ: {fps}")
            return

        self._multi_dev_fps_value.set(fps)
        try:
            self._adopt_running_clients(core.running_clients())
        except Exception as exc:
            print(
                "[KVTM DEV] WARN FPS client scan failed: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )

        targets: list[int] = []
        for process in tuple(getattr(self, "processes", {}).values()):
            try:
                if process is not None and process.poll() is None:
                    pid = int(process.pid)
                    if pid not in targets:
                        targets.append(pid)
            except Exception:
                continue

        if not targets:
            self.note.set(
                f"FPS {fps} đã chọn • chưa có ClientJS đang chạy • "
                "mặc định AUTO vẫn 20 FPS"
            )
            return

        self.note.set(
            f"Đang áp dụng {fps} FPS cho {len(targets)} ClientJS qua Bridge V3..."
        )

        def worker() -> None:
            applied: list[int] = []
            unsupported: list[int] = []
            failed: list[tuple[int, str]] = []
            for pid in targets:
                try:
                    protocol = bridge_command(pid, "PING")
                    if _MULTI_DEV_FPS_CAPABILITY not in protocol.split():
                        unsupported.append(pid)
                        continue
                    response = bridge_command(pid, f"FPS {fps}")
                    if response != f"OK FPS {fps}":
                        raise RuntimeError(response or "empty Bridge response")
                    applied.append(pid)
                except Exception as exc:
                    failed.append((pid, f"{type(exc).__name__}: {exc}"))

            def finish() -> None:
                if applied:
                    message = (
                        f"FPS {fps} • Bridge V3 áp dụng {len(applied)}/{len(targets)} "
                        "ClientJS • AUTO CAPTURE3/native size không đổi"
                    )
                    if unsupported:
                        message += f" • {len(unsupported)} client cần nạp Bridge V3 mới"
                    if failed:
                        message += f" • lỗi {len(failed)} client"
                    self.note.set(message)
                elif unsupported:
                    self.note.set(
                        f"FPS {fps}: Bridge đang chạy chưa có FPS_LIMIT1 • "
                        "hãy restart ClientJS sau khi build DEV"
                    )
                else:
                    self.note.set(
                        f"FPS {fps}: chưa áp dụng được cho ClientJS • xem log DEV"
                    )
                if failed:
                    print(
                        "[KVTM DEV] FPS apply errors | "
                        + "; ".join(f"pid={pid} {error}" for pid, error in failed),
                        flush=True,
                    )

            try:
                self.after(0, finish)
            except Exception:
                pass

        threading.Thread(
            target=worker,
            name=f"kvtm-dev-fps-{fps}",
            daemon=True,
        ).start()

    def build_ui_without_live_view(self) -> None:
        original_build_ui(self)
        remove_live_view_widgets(self)

        self._multi_dev_fps_value = core.tk.IntVar(
            master=self, value=_MULTI_DEV_FPS_DEFAULT
        )
        try:
            menu_name = str(self.cget("menu") or "")
            menubar = self.nametowidget(menu_name) if menu_name else None
        except Exception:
            menubar = None
        if menubar is None:
            menubar = core.tk.Menu(self, tearoff=False)
            self.configure(menu=menubar)

        fps_menu = core.tk.Menu(menubar, tearoff=False)
        for fps in _MULTI_DEV_FPS_PRESETS:
            fps_menu.add_radiobutton(
                label=f"{fps} FPS",
                variable=self._multi_dev_fps_value,
                value=fps,
                command=lambda value=fps: apply_render_fps(self, value),
            )
        menubar.add_cascade(label="FPS", menu=fps_menu)
        self._multi_dev_fps_menu = fps_menu

    app_cls._register_live_thumbnail = disabled_register_live_thumbnail
    app_cls._update_live_dwm = disabled_update_live_dwm
    app_cls._live_worker = disabled_live_worker
    app_cls._poll_live_results = disabled_poll_live_results
    app_cls.preview_selected = disabled_preview_selected
    app_cls._build_ui = build_ui_without_live_view
    app_cls._set_multi_dev_render_fps = apply_render_fps
    app_cls._gpu_runtime_policy_installed = True
    print(
        "[KVTM DEV] GPU policy READY • Live View=REMOVED • DWM Live View=OFF • "
        "FPS menu=10/15/20/25/30/40/60 • default=20 • "
        "AUTO capture/native resolution=UNCHANGED",
        flush=True,
    )


def _install_auto_main_lifecycle_tracking(dev_entry) -> None:
    """Give each ClientJS generation one fresh-start gate per tool session.

    The first AUTO start for a live ``profile + ClientJS PID`` in this resident
    Multi DEV process is fresh, even when the ClientJS process was already open
    or adopted before AUTO started. This matches the operator lifecycle: after
    restarting the tool/ClientJS, popup handling owns a full 60-second window
    before any camera recovery is allowed.

    Stop AUTO -> Start AUTO again on the same ClientJS PID does not receive a new
    marker, so it re-enters through unknown-camera recovery instead. A new PID is
    a new ClientJS generation and receives the fresh gate once.
    """
    app_cls = dev_entry.MultiDevApp
    if getattr(app_cls, "_auto_main_lifecycle_tracking_installed", False):
        return

    original_start = app_cls._start_clean_auto_session
    original_launch = app_cls._launch

    def _is_alive(process) -> bool:
        try:
            return bool(process and process.poll() is None)
        except Exception:
            return False

    def _mark_fresh_client(self, profile_id: str, process, *, source: str) -> bool:
        profile_id = str(profile_id or "")
        if not profile_id or not _is_alive(process):
            return False

        pid = int(process.pid)
        key = (profile_id, pid)
        seen = getattr(self, "_auto_main_fresh_marked_clients", None)
        if not isinstance(seen, set):
            seen = set()
            self._auto_main_fresh_marked_clients = seen
        if key in seen:
            return False

        marker_root = dev_entry.core.APP_DIR / "auto-multi-dev" / profile_id
        marker_root.mkdir(parents=True, exist_ok=True)
        marker = marker_root / _AUTO_MAIN_FRESH_MARKER
        payload = {
            "version": 1,
            "profile_id": profile_id,
            "pid": pid,
            "created_at": time.time(),
        }
        marker.write_text(
            json.dumps(payload, ensure_ascii=True, separators=(",", ":")),
            encoding="utf-8",
        )
        seen.add(key)
        print(
            "[KVTM DEV] AUTO lifecycle marker • "
            f"fresh ClientJS profile={profile_id} pid={pid} source={source}",
            flush=True,
        )
        return True

    def tracked_start(self, *args, **kwargs):
        # A restarted resident tool may adopt ClientJS processes that were
        # already running before AUTO is pressed. The first AUTO start for each
        # current PID must still own the 60-second startup popup-only window.
        try:
            selected = list(map(str, self.selected_ids()))
        except Exception:
            selected = []
        for profile_id in selected:
            process = self.processes.get(profile_id)
            _mark_fresh_client(
                self,
                profile_id,
                process,
                source="existing-client-first-auto-start",
            )

        previous_depth = int(getattr(self, "_auto_main_launch_tracking_depth", 0) or 0)
        self._auto_main_launch_tracking_depth = previous_depth + 1
        try:
            return original_start(self, *args, **kwargs)
        finally:
            self._auto_main_launch_tracking_depth = previous_depth

    def tracked_launch(self, profile, *args, **kwargs):
        result = original_launch(self, profile, *args, **kwargs)
        if int(getattr(self, "_auto_main_launch_tracking_depth", 0) or 0) <= 0:
            return result

        profile_id = str((profile or {}).get("id") or "")
        process = self.processes.get(profile_id) if profile_id else None
        _mark_fresh_client(
            self,
            profile_id,
            process,
            source="auto-launched-client",
        )
        return result

    app_cls._start_clean_auto_session = tracked_start
    app_cls._launch = tracked_launch
    app_cls._auto_main_lifecycle_tracking_installed = True
    print(
        "[KVTM DEV] AUTO lifecycle tracking READY • "
        "first AUTO start per ClientJS PID=fresh; same PID re-entry afterwards",
        flush=True,
    )


def _configure_dpi() -> None:
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


def main() -> int:
    try:
        _check_python()
        multi_root, component_root, auto_root = _roots()
        if not component_root.is_dir() or not auto_root.is_dir():
            raise RuntimeError(
                f"Thiếu package runtime: component={component_root} auto={auto_root}"
            )

        # This is the ONLY native image import for the DEV lifetime. The process
        # stays alive afterwards and becomes the Multi UI + probe runtime.
        _load_resident_runtime(component_root, auto_root)

        multi_text = str(multi_root)
        if multi_text not in sys.path:
            sys.path.insert(0, multi_text)

        print("[KVTM DEV] Resident host: importing Multi UI AFTER runtime READY...", flush=True)
        import kvtm_multi_dev_entry
        from auto_builder_integration import install_auto_builder_integration
        from auto_error_log_integration import install_auto_error_log_integration
        from auto_main_profile_settings import install_auto_main_profile_settings
        from client_video_recorder import install_client_video_recorder
        from daily_sale_counter_integration import install_daily_sale_counter_integration

        # Multi DEV is unattended-capable: error dialogs must never block all
        # running clones. Callers still update note/status and every worker error
        # remains in action/detail logs.
        _install_non_modal_error_ui(kvtm_multi_dev_entry.core)
        _install_pinned_dev_settings(kvtm_multi_dev_entry.core)
        _install_gpu_runtime_policy(kvtm_multi_dev_entry)
        _install_auto_main_lifecycle_tracking(kvtm_multi_dev_entry)

        # Builder is DEV-only and is layered onto MultiDevApp after import. This
        # keeps the shared kvtm_multi.py production UI untouched while reusing its
        # exact ttk styles/tab strip/lifecycle.
        install_auto_builder_integration(
            kvtm_multi_dev_entry.MultiDevApp,
            kvtm_multi_dev_entry.core,
        )
        # Scheduler persistence is also DEV-only. Install it after Builder so it
        # can wrap the final AUTO Main controls without touching the core UI.
        install_auto_main_profile_settings(
            kvtm_multi_dev_entry.MultiDevApp,
            kvtm_multi_dev_entry.core,
        )
        # Daily counters and error journal wrap the final AUTO panel/detail area.
        # They are installed after Builder/Profile so their fields/buttons survive
        # normal UI reconstruction and remain scoped to the selected account.
        install_daily_sale_counter_integration(
            kvtm_multi_dev_entry.MultiDevApp,
            kvtm_multi_dev_entry.core,
        )
        install_auto_error_log_integration(
            kvtm_multi_dev_entry.MultiDevApp,
            kvtm_multi_dev_entry.core,
        )
        # Recorder is installed last so its GUI wrapper sees the final control
        # layout. It captures ClientJS HWND directly and never owns CAPTURE3.
        install_client_video_recorder(
            kvtm_multi_dev_entry.MultiDevApp,
            kvtm_multi_dev_entry.core,
        )

        _configure_dpi()
        app = kvtm_multi_dev_entry.MultiDevApp()
        app.mainloop()
        return 0
    except Exception as exc:
        print(
            f"[KVTM DEV] RESIDENT HOST FAILED: {type(exc).__name__}: {exc}",
            flush=True,
        )
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
