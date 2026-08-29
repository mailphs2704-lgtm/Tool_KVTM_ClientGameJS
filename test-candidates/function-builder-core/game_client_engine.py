from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
import struct
import time
import math


LOGICAL_WIDTH = 1000
LOGICAL_HEIGHT = 1000


if not hasattr(ctypes, "windll"):
    raise RuntimeError("Engine Core chi ho tro Windows")

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

kernel32.WaitNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
kernel32.WaitNamedPipeW.restype = wintypes.BOOL
kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
]
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.WriteFile.argtypes = [
    wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
]
kernel32.WriteFile.restype = wintypes.BOOL
kernel32.ReadFile.argtypes = [
    wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
]
kernel32.ReadFile.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL


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
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


@dataclass(frozen=True)
class ClientGeometry:
    width: int
    height: int

    def logical_to_client(self, x: float, y: float) -> tuple[int, int]:
        if not 0 <= x <= LOGICAL_WIDTH or not 0 <= y <= LOGICAL_HEIGHT:
            raise ValueError(f"Toa do ngoai vung 1000x1000: {(x, y)}")
        return (
            round(float(x) * self.width / LOGICAL_WIDTH),
            round(float(y) * self.height / LOGICAL_HEIGHT),
        )


def find_game_window(pid: int) -> int:
    matches: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _lparam):
        window_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        if window_pid.value != int(pid) or not user32.IsWindowVisible(hwnd):
            return True
        rect = wintypes.RECT()
        if user32.GetClientRect(hwnd, ctypes.byref(rect)) and rect.right > 100 and rect.bottom > 100:
            matches.append(int(hwnd))
            return False
        return True

    user32.EnumWindows(callback_type(callback), 0)
    if not matches:
        raise RuntimeError(f"Khong tim thay cua so GameClientJS PID {pid}")
    return matches[0]


def get_geometry(hwnd: int) -> ClientGeometry:
    rect = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        raise ctypes.WinError()
    width, height = rect.right - rect.left, rect.bottom - rect.top
    if width <= 0 or height <= 0:
        raise RuntimeError("Client game khong co vung hien thi")
    return ClientGeometry(width, height)


def capture_bgra(hwnd: int) -> tuple[bytes, ClientGeometry]:
    geometry = get_geometry(hwnd)
    window_dc = user32.GetDC(hwnd)
    if not window_dc:
        raise ctypes.WinError()
    memory_dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, geometry.width, geometry.height)
    old = gdi32.SelectObject(memory_dc, bitmap)
    try:
        ok = user32.PrintWindow(hwnd, memory_dc, 0x00000003)
        if not ok:
            ok = gdi32.BitBlt(
                memory_dc, 0, 0, geometry.width, geometry.height,
                window_dc, 0, 0, 0x00CC0020,
            )
        if not ok:
            raise ctypes.WinError()

        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = geometry.width
        info.bmiHeader.biHeight = -geometry.height
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        buffer = ctypes.create_string_buffer(geometry.width * geometry.height * 4)
        rows = gdi32.GetDIBits(
            memory_dc, bitmap, 0, geometry.height,
            buffer, ctypes.byref(info), 0,
        )
        if rows != geometry.height:
            raise ctypes.WinError()
        return buffer.raw, geometry
    finally:
        gdi32.SelectObject(memory_dc, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(hwnd, window_dc)


def save_bmp(raw: bytes, geometry: ClientGeometry, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    stride = geometry.width * 4
    pixels = b"".join(
        raw[row * stride:(row + 1) * stride]
        for row in range(geometry.height - 1, -1, -1)
    )
    offset = 54
    file_header = struct.pack("<2sIHHI", b"BM", offset + len(pixels), 0, 0, offset)
    dib_header = struct.pack(
        "<IiiHHIIiiII", 40, geometry.width, geometry.height,
        1, 32, 0, len(pixels), 2835, 2835, 0, 0,
    )
    destination.write_bytes(file_header + dib_header + pixels)


class BridgeClient:
    def __init__(self, pid: int, timeout_ms: int = 2000) -> None:
        self.pid = int(pid)
        self.timeout_ms = int(timeout_ms)
        self.pipe_name = rf"\\.\pipe\KVTM-Cocos-{self.pid}"

    def request(self, command: str) -> str:
        if not kernel32.WaitNamedPipeW(self.pipe_name, self.timeout_ms):
            raise RuntimeError(
                f"Bridge PID {self.pid} chua san sang. Hay nap kvtm_bridge.dll truoc."
            )
        handle = kernel32.CreateFileW(
            self.pipe_name,
            0xC0000000,
            0,
            None,
            3,
            0,
            None,
        )
        if handle == wintypes.HANDLE(-1).value:
            raise ctypes.WinError()
        try:
            payload = (command.rstrip("\r\n") + "\n").encode("ascii")
            written = wintypes.DWORD()
            if not kernel32.WriteFile(handle, payload, len(payload), ctypes.byref(written), None):
                raise ctypes.WinError()
            output = ctypes.create_string_buffer(128)
            read = wintypes.DWORD()
            if not kernel32.ReadFile(handle, output, len(output) - 1, ctypes.byref(read), None):
                raise ctypes.WinError()
            response = output.raw[:read.value].decode("ascii", errors="replace").strip()
            if not response.startswith("OK"):
                raise RuntimeError(f"Bridge tra loi loi: {response}")
            return response
        finally:
            kernel32.CloseHandle(handle)

    def ping(self) -> None:
        self.request("PING")

    def touch(self, phase: str, x: float, y: float) -> None:
        phase = phase.upper()
        if phase not in {"DOWN", "MOVE", "UP"}:
            raise ValueError(f"Touch phase khong hop le: {phase}")
        if not 0 <= x <= LOGICAL_WIDTH or not 0 <= y <= LOGICAL_HEIGHT:
            raise ValueError(f"Toa do ngoai vung 1000x1000: {(x, y)}")
        self.request(f"{phase} {float(x):.3f} {float(y):.3f}")

    def swipe_points(self, points: list[tuple[float, float]], duration: float) -> None:
        if len(points) < 2:
            raise ValueError("Swipe can it nhat hai diem")
        logical = [(float(x), float(y)) for x, y in points]
        lengths = [
            math.hypot(b[0] - a[0], b[1] - a[1])
            for a, b in zip(logical, logical[1:])
        ]
        total_length = sum(lengths)
        if total_length < 1.0:
            raise ValueError("Duong swipe qua ngan")

        # GameClientJS bo qua MOVE neu hai moc cach nhau qua xa. Noi suy theo
        # khoang cach, nhung van giu nguyen moi waypoint nguoi dung da ve.
        duration = max(0.20, float(duration))
        sample_count = max(
            len(logical) - 1,
            int(math.ceil(total_length / 8.0)),
            int(math.ceil(duration * 45.0)),
        )
        sample_count = min(sample_count, 600)
        samples = [logical[0]]
        for index in range(1, sample_count + 1):
            target = total_length * index / sample_count
            travelled = 0.0
            for segment, length in enumerate(lengths):
                if target <= travelled + length or segment == len(lengths) - 1:
                    ratio = 1.0 if length == 0 else (target - travelled) / length
                    ratio = max(0.0, min(1.0, ratio))
                    start, end = logical[segment], logical[segment + 1]
                    samples.append((
                        start[0] + (end[0] - start[0]) * ratio,
                        start[1] + (end[1] - start[1]) * ratio,
                    ))
                    break
                travelled += length

        started = time.monotonic()
        self.touch("DOWN", *samples[0])
        try:
            for index, point in enumerate(samples[1:], 1):
                deadline = started + duration * index / (len(samples) - 1)
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    time.sleep(remaining)
                self.touch("MOVE", *point)
            self.touch("UP", *samples[-1])
        except Exception:
            try:
                self.touch("UP", *samples[-1])
            except Exception:
                pass
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description="KVTM Engine Core candidate test")
    parser.add_argument("pid", type=int, help="PID GameClientJS")
    parser.add_argument("--output", default="engine-test-capture.bmp")
    parser.add_argument("--swipe", action="store_true", help="Chay swipe 4 tang co chu y")
    parser.add_argument("--duration", type=float, default=2.0)
    args = parser.parse_args()

    hwnd = find_game_window(args.pid)
    geometry = get_geometry(hwnd)
    print(f"WINDOW OK hwnd={hwnd} client={geometry.width}x{geometry.height}")
    print(f"MAP center={geometry.logical_to_client(500, 500)}")

    bridge = BridgeClient(args.pid)
    bridge.ping()
    print("BRIDGE OK")

    raw, captured_geometry = capture_bgra(hwnd)
    destination = Path(args.output).resolve()
    save_bmp(raw, captured_geometry, destination)
    print(f"CAPTURE OK {destination}")

    if args.swipe:
        points = [(387.0, y) for y in range(918, 68, -8)]
        if points[-1] != (387.0, 69.0):
            points.append((387.0, 69.0))
        bridge.swipe_points(points, args.duration)
        print(f"SWIPE OK duration={args.duration:.2f}s points={len(points)}")
    else:
        print("SWIPE SKIPPED (them --swipe neu muon test)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
