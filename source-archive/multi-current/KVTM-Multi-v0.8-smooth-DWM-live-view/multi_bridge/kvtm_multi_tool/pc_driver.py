from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import struct
import threading
import time


if os.name == "nt":
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32


_INPUT_LOCK = threading.RLock()


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


def find_window(pid: int) -> int | None:
    found: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _lparam):
        window_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        if window_pid.value == int(pid) and user32.IsWindowVisible(hwnd):
            rect = wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(rect))
            if rect.right > 100 and rect.bottom > 100:
                found.append(hwnd)
                return False
        return True

    user32.EnumWindows(callback_type(callback), 0)
    return found[0] if found else None


def client_size(hwnd: int) -> tuple[int, int]:
    rect = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        raise ctypes.WinError()
    return rect.right - rect.left, rect.bottom - rect.top


def capture_bgra(hwnd: int) -> tuple[bytes, int, int]:
    """Capture only the client area, including when another window overlaps it."""
    width, height = client_size(hwnd)
    if width <= 0 or height <= 0:
        raise RuntimeError("Cửa sổ game không có vùng hiển thị")
    window_dc = user32.GetDC(hwnd)
    memory_dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    old = gdi32.SelectObject(memory_dc, bitmap)
    try:
        # PW_CLIENTONLY | PW_RENDERFULLCONTENT. Fall back to BitBlt if needed.
        ok = user32.PrintWindow(hwnd, memory_dc, 0x00000003)
        if not ok:
            gdi32.BitBlt(memory_dc, 0, 0, width, height, window_dc, 0, 0, 0x00CC0020)
        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = 0
        size = width * height * 4
        buffer = ctypes.create_string_buffer(size)
        rows = gdi32.GetDIBits(memory_dc, bitmap, 0, height, buffer, ctypes.byref(info), 0)
        if rows != height:
            raise ctypes.WinError()
        return buffer.raw, width, height
    finally:
        gdi32.SelectObject(memory_dc, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(hwnd, window_dc)


def save_bgra_bmp(raw: bytes, width: int, height: int, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    pixels = b"".join(
        raw[row * width * 4:(row + 1) * width * 4]
        for row in range(height - 1, -1, -1)
    )
    pixel_offset = 14 + 40
    file_size = pixel_offset + len(pixels)
    file_header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, pixel_offset)
    dib_header = struct.pack(
        "<IiiHHIIiiII", 40, width, height, 1, 32, 0,
        len(pixels), 2835, 2835, 0, 0,
    )
    destination.write_bytes(file_header + dib_header + pixels)


def draw_swipe_bgra(raw: bytes, width: int, height: int,
                     start: tuple[int, int], end: tuple[int, int]) -> bytes:
    """Draw an exact high-contrast swipe overlay without image dependencies."""
    data = bytearray(raw)

    def pixel(x: int, y: int, color=(0, 0, 255, 255)) -> None:
        if 0 <= x < width and 0 <= y < height:
            i = (y * width + x) * 4
            data[i:i + 4] = bytes(color)  # BGRA

    def disc(cx: int, cy: int, radius: int, color) -> None:
        rr = radius * radius
        for yy in range(cy - radius, cy + radius + 1):
            for xx in range(cx - radius, cx + radius + 1):
                if (xx - cx) ** 2 + (yy - cy) ** 2 <= rr:
                    pixel(xx, yy, color)

    x1, y1 = start
    x2, y2 = end
    steps = max(abs(x2 - x1), abs(y2 - y1), 1)
    for n in range(steps + 1):
        x = round(x1 + (x2 - x1) * n / steps)
        y = round(y1 + (y2 - y1) * n / steps)
        disc(x, y, 3, (0, 0, 255, 255))
    disc(x1, y1, 13, (0, 220, 0, 255))       # green start
    disc(x2, y2, 13, (0, 0, 255, 255))       # red end
    # Arrow head pointing at the end.
    direction = 1 if y2 >= y1 else -1
    for delta in range(0, 30):
        spread = delta // 2
        yy = y2 - direction * delta
        for xx in range(x2 - spread, x2 + spread + 1):
            pixel(xx, yy, (0, 0, 255, 255))
    return bytes(data)


class TouchProxy:
    def __init__(self, driver: "PCDriver") -> None:
        self.driver = driver

    def down(self, x: int, y: int):
        self.driver._mouse(0x0201, x, y, 0x0001)
        return self

    def move(self, x: int, y: int):
        self.driver._mouse(0x0200, x, y, 0x0001)
        return self

    def up(self, x: int, y: int):
        self.driver._mouse(0x0202, x, y, 0)
        return self


class PCDriver:
    """uiautomator2-compatible subset backed by one GameClientJS window."""

    def __init__(self, pid: int, reference_size: tuple[int, int] = (1000, 1000)) -> None:
        self.pid = int(pid)
        self.reference_size = reference_size
        self.touch = TouchProxy(self)
        self._process = None
        self._dev = self

    @property
    def hwnd(self) -> int:
        hwnd = find_window(self.pid)
        if not hwnd:
            raise RuntimeError(f"Không tìm thấy cửa sổ GameClientJS PID {self.pid}")
        return hwnd

    @property
    def info(self) -> dict:
        width, height = client_size(self.hwnd)
        return {"displayWidth": width, "displayHeight": height, "pid": self.pid, "platform": "win32"}

    def _xy(self, x: float, y: float) -> tuple[int, int]:
        width, height = client_size(self.hwnd)
        ref_w, ref_h = self.reference_size
        return round(float(x) * width / ref_w), round(float(y) * height / ref_h)

    def _mouse(self, message: int, x: float, y: float, buttons: int = 0) -> None:
        px, py = self._xy(x, y)
        lparam = (py << 16) | (px & 0xFFFF)
        user32.PostMessageW(self.hwnd, message, buttons, lparam)

    def click(self, x: float, y: float) -> None:
        """Send a real foreground mouse click; Cocos ignores synthetic PostMessage clicks."""
        with _INPUT_LOCK:
            hwnd = self.hwnd
            px, py = self._xy(x, y)
            point = wintypes.POINT(px, py)
            if not user32.ClientToScreen(hwnd, ctypes.byref(point)):
                raise ctypes.WinError()
            old_cursor = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(old_cursor))
            old_foreground = user32.GetForegroundWindow()
            was_minimized = bool(user32.IsIconic(hwnd))
            try:
                if was_minimized:
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    time.sleep(0.12)
                    # Client coordinates may change after restore.
                    px, py = self._xy(x, y)
                    point = wintypes.POINT(px, py)
                    user32.ClientToScreen(hwnd, ctypes.byref(point))
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
                time.sleep(0.045)
                user32.SetCursorPos(point.x, point.y)
                user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
                time.sleep(0.055)
                user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP
                time.sleep(0.055)
            finally:
                user32.SetCursorPos(old_cursor.x, old_cursor.y)
                if old_foreground and old_foreground != hwnd:
                    user32.SetForegroundWindow(old_foreground)

    def swipe(self, x1: float, y1: float, x2: float, y2: float, duration: float = 0.3) -> None:
        steps = max(4, min(40, int(float(duration) * 50)))
        self._mouse(0x0201, x1, y1, 0x0001)
        for step in range(1, steps + 1):
            ratio = step / steps
            self._mouse(0x0200, x1 + (x2 - x1) * ratio, y1 + (y2 - y1) * ratio, 0x0001)
            time.sleep(float(duration) / steps)
        self._mouse(0x0202, x2, y2, 0)

    def press(self, key: str) -> None:
        vk = {"back": 0x1B, "home": 0x24, "enter": 0x0D}.get(str(key).lower())
        if vk is None:
            raise ValueError(f"Phím chưa hỗ trợ: {key}")
        user32.PostMessageW(self.hwnd, 0x0100, vk, 0)
        user32.PostMessageW(self.hwnd, 0x0101, vk, 0)

    def screenshot(self, format: str | None = None):
        raw, width, height = capture_bgra(self.hwnd)
        if format == "opencv":
            import numpy as np
            import cv2
            frame = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 4))[:, :, :3].copy()
            ref_w, ref_h = self.reference_size
            if (width, height) != (ref_w, ref_h):
                frame = cv2.resize(frame, (ref_w, ref_h), interpolation=cv2.INTER_AREA)
            return frame
        from PIL import Image
        image = Image.frombuffer("RGBA", (width, height), raw, "raw", "BGRA", 0, 1).convert("RGB")
        if image.size != self.reference_size:
            image = image.resize(self.reference_size, Image.Resampling.LANCZOS)
        return image

    def swipe_four_floors(self, duration: float = 1.0) -> None:
        """Original LDPlayer goUp(4), corrected to its real drag direction."""
        self.swipe(387, 918, 387, 69, duration=duration)

    def app_current(self) -> dict:
        return {"package": "vn.kvtm.js", "activity": "GameClientJS", "pid": self.pid}

    def app_start(self, _package: str, **_kwargs) -> int:
        return self.pid

    def app_stop(self, _package: str) -> None:
        user32.PostMessageW(self.hwnd, 0x0010, 0, 0)

    def shell(self, command: str):
        if "force-stop" in command:
            self.app_stop("vn.kvtm.js")
        return ""

    def disconnect(self) -> None:
        return None


def save_diagnostic(pid: int, destination: Path) -> dict:
    driver = PCDriver(pid)
    raw, width, height = capture_bgra(driver.hwnd)
    save_bgra_bmp(raw, width, height, destination)
    return {**driver.info, "file": str(destination)}


def save_four_floor_swipe_preview(pid: int, destination: Path) -> dict:
    """Preview the original LDPlayer goUp(4) swipe on a 1000x1000 client."""
    driver = PCDriver(pid, reference_size=(1000, 1000))
    raw, width, height = capture_bgra(driver.hwnd)
    start_ref, end_ref = (387, 918), (387, 69)
    start = driver._xy(*start_ref)
    end = driver._xy(*end_ref)
    marked = draw_swipe_bgra(raw, width, height, start, end)
    save_bgra_bmp(marked, width, height, destination)
    return {**driver.info, "file": str(destination), "start": start, "end": end,
            "reference_start": start_ref, "reference_end": end_ref}
