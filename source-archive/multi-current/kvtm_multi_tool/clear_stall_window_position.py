from __future__ import annotations

import ctypes
from ctypes import wintypes


_MONITOR_DEFAULTTONEAREST = 0x00000002
_SWP_NOSIZE = 0x0001
_SWP_NOZORDER = 0x0004
_SWP_NOACTIVATE = 0x0010
_POSITION_FLAGS = _SWP_NOSIZE | _SWP_NOZORDER | _SWP_NOACTIVATE
_POLL_MS = 50


def install_clear_stall_window_position(app_cls, core) -> None:
    """Pin every newly launched ClientJS window to the work-area top-right."""
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

    original_launch = app_cls._launch
    original_apply_display = app_cls._apply_display_to_process

    def tracked_pids(self) -> set[int]:
        value = getattr(self, "_client_top_right_position_pids", None)
        if not isinstance(value, set):
            value = set()
            self._client_top_right_position_pids = value
        return value

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
        if hwnd and pin_top_right(hwnd):
            print(
                f"[KVTM DEV] ClientJS pinned top-right | pid={pid} hwnd={hwnd}",
                flush=True,
            )
            return
        self.after(_POLL_MS, lambda target_pid=pid: pin_when_window_exists(self, target_pid))

    def launch_with_top_right_position(self, profile: dict):
        profile_id = str((profile or {}).get("id") or "")
        result = original_launch(self, profile)
        process = getattr(self, "processes", {}).get(profile_id)
        try:
            pid = int(process.pid) if process is not None and process.poll() is None else 0
        except Exception:
            pid = 0
        if pid:
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
        if hwnd and pin_top_right(hwnd):
            marks.discard(pid)
        return result

    app_cls._launch = launch_with_top_right_position
    app_cls._apply_display_to_process = apply_display_then_restore_position
    app_cls._clear_stall_window_position_installed = True
    print(
        "[KVTM DEV] ClientJS window position READY • top-right work area • "
        "size/z-order/focus unchanged",
        flush=True,
    )
