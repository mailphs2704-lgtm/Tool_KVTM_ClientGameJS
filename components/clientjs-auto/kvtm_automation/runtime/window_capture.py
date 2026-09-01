from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from typing import Any


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3),
    ]


def _win32() -> tuple[Any, Any]:
    if os.name != "nt":
        raise RuntimeError("Windows capture chỉ hỗ trợ Windows")
    return ctypes.windll.user32, ctypes.windll.gdi32


def find_window(pid: int) -> int:
    """Return the visible GameClientJS top-level window owned by ``pid``."""

    user32, _gdi32 = _win32()
    found: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HWND,
        wintypes.LPARAM,
    )

    def callback(hwnd, _lparam):
        window_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        if window_pid.value != int(pid) or not user32.IsWindowVisible(hwnd):
            return True
        rect = wintypes.RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
            return True
        if rect.right > 100 and rect.bottom > 100:
            found.append(int(hwnd))
            return False
        return True

    user32.EnumWindows(callback_type(callback), 0)
    if not found:
        raise RuntimeError(f"Không tìm thấy cửa sổ GameClientJS PID {int(pid)}")
    return found[0]


def client_size(hwnd: int) -> tuple[int, int]:
    user32, _gdi32 = _win32()
    rect = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        raise ctypes.WinError()
    width = int(rect.right - rect.left)
    height = int(rect.bottom - rect.top)
    if width <= 0 or height <= 0:
        raise RuntimeError("Cửa sổ GameClientJS không có vùng hiển thị")
    return width, height


def capture_bgra(hwnd: int) -> tuple[bytes, int, int]:
    """Capture only the client area using the same Win32 path as AUTO chính.

    ``PrintWindow(PW_CLIENTONLY | PW_RENDERFULLCONTENT)`` is attempted first so
    another desktop window can overlap the game.  ``BitBlt`` is the fallback.
    The returned BGRA buffer is top-down because ``biHeight`` is negative.
    """

    user32, gdi32 = _win32()
    width, height = client_size(hwnd)
    window_dc = user32.GetDC(hwnd)
    if not window_dc:
        raise ctypes.WinError()
    memory_dc = gdi32.CreateCompatibleDC(window_dc)
    if not memory_dc:
        user32.ReleaseDC(hwnd, window_dc)
        raise ctypes.WinError()
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    if not bitmap:
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(hwnd, window_dc)
        raise ctypes.WinError()
    old = gdi32.SelectObject(memory_dc, bitmap)
    try:
        ok = user32.PrintWindow(hwnd, memory_dc, 0x00000003)
        if not ok:
            if not gdi32.BitBlt(
                memory_dc,
                0,
                0,
                width,
                height,
                window_dc,
                0,
                0,
                0x00CC0020,
            ):
                raise ctypes.WinError()

        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = 0
        size = width * height * 4
        buffer = ctypes.create_string_buffer(size)
        rows = gdi32.GetDIBits(
            memory_dc,
            bitmap,
            0,
            height,
            buffer,
            ctypes.byref(info),
            0,
        )
        if int(rows) != height:
            raise ctypes.WinError()
        return buffer.raw, width, height
    finally:
        gdi32.SelectObject(memory_dc, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(hwnd, window_dc)


def screenshot(
    pid: int,
    *,
    reference_size: tuple[int, int] = (1000, 1000),
    format: str | None = None,
):
    """Capture GameClientJS without using legacy AUTO Python modules."""

    hwnd = find_window(int(pid))
    raw, width, height = capture_bgra(hwnd)
    target = tuple(map(int, reference_size))

    if format == "opencv":
        import cv2
        import numpy as np

        frame = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 4))[
            :, :, :3
        ].copy()
        if (width, height) != target:
            frame = cv2.resize(frame, target, interpolation=cv2.INTER_AREA)
        return frame

    from PIL import Image

    image = Image.frombuffer(
        "RGBA",
        (width, height),
        raw,
        "raw",
        "BGRA",
        0,
        1,
    ).convert("RGB")
    if image.size != target:
        image = image.resize(target, Image.Resampling.LANCZOS)
    return image
