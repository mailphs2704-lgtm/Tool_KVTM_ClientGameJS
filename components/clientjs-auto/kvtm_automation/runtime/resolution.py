from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import sys
import time


__all__ = [
    "LOGICAL_REFERENCE_SIZE",
    "PRODUCTION_CLIENT_SIZE",
    "disable_legacy_adaptive_matching",
    "ensure_production_client_size",
]

FILE_FUNCTIONS = (
    "Giữ source AUTO ở hệ logical 1000x1000",
    "Đặt riêng ClientJS của worker hiện tại về client-area 500x500 trước Bridge V3",
    "Giữ 500x500 ổn định đủ lâu để thắng callback display cũ của Multi khi client vừa launch",
    "Không di chuyển cửa sổ và không đụng ClientJS/profile khác",
    "Gỡ monkeypatch adaptive_cv cũ trong isolated worker để tránh scale template/frame lần hai",
)

LOGICAL_REFERENCE_SIZE = (1000, 1000)
PRODUCTION_CLIENT_SIZE = (500, 500)


def disable_legacy_adaptive_matching() -> bool:
    """Restore native ``cv2.matchTemplate`` inside the isolated clean worker.

    The legacy AUTO PRO launcher installs a global adaptive_cv monkeypatch which
    downscales both image and template. Clean VisionEngine now owns explicit
    logical->frame scaling, so keeping that monkeypatch would scale the already
    adapted 500x500 matcher a second time and throw away image detail.

    Return True only when an installed legacy wrapper was actually removed.
    """
    module = sys.modules.get("adaptive_cv")
    if module is None:
        return False
    original = getattr(module, "_ORIGINAL", None)
    installed = bool(getattr(module, "_INSTALLED", False))
    if not installed or original is None:
        return False

    import cv2

    cv2.matchTemplate = original
    try:
        module._INSTALLED = False
        module._ORIGINAL = None
    except Exception:
        pass
    return True


def _find_window(pid: int) -> int | None:
    if os.name != "nt":
        return None
    user32 = ctypes.windll.user32
    found: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
    )

    def callback(hwnd, _lparam):
        window_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        if window_pid.value != int(pid) or not user32.IsWindowVisible(hwnd):
            return True
        rect = wintypes.RECT()
        if user32.GetClientRect(hwnd, ctypes.byref(rect)):
            width = int(rect.right - rect.left)
            height = int(rect.bottom - rect.top)
            if width > 100 and height > 100:
                found.append(int(hwnd))
                return False
        return True

    user32.EnumWindows(callback_type(callback), 0)
    return found[0] if found else None


def _client_size(hwnd: int) -> tuple[int, int]:
    rect = wintypes.RECT()
    if not ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect)):
        raise ctypes.WinError()
    return int(rect.right - rect.left), int(rect.bottom - rect.top)


def _resize_client(hwnd: int, width: int, height: int) -> None:
    """Resize drawable client area without changing its desktop position."""
    user32 = ctypes.windll.user32
    rect = wintypes.RECT(0, 0, int(width), int(height))
    style = user32.GetWindowLongW(hwnd, -16)
    ex_style = user32.GetWindowLongW(hwnd, -20)

    adjusted = False
    adjust_for_dpi = getattr(user32, "AdjustWindowRectExForDpi", None)
    if adjust_for_dpi:
        dpi = user32.GetDpiForWindow(hwnd)
        adjusted = bool(
            adjust_for_dpi(
                ctypes.byref(rect), style, False, ex_style, dpi
            )
        )
    if not adjusted:
        if not user32.AdjustWindowRectEx(
            ctypes.byref(rect), style, False, ex_style
        ):
            raise ctypes.WinError()

    outer_width = int(rect.right - rect.left)
    outer_height = int(rect.bottom - rect.top)
    # SWP_NOMOVE | SWP_NOZORDER | SWP_SHOWWINDOW. Only this PID's hwnd is used.
    if not user32.SetWindowPos(
        hwnd,
        0,
        0,
        0,
        outer_width,
        outer_height,
        0x0002 | 0x0004 | 0x0040,
    ):
        raise ctypes.WinError()


def ensure_production_client_size(
    pid: int,
    *,
    target: tuple[int, int] = PRODUCTION_CLIENT_SIZE,
    timeout: float = 20.0,
    stable_seconds: float = 2.0,
) -> tuple[int, int]:
    """Make one selected ClientJS stay at production 500x500 before automation.

    Multi's generic launcher can have a delayed display callback roughly one
    second after process start. A one-shot resize in the worker could therefore
    be overwritten back to an old saved size. This helper keeps observing only
    this PID until the target client area remains stable for ``stable_seconds``.

    It is intentionally called before Bridge V3 construction, so vision caches
    and CAPTURE3 never begin at one size and switch resolution mid-run.
    """
    if os.name != "nt":
        raise RuntimeError("AUTO MULTI DEV production resolution chỉ hỗ trợ Windows")

    width, height = map(int, target)
    if width < 200 or height < 200:
        raise ValueError("Production ClientJS size quá nhỏ")

    deadline = time.monotonic() + max(1.0, float(timeout))
    stable_since: float | None = None
    last_size: tuple[int, int] | None = None
    resize_count = 0

    while time.monotonic() < deadline:
        hwnd = _find_window(int(pid))
        if hwnd is None:
            stable_since = None
            time.sleep(0.10)
            continue

        current = _client_size(hwnd)
        last_size = current
        if current != (width, height):
            _resize_client(hwnd, width, height)
            resize_count += 1
            stable_since = None
            time.sleep(0.12)
            continue

        now = time.monotonic()
        if stable_since is None:
            stable_since = now
        if now - stable_since >= max(0.25, float(stable_seconds)):
            # Final fresh measurement after the stability window. This catches a
            # delayed parent callback landing at the very end of the interval.
            final_size = _client_size(hwnd)
            if final_size == (width, height):
                return final_size
            last_size = final_size
            stable_since = None
        time.sleep(0.10)

    raise RuntimeError(
        "Không khóa được ClientJS production size "
        f"{width}x{height} cho PID {int(pid)} sau {float(timeout):.1f}s; "
        f"last_size={last_size}, resize_count={resize_count}"
    )
