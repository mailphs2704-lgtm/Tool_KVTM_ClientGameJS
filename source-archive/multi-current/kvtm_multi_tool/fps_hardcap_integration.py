from __future__ import annotations

"""Multi DEV native FPS hard-cap integration.

This layer deliberately owns only Bridge V3 lifetime and the render-FPS menu.
It does not resize ClientJS, change CAPTURE3, or touch AUTO business workflows.
The native DLL sleeps the render thread with a kernel waitable timer at the
OpenGL present boundary, so there is no Python polling loop or busy-spin cost.
"""

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import threading
import time


_RENDER_FPS_SETTINGS_KEY = "multi_dev_render_fps"
_RENDER_FPS_ENV_KEY = "KVTM_MULTI_DEV_RENDER_FPS"
_RENDER_FPS_PRESETS = (10, 15, 20, 25, 30, 40, 60)
_RENDER_FPS_DEFAULT = 20
_RENDER_FPS_CAPABILITY = "FPS_LIMIT1"
_V3_PROTOCOL_TOKEN = "KVTM_BRIDGE_V3"


def _normalize_fps(raw) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = _RENDER_FPS_DEFAULT
    return value if value in _RENDER_FPS_PRESETS else _RENDER_FPS_DEFAULT


def _v3_command(pid: int, command: str, timeout_ms: int = 800) -> str:
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
    pipe_name = rf"\\.\pipe\KVTM-CocosV3-{int(pid)}"
    payload = (str(command).rstrip("\r\n") + "\n").encode("ascii")
    output = ctypes.create_string_buffer(512)
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


def install_fps_hardcap_integration(app_class, core) -> None:
    if getattr(app_class, "_kvtm_fps_hardcap_installed", False):
        return

    original_inject_bridge = app_class._inject_bridge

    def _fps_v3_files(self) -> tuple[Path, Path] | None:
        tool_dir = Path(core.TOOL_DIR)
        candidates = (
            tool_dir.parent / "AUTO_PRO" / "bin",
            tool_dir / "bin",
            tool_dir.parent / "bin",
        )
        for folder in candidates:
            loader = folder / "kvtm_loader_v3.exe"
            bridge = folder / "kvtm_bridge_v3.dll"
            if loader.is_file() and bridge.is_file():
                return loader, bridge
        return None

    def _fps_v3_ping(self, pid: int, timeout_ms: int = 500) -> str:
        response = _v3_command(int(pid), "PING", timeout_ms)
        tokens = response.upper().split()
        if _V3_PROTOCOL_TOKEN not in tokens:
            raise RuntimeError(f"Bridge không phải V3: {response}")
        if _RENDER_FPS_CAPABILITY not in tokens:
            raise RuntimeError(f"Bridge V3 thiếu FPS_LIMIT1: {response}")
        return response

    def _ensure_fps_v3_bridge(self, pid: int) -> bool:
        pid = int(pid)
        if pid <= 0:
            return False
        try:
            self._fps_v3_ping(pid, 180)
            return True
        except Exception:
            pass

        files = self._fps_v3_files()
        if not files:
            print(
                f"[KVTM DEV] FPS hard-cap WAIT • pid={pid} • thiếu Bridge V3 binary",
                flush=True,
            )
            return False
        loader, bridge = files
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            result = subprocess.run(
                [str(loader), str(pid), str(bridge)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=flags,
                timeout=15,
            )
            # A resident V3 may make a second loader invocation non-zero; PING
            # below is the authority, not the loader exit code.
            loader_detail = (result.stderr or result.stdout or "").strip()
        except Exception as exc:
            print(
                "[KVTM DEV] FPS hard-cap RETRY • "
                f"pid={pid} • inject={type(exc).__name__}: {exc}",
                flush=True,
            )
            return False

        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline:
            try:
                self._fps_v3_ping(pid, 250)
                return True
            except Exception:
                time.sleep(0.10)

        print(
            "[KVTM DEV] FPS hard-cap RETRY • "
            f"pid={pid} • Bridge V3 chưa READY"
            + (f" • loader={loader_detail}" if loader_detail else ""),
            flush=True,
        )
        return False

    def _apply_fps_hardcap_pid(
        self,
        pid: int,
        *,
        source: str,
        force: bool = False,
    ) -> bool:
        pid = int(pid)
        if pid <= 0:
            return False
        target = _normalize_fps(
            getattr(self, "_multi_dev_fps_target", None)
            if getattr(self, "_multi_dev_fps_target", None) is not None
            else self.settings.get(_RENDER_FPS_SETTINGS_KEY, _RENDER_FPS_DEFAULT)
        )
        self._multi_dev_fps_target = target

        applied = getattr(self, "_multi_dev_fps_applied", None)
        if not isinstance(applied, dict):
            applied = {}
            self._multi_dev_fps_applied = applied
        if not force and applied.get(pid) == target:
            return True

        if not self._ensure_fps_v3_bridge(pid):
            return False
        try:
            response = _v3_command(pid, f"FPS {target}", 1200)
            expected = f"OK FPS {target}"
            if response != expected:
                raise RuntimeError(response or "empty Bridge V3 response")
        except Exception as exc:
            print(
                "[KVTM DEV] FPS hard-cap RETRY • "
                f"pid={pid} • target={target} • source={source} • "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )
            return False

        applied[pid] = target
        print(
            "[KVTM DEV] FPS hard-cap APPLIED • "
            f"pid={pid} • target={target} • source={source} • "
            "Bridge=V3 • governor=OpenGL-present/waitable-timer • "
            "busy-spin=false • CAPTURE3 unchanged",
            flush=True,
        )
        return True

    def _schedule_fps_hardcap_policy(
        self,
        pids,
        *,
        source: str,
        force: bool = False,
    ) -> None:
        target = _normalize_fps(
            getattr(self, "_multi_dev_fps_target", None)
            if getattr(self, "_multi_dev_fps_target", None) is not None
            else self.settings.get(_RENDER_FPS_SETTINGS_KEY, _RENDER_FPS_DEFAULT)
        )
        applied = getattr(self, "_multi_dev_fps_applied", None)
        if not isinstance(applied, dict):
            applied = {}
            self._multi_dev_fps_applied = applied

        lock = getattr(self, "_fps_hardcap_pending_lock", None)
        if lock is None:
            lock = threading.Lock()
            self._fps_hardcap_pending_lock = lock
        pending = getattr(self, "_fps_hardcap_pending", None)
        if not isinstance(pending, set):
            pending = set()
            self._fps_hardcap_pending = pending

        targets: list[int] = []
        with lock:
            for raw_pid in pids:
                try:
                    pid = int(raw_pid)
                except (TypeError, ValueError):
                    continue
                if pid <= 0 or pid in pending or pid in targets:
                    continue
                if not force and applied.get(pid) == target:
                    continue
                pending.add(pid)
                targets.append(pid)
        if not targets:
            return

        def worker() -> None:
            try:
                for pid in targets:
                    self._apply_multi_dev_fps_pid(
                        pid, source=source, force=force
                    )
            finally:
                with lock:
                    for pid in targets:
                        pending.discard(pid)

        threading.Thread(
            target=worker,
            name=f"kvtm-fps-hardcap-{source}",
            daemon=True,
        ).start()

    def _set_fps_hardcap_target(self, fps: int) -> None:
        fps = _normalize_fps(fps)
        self._multi_dev_fps_target = fps
        self.settings[_RENDER_FPS_SETTINGS_KEY] = fps
        os.environ[_RENDER_FPS_ENV_KEY] = str(fps)
        core.save_settings(self.settings)
        try:
            self._multi_dev_fps_value.set(fps)
        except Exception:
            pass

        applied = getattr(self, "_multi_dev_fps_applied", None)
        if isinstance(applied, dict):
            applied.clear()
        self._schedule_multi_dev_fps_policy(
            self._live_client_pids(), source="menu-change", force=True
        )
        print(
            "[KVTM DEV] FPS hard-cap SELECTED • "
            f"target={fps} • persisted=true • transport=Bridge-V3",
            flush=True,
        )

    def inject_bridge_with_hardcap(self, pid: int) -> bool:
        pid = int(pid)
        legacy_ready = False
        try:
            legacy_ready = bool(original_inject_bridge(self, pid))
        except Exception as exc:
            print(
                "[KVTM DEV] WARN legacy bridge attach • "
                f"pid={pid} • {type(exc).__name__}: {exc}",
                flush=True,
            )
        hardcap_ready = self._ensure_fps_v3_bridge(pid)
        if hardcap_ready:
            self._schedule_multi_dev_fps_policy(
                (pid,), source="bridge-ready-v3", force=True
            )
        return legacy_ready or hardcap_ready

    app_class._fps_v3_files = _fps_v3_files
    app_class._fps_v3_ping = _fps_v3_ping
    app_class._ensure_fps_v3_bridge = _ensure_fps_v3_bridge
    app_class._apply_multi_dev_fps_pid = _apply_fps_hardcap_pid
    app_class._schedule_multi_dev_fps_policy = _schedule_fps_hardcap_policy
    app_class._set_multi_dev_render_fps = _set_fps_hardcap_target
    app_class._inject_bridge = inject_bridge_with_hardcap
    app_class._kvtm_fps_hardcap_installed = True

    print(
        "[KVTM DEV] FPS hard-cap runtime READY • "
        "OpenGL present governor • kernel waitable timer • "
        "no persistent Python polling • CAPTURE3/native resolution UNCHANGED",
        flush=True,
    )
