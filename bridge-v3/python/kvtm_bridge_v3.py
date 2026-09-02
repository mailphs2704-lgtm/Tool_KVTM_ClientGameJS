from __future__ import annotations

import ctypes
from ctypes import wintypes
import math
import struct
import time


_HEADER = struct.Struct("<4s9IQ")
_PROTOCOL_PREFIX = "OK PONG KVTM_BRIDGE_V3"


class BridgeV3Error(RuntimeError):
    pass


class BridgeV3Client:
    """Strict V3 client: no HWND capture fallback and one timing owner."""

    def __init__(self, pid: int) -> None:
        self.pid = int(pid)
        if self.pid <= 0:
            raise ValueError("pid must be positive")
        self.kernel32 = ctypes.windll.kernel32
        self.kernel32.CallNamedPipeW.argtypes = [
            wintypes.LPCWSTR, wintypes.LPVOID, wintypes.DWORD,
            wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
            wintypes.DWORD,
        ]
        self.kernel32.CallNamedPipeW.restype = wintypes.BOOL
        self.kernel32.OpenFileMappingW.argtypes = [
            wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR,
        ]
        self.kernel32.OpenFileMappingW.restype = wintypes.HANDLE
        self.kernel32.MapViewOfFile.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
            wintypes.DWORD, ctypes.c_size_t,
        ]
        self.kernel32.MapViewOfFile.restype = wintypes.LPVOID

    @property
    def pipe_name(self) -> str:
        return rf"\\.\pipe\KVTM-CocosV3-{self.pid}"

    @property
    def mapping_name(self) -> str:
        return rf"Local\KVTM-CaptureV3-{self.pid}"

    def command(self, text: str, timeout_ms: int = 3000) -> str:
        payload = (text.rstrip("\n") + "\n").encode("ascii")
        output = ctypes.create_string_buffer(256)
        read = wintypes.DWORD()
        if not self.kernel32.CallNamedPipeW(
            self.pipe_name, ctypes.c_char_p(payload), len(payload), output,
            len(output), ctypes.byref(read), int(timeout_ms),
        ):
            raise ctypes.WinError()
        response = output.raw[:read.value].decode("ascii", "replace").strip()
        if not response.startswith("OK"):
            raise BridgeV3Error(response or "empty bridge response")
        return response

    def verify_protocol(self) -> str:
        response = self.command("PING", 1000)
        if not response.startswith(_PROTOCOL_PREFIX):
            raise BridgeV3Error(f"unexpected protocol: {response}")
        return response

    def touch(self, phase: str, x: float, y: float) -> None:
        name = phase.upper()
        if name not in {"DOWN", "MOVE", "UP"}:
            raise ValueError(f"invalid phase: {phase}")
        if not (0.0 <= x <= 1000.0 and 0.0 <= y <= 1000.0):
            raise ValueError(f"point outside 1000x1000: {(x, y)}")
        self.command(f"{name} {x:.3f} {y:.3f}", 1000)

    @staticmethod
    def interpolate(points, max_step_px: float = 8.0) -> list[tuple[float, float]]:
        source = [(float(x), float(y)) for x, y in points]
        if len(source) < 2:
            raise ValueError("gesture requires at least two points")
        result = [source[0]]
        for start, end in zip(source, source[1:]):
            distance = math.hypot(end[0] - start[0], end[1] - start[1])
            steps = max(1, int(math.ceil(distance / max(1.0, max_step_px))))
            for index in range(1, steps + 1):
                ratio = index / steps
                result.append((
                    start[0] + (end[0] - start[0]) * ratio,
                    start[1] + (end[1] - start[1]) * ratio,
                ))
        return result

    def swipe(self, points, duration_s: float, max_step_px: float = 8.0) -> dict:
        """Replay one gesture against absolute deadlines.

        duration_s is the total gesture duration, never duration per segment.
        Pipe overhead is included instead of being added after every point.
        """
        path = self.interpolate(points, max_step_px=max_step_px)
        duration = max(0.02, float(duration_s))
        started = time.perf_counter()
        self.touch("DOWN", *path[0])
        try:
            moves = path[1:]
            for index, point in enumerate(moves, start=1):
                deadline = started + duration * index / len(moves)
                remaining = deadline - time.perf_counter()
                if remaining > 0:
                    time.sleep(remaining)
                self.touch("MOVE", *point)
            self.touch("UP", *path[-1])
        except Exception:
            try:
                self.touch("UP", *path[-1])
            except Exception:
                pass
            raise
        actual = time.perf_counter() - started
        return {
            "requested_seconds": duration,
            "actual_seconds": actual,
            "point_count": len(path),
            "timing_error_ms": (actual - duration) * 1000.0,
        }

    def capture_bgra(self) -> tuple[bytes, int, int, int]:
        response = self.command("CAPTURE", 3000)
        parts = response.split()
        if len(parts) != 6 or parts[:2] != ["OK", "FRAME"]:
            raise BridgeV3Error(f"invalid capture response: {response}")
        expected_frame, expected_width, expected_height, expected_stride = map(
            int, parts[2:]
        )
        handle = self.kernel32.OpenFileMappingW(0x0004, False, self.mapping_name)
        if not handle:
            raise ctypes.WinError()
        view = None
        try:
            view = self.kernel32.MapViewOfFile(handle, 0x0004, 0, 0, 0)
            if not view:
                raise ctypes.WinError()
            values = _HEADER.unpack(ctypes.string_at(view, _HEADER.size))
            (
                magic, version, header_size, width, height, stride,
                pixel_format, buffer_size, frame_id, status, _timestamp,
            ) = values
            if magic != b"KCAP" or version != 3 or header_size < _HEADER.size:
                raise BridgeV3Error("invalid KCAP v3 header")
            if status != 2 or frame_id != expected_frame:
                raise BridgeV3Error("unstable KCAP v3 frame")
            if (width, height, stride) != (
                expected_width, expected_height, expected_stride
            ):
                raise BridgeV3Error("KCAP v3 dimensions do not match")
            if pixel_format != 2 or stride != width * 4:
                raise BridgeV3Error("KCAP v3 must be top-down BGRA8")
            if buffer_size != stride * height or buffer_size > 64 * 1024 * 1024:
                raise BridgeV3Error("invalid KCAP v3 buffer size")
            raw = ctypes.string_at(int(view) + header_size, buffer_size)
            return raw, width, height, frame_id
        finally:
            if view:
                self.kernel32.UnmapViewOfFile(view)
            self.kernel32.CloseHandle(handle)
