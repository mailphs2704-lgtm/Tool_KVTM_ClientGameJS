from __future__ import annotations

import ctypes
from ctypes import wintypes
import time


_MONITOR_DEFAULTTONEAREST = 0x00000002
_SWP_NOSIZE = 0x0001
_SWP_NOZORDER = 0x0004
_SWP_NOACTIVATE = 0x0010
_POSITION_FLAGS = _SWP_NOSIZE | _SWP_NOZORDER | _SWP_NOACTIVATE
_POLL_MS = 50
_WINDOW_CLOSE_CONFIRM_SECONDS = 0.75


def install_clear_stall_window_position(app_cls, core) -> None:
    """Pin launched ClientJS windows and keep their UI online state accurate."""
    if getattr(app_cls, "_clear_stall_window_position_installed", False):
        return

    user32 = ctypes.windll.user32
    user32.GetWindowRect.argtypes = [
        wintypes.HWND, ctypes.POINTER(wintypes.RECT),
    ]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.MonitorFromWindow.restype = wintypes.HANDLE
    user32.GetMonitorInfoW.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(core.MONITORINFO),
    ]
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [
        wintypes.HWND, wintypes.HWND,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL

    original_launch = app_cls._launch
    original_apply_display = app_cls._apply_display_to_process
    original_refresh = app_cls.refresh

    def tracked_pids(self) -> set[int]:
        value = getattr(self, "_client_top_right_position_pids", None)
        if not isinstance(value, set):
            value = set()
            self._client_top_right_position_pids = value
        return value

    def lifecycle_hwnds(self) -> dict[int, int]:
        value = getattr(self, "_client_lifecycle_hwnds", None)
        if not isinstance(value, dict):
            value = {}
            self._client_lifecycle_hwnds = value
        return value

    def missing_since(self) -> dict[int, float]:
        value = getattr(self, "_client_window_missing_since", None)
        if not isinstance(value, dict):
            value = {}
            self._client_window_missing_since = value
        return value

    def closed_reported(self) -> set[int]:
        value = getattr(self, "_client_window_closed_reported", None)
        if not isinstance(value, set):
            value = set()
            self._client_window_closed_reported = value
        return value

    def remember_window(self, pid: int, hwnd: int) -> None:
        if pid > 0 and hwnd:
            lifecycle_hwnds(self)[int(pid)] = int(hwnd)
            missing_since(self).pop(int(pid), None)
            closed_reported(self).discard(int(pid))

    def process_alive(self, pid: int) -> bool:
        for process in tuple(getattr(self, "processes", {}).values()):
            try:
                if (
                    process is not None
                    and int(process.pid) == int(pid)
                    and process.poll() is None
                ):
                    return True
            except Exception:
                continue
        return False

    def reconcile_client_windows(self) -> None:
        """Drop stale online refs after a ClientJS main HWND has really closed.

        The core UI classifies ONLINE from process.poll() only. ClientJS can keep
        its process alive briefly after the real top-level window has been
        destroyed, leaving the account stuck in ONLINE. Track the exact HWND
        once it has existed; hidden clients remain online because IsWindow still
        succeeds, while a destroyed HWND is confirmed before its stale process
        reference is removed.
        """
        processes = getattr(self, "processes", {})
        if not isinstance(processes, dict):
            return

        handles = lifecycle_hwnds(self)
        missing = missing_since(self)
        reported = closed_reported(self)
        marks = tracked_pids(self)
        now = time.monotonic()

        for profile_id, process in list(processes.items()):
            try:
                pid = int(process.pid)
                alive = process.poll() is None
            except Exception:
                continue

            if not alive:
                processes.pop(profile_id, None)
                handles.pop(pid, None)
                missing.pop(pid, None)
                reported.discard(pid)
                marks.discard(pid)
                continue

            try:
                visible_hwnd = int(self._window_for_pid(pid) or 0)
            except Exception:
                visible_hwnd = 0

            if visible_hwnd:
                remember_window(self, pid, visible_hwnd)
                continue

            known_hwnd = int(handles.get(pid, 0) or 0)
            if not known_hwnd:
                # Startup grace: the process may exist before ClientJS creates
                # its first top-level window, so process-only ONLINE is retained.
                continue

            if user32.IsWindow(wintypes.HWND(known_hwnd)):
                # The existing “Ẩn/Hiện client” feature intentionally hides the
                # window. A hidden HWND still exists and must stay ONLINE.
                missing.pop(pid, None)
                continue

            first_missing = missing.setdefault(pid, now)
            if now - float(first_missing) < _WINDOW_CLOSE_CONFIRM_SECONDS:
                continue

            # Main ClientJS HWND was destroyed while the process lingered. Remove
            # only the stale runtime reference; do not terminate the process.
            processes.pop(profile_id, None)
            marks.discard(pid)
            if pid not in reported:
                print(
                    "[KVTM DEV] ClientJS window closed -> account OFF | "
                    f"profile={profile_id} pid={pid} hwnd={known_hwnd}",
                    flush=True,
                )
                reported.add(pid)

    def pin_top_right(hwnd: int) -> bool:
        if not hwnd:
            return False

        rect = wintypes.RECT()
        if not user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
            return False
        width = int(rect.right - rect.left)
        height = int(rect.bottom - rect.top)
        if width <= 0 or height <= 0:
            return False

        monitor = user32.MonitorFromWindow(
            wintypes.HWND(hwnd), _MONITOR_DEFAULTTONEAREST
        )
        if not monitor:
            return False
        info = core.MONITORINFO()
        info.cbSize = ctypes.sizeof(info)
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return False

        x = int(info.rcWork.right - width)
        y = int(info.rcWork.top)
        return bool(
            user32.SetWindowPos(
                wintypes.HWND(hwnd),
                wintypes.HWND(0),
                x, y, 0, 0,
                _POSITION_FLAGS,
            )
        )

    def pin_when_window_exists(self, pid: int) -> None:
        pid = int(pid)
        marks = tracked_pids(self)
        if pid not in marks:
            return
        if not process_alive(self, pid):
            marks.discard(pid)
            return
        try:
            hwnd = int(self._window_for_pid(pid) or 0)
        except Exception:
            hwnd = 0
        if hwnd:
            remember_window(self, pid, hwnd)
        if hwnd and pin_top_right(hwnd):
            print(
                f"[KVTM DEV] ClientJS pinned top-right | pid={pid} hwnd={hwnd}",
                flush=True,
            )
            return
        self.after(_POLL_MS, lambda target_pid=pid: pin_when_window_exists(self, target_pid))

    def launch_with_top_right_position(self, profile: dict):
        profile_id = str((profile or {}).get("id") or "")
        # If the previous ClientJS window was already destroyed but its process
        # is lingering, clear that stale reference before core decides whether
        # this profile is already open.
        reconcile_client_windows(self)
        result = original_launch(self, profile)
        process = getattr(self, "processes", {}).get(profile_id)
        try:
            pid = int(process.pid) if process is not None and process.poll() is None else 0
        except Exception:
            pid = 0
        if pid:
            lifecycle_hwnds(self).pop(pid, None)
            missing_since(self).pop(pid, None)
            closed_reported(self).discard(pid)
            tracked_pids(self).add(pid)
            self.after(0, lambda target_pid=pid: pin_when_window_exists(self, target_pid))
        return result

    def apply_display_then_restore_position(self, proc) -> None:
        # Preserve the existing display/bridge behavior exactly. Once core has
        # finished its existing resize, re-pin so the right edge remains flush.
        result = original_apply_display(self, proc)
        try:
            pid = int(proc.pid)
        except Exception:
            return result
        marks = tracked_pids(self)
        if pid not in marks:
            return result
        try:
            hwnd = int(self._window_for_pid(pid) or 0)
        except Exception:
            hwnd = 0
        if hwnd:
            remember_window(self, pid, hwnd)
        if hwnd and pin_top_right(hwnd):
            marks.discard(pid)
        return result

    def refresh_with_client_window_lifecycle(self) -> None:
        reconcile_client_windows(self)
        return original_refresh(self)

    app_cls._launch = launch_with_top_right_position
    app_cls._apply_display_to_process = apply_display_then_restore_position
    app_cls.refresh = refresh_with_client_window_lifecycle
    app_cls._clear_stall_window_position_installed = True
    print(
        "[KVTM DEV] ClientJS window position/state READY • top-right work area • "
        "OFF follows closed HWND • hidden HWND stays ONLINE",
        flush=True,
    )
