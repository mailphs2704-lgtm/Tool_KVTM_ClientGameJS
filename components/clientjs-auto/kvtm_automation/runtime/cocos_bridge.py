from __future__ import annotations

import ctypes
from ctypes import wintypes
import math
import os
from pathlib import Path
import struct
import subprocess
import threading
import time
from typing import Callable

from . import window_capture
from .profile_process import ProfileProcessResolver


_GESTURE_LOCK = threading.RLock()


class _TouchProxy:
    """uiautomator2-style touch facade backed by the Cocos DLL bridge."""

    def __init__(self, driver: "CocosBridgeDriver") -> None:
        self.driver = driver
        self._locked = False

    def down(self, x: float, y: float):
        _GESTURE_LOCK.acquire()
        self._locked = True
        try:
            self.driver._touch_event("down", x, y)
        except Exception:
            self._locked = False
            _GESTURE_LOCK.release()
            raise
        return self

    def move(self, x: float, y: float):
        self.driver._touch_event("move", x, y)
        return self

    def up(self, x: float, y: float):
        try:
            self.driver._touch_event("up", x, y)
        finally:
            if self._locked:
                self._locked = False
                _GESTURE_LOCK.release()
        return self


class CocosBridgeDriver:
    """Clean ClientJS driver backed by ``kvtm_bridge.dll``.

    Touch input always travels through the Cocos named-pipe bridge. Capture is
    capability-driven: bridge builds advertising ``CAPTURE1`` use KCAP shared
    memory; older bridge builds (the same ones the working AUTO supports) use a
    clean Win32 ``PrintWindow`` capture fallback while touches remain in-DLL.

    No AUTO PRO business bytecode and no legacy ``engine_driver.py`` are used.
    """

    HEADER_FORMAT = "<4s9IQ"
    CAPTURE_MAGIC = b"KCAP"
    CAPTURE_VERSION = 1
    PIXEL_BGRA8_BOTTOM_UP = 1
    PIXEL_BGRA8_TOP_DOWN = 2

    def __init__(
        self,
        pid: int,
        auto_root: Path,
        *,
        reference_size: tuple[int, int] = (1000, 1000),
        logger: Callable[[str], None] | None = None,
        profile_id: str | None = None,
        profile_file: Path | None = None,
    ) -> None:
        if os.name != "nt":
            raise RuntimeError("Cocos DLL bridge chỉ hỗ trợ Windows")
        self.pid = int(pid)
        self.auto_root = Path(auto_root).resolve()
        self.reference_size = tuple(map(int, reference_size))
        self.logger = logger
        self.profile_id = str(profile_id or "")
        self.profile_resolver = (
            ProfileProcessResolver(self.profile_id, profile_file, logger=logger)
            if self.profile_id and profile_file is not None else None
        )
        self._rebinding = False
        self.bin_root = self.auto_root / "bin"
        self.loader_path = self.bin_root / "kvtm_loader.exe"
        self.bridge_path = self.bin_root / "kvtm_bridge.dll"
        self.touch = _TouchProxy(self)
        self.ping_response = ""
        self.shared_capture_supported = False
        self._capture_mode_logged = False
        self._configure_kernel32()
        self.ensure_bridge()

    def _log(self, message: str) -> None:
        if self.logger is not None:
            try:
                self.logger(str(message))
            except Exception:
                pass

    @property
    def pipe_name(self) -> str:
        return rf"\\.\pipe\KVTM-Cocos-{self.pid}"

    @property
    def capture_mapping_name(self) -> str:
        return rf"Local\KVTM-Capture-{self.pid}"

    def _configure_kernel32(self) -> None:
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
        kernel32.OpenFileMappingW.argtypes = [
            wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR
        ]
        kernel32.OpenFileMappingW.restype = wintypes.HANDLE
        kernel32.MapViewOfFile.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_size_t,
        ]
        kernel32.MapViewOfFile.restype = wintypes.LPVOID
        kernel32.UnmapViewOfFile.argtypes = [wintypes.LPCVOID]
        kernel32.UnmapViewOfFile.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        self.kernel32 = kernel32

    def _refresh_profile_pid(self) -> bool:
        """Rebind Bridge transport to the replacement PID of this exact profile."""
        if self._rebinding or self.profile_resolver is None:
            return False
        if self.profile_resolver.is_alive(self.pid):
            return False
        replacement = self.profile_resolver.current_pid()
        if not replacement:
            raise RuntimeError(
                f"Profile {self.profile_id} chưa có ClientJS thay thế sau restart"
            )
        old_pid = self.pid
        self.pid = int(replacement)
        self.ping_response = ""
        self.shared_capture_supported = False
        self._capture_mode_logged = False
        self._rebinding = True
        try:
            self.ensure_bridge()
        finally:
            self._rebinding = False
        self._log(
            f"ClientJS profile rebind READY: old_pid={old_pid} new_pid={self.pid}"
        )
        return True

    def _pipe(self, command: str, timeout_ms: int = 3000) -> str:
        if not self._rebinding:
            self._refresh_profile_pid()
        payload = command.encode("ascii")
        deadline = time.monotonic() + max(0.15, timeout_ms / 1000.0)
        last_error = 2
        while time.monotonic() < deadline:
            output = ctypes.create_string_buffer(256)
            read = wintypes.DWORD()
            remaining_ms = max(
                25,
                min(250, int(max(0.025, deadline - time.monotonic()) * 1000)),
            )
            ok = self.kernel32.CallNamedPipeW(
                self.pipe_name,
                ctypes.c_char_p(payload),
                len(payload),
                output,
                len(output),
                ctypes.byref(read),
                remaining_ms,
            )
            if ok:
                response = output.raw[: read.value].decode("ascii", "replace").strip()
                if not response.startswith("OK"):
                    raise RuntimeError(f"DLL bridge trả về: {response}")
                return response
            last_error = int(self.kernel32.GetLastError())
            if last_error not in (2, 231):  # FILE_NOT_FOUND / PIPE_BUSY
                raise ctypes.WinError(last_error)
            time.sleep(0.01)
        raise ctypes.WinError(last_error)

    def _remember_ping(self, response: str) -> str:
        self.ping_response = str(response)
        self.shared_capture_supported = "CAPTURE1" in self.ping_response.upper().split()
        return self.ping_response

    def ping(self, timeout_ms: int = 300) -> str:
        return self._remember_ping(self._pipe("PING\n", timeout_ms))

    def ensure_bridge(self) -> None:
        self._log(f"DLL bridge: PID={self.pid}")
        self._log(f"DLL bridge: loader={self.loader_path}")
        self._log(f"DLL bridge: dll={self.bridge_path}")
        if not self.loader_path.is_file():
            raise RuntimeError(f"Thiếu bridge loader: {self.loader_path}")
        if not self.bridge_path.is_file():
            raise RuntimeError(f"Thiếu bridge DLL: {self.bridge_path}")

        try:
            response = self.ping(180)
            self._log(f"DLL bridge: PING sẵn sàng -> {response}")
            self._log(
                "DLL bridge: capture capability="
                + ("CAPTURE1" if self.shared_capture_supported else "legacy-window-fallback")
            )
            return
        except Exception as exc:
            self._log(f"DLL bridge: PING chưa sẵn sàng -> {exc}")

        self._log("DLL bridge: đang inject kvtm_bridge.dll")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(
            [str(self.loader_path), str(self.pid), str(self.bridge_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=flags,
            timeout=15,
        )
        if result.returncode:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(
                f"Inject kvtm_bridge.dll thất bại code={result.returncode}: {detail}"
            )
        self._log("DLL bridge: loader trả về thành công, đang chờ named pipe")

        last_error: Exception | None = None
        for attempt in range(1, 61):
            try:
                response = self.ping(180)
                self._log(f"DLL bridge: PING PASS lần {attempt} -> {response}")
                self._log(
                    "DLL bridge: capture capability="
                    + ("CAPTURE1" if self.shared_capture_supported else "legacy-window-fallback")
                )
                return
            except Exception as exc:
                last_error = exc
                time.sleep(0.10)
        raise RuntimeError(
            f"DLL đã inject nhưng named pipe {self.pipe_name} chưa sẵn sàng: {last_error}"
        )

    def _capture_shared_bgra(self) -> tuple[bytes, int, int, int]:
        response = self._pipe("CAPTURE\n", 3000)
        parts = response.split()
        if len(parts) != 6 or parts[:2] != ["OK", "FRAME"]:
            raise RuntimeError(f"Phản hồi CAPTURE không hợp lệ: {response}")
        expected_frame, expected_width, expected_height, expected_stride = map(
            int, parts[2:]
        )
        self._log(
            "DLL bridge: CAPTURE metadata "
            f"frame={expected_frame} size={expected_width}x{expected_height} "
            f"stride={expected_stride}"
        )

        FILE_MAP_READ = 0x0004
        handle = self.kernel32.OpenFileMappingW(
            FILE_MAP_READ, False, self.capture_mapping_name
        )
        if not handle:
            raise ctypes.WinError()
        view = None
        try:
            view = self.kernel32.MapViewOfFile(handle, FILE_MAP_READ, 0, 0, 0)
            if not view:
                raise ctypes.WinError()
            header_size = struct.calcsize(self.HEADER_FORMAT)
            values = struct.unpack(
                self.HEADER_FORMAT, ctypes.string_at(view, header_size)
            )
            (
                magic,
                version,
                mapped_header_size,
                width,
                height,
                stride,
                pixel_format,
                buffer_size,
                frame_id,
                status,
                _timestamp_ms,
            ) = values
            if magic != self.CAPTURE_MAGIC or version != self.CAPTURE_VERSION:
                raise RuntimeError("KCAP header không hợp lệ")
            if mapped_header_size < header_size:
                raise RuntimeError("KCAP header_size quá nhỏ")
            if status != 2 or frame_id != expected_frame:
                raise RuntimeError(
                    f"KCAP frame chưa hoàn tất: status={status}, frame={frame_id}"
                )
            if (width, height, stride) != (
                expected_width,
                expected_height,
                expected_stride,
            ):
                raise RuntimeError("KCAP kích thước không khớp phản hồi pipe")
            if stride != width * 4 or buffer_size != stride * height:
                raise RuntimeError("KCAP stride/buffer_size không hợp lệ")
            if pixel_format not in (
                self.PIXEL_BGRA8_BOTTOM_UP,
                self.PIXEL_BGRA8_TOP_DOWN,
            ):
                raise RuntimeError(f"KCAP pixel_format chưa hỗ trợ: {pixel_format}")
            address = ctypes.cast(view, ctypes.c_void_p).value
            if not address:
                raise RuntimeError("KCAP shared-memory address rỗng")
            raw = ctypes.string_at(address + mapped_header_size, buffer_size)
            return raw, int(width), int(height), int(pixel_format)
        finally:
            if view:
                self.kernel32.UnmapViewOfFile(view)
            self.kernel32.CloseHandle(handle)

    def _shared_screenshot(self, format: str | None = None):
        raw, width, height, pixel_format = self._capture_shared_bgra()
        if format == "opencv":
            import cv2
            import numpy as np

            frame = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 4))[
                :, :, :3
            ].copy()
            if pixel_format == self.PIXEL_BGRA8_BOTTOM_UP:
                frame = frame[::-1].copy()
            if (width, height) != self.reference_size:
                frame = cv2.resize(
                    frame, self.reference_size, interpolation=cv2.INTER_AREA
                )
            return frame

        from PIL import Image

        orientation = -1 if pixel_format == self.PIXEL_BGRA8_BOTTOM_UP else 1
        image = Image.frombuffer(
            "RGBA",
            (width, height),
            raw,
            "raw",
            "BGRA",
            0,
            orientation,
        ).convert("RGB")
        if image.size != self.reference_size:
            image = image.resize(self.reference_size, Image.Resampling.LANCZOS)
        return image

    def screenshot(self, format: str | None = None):
        """Capture using DLL when supported, otherwise mirror working AUTO fallback."""

        if self.shared_capture_supported:
            try:
                if not self._capture_mode_logged:
                    self._log("Capture: dùng DLL shared-memory CAPTURE1")
                    self._capture_mode_logged = True
                return self._shared_screenshot(format=format)
            except Exception as exc:
                self._log(
                    "Capture: DLL CAPTURE1 lỗi; chuyển Win32 fallback như AUTO chính -> "
                    f"{type(exc).__name__}: {exc}"
                )

        if not self._capture_mode_logged:
            self._log(
                "Capture: DLL hiện tại không quảng bá CAPTURE1; "
                "dùng Win32 PrintWindow fallback như AUTO chính"
            )
            self._capture_mode_logged = True
        return window_capture.screenshot(
            self.pid,
            reference_size=self.reference_size,
            format=format,
        )

    def _validate_point(self, x: float, y: float) -> tuple[float, float]:
        x, y = float(x), float(y)
        if not (0.0 <= x <= 1000.0 and 0.0 <= y <= 1000.0):
            raise ValueError(f"Tọa độ ngoài vùng 1000x1000: {(x, y)}")
        return x, y

    def _touch_event(self, phase: str, x: float, y: float) -> None:
        x, y = self._validate_point(x, y)
        name = {"down": "DOWN", "move": "MOVE", "up": "UP"}[phase]
        response = self._pipe(f"{name} {x:.3f} {y:.3f}\n", 1500)
        self._log(f"DLL bridge: {name} ({x:.1f},{y:.1f}) -> {response}")

    def click(self, x: float, y: float) -> None:
        with _GESTURE_LOCK:
            x, y = self._validate_point(x, y)
            self._touch_event("down", x, y)
            time.sleep(0.045)
            self._touch_event("up", x, y)
            time.sleep(0.035)

    def swipe(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        duration: float = 0.3,
    ) -> None:
        start = self._validate_point(x1, y1)
        end = self._validate_point(x2, y2)
        steps = max(4, min(80, int(max(0.08, float(duration)) * 60)))
        with _GESTURE_LOCK:
            self._touch_event("down", *start)
            try:
                for step in range(1, steps + 1):
                    ratio = step / steps
                    point = (
                        start[0] + (end[0] - start[0]) * ratio,
                        start[1] + (end[1] - start[1]) * ratio,
                    )
                    time.sleep(max(0.0, float(duration)) / steps)
                    self._touch_event("move", *point)
                self._touch_event("up", *end)
            except Exception:
                try:
                    self._touch_event("up", *end)
                except Exception:
                    pass
                raise

    def swipe_points(self, points, duration: float = 0.5) -> None:
        path = [self._validate_point(point[0], point[1]) for point in points]
        if len(path) < 2:
            raise ValueError("swipe_points cần ít nhất hai tọa độ")
        replay = [path[0]]
        for start, end in zip(path, path[1:]):
            distance = math.hypot(end[0] - start[0], end[1] - start[1])
            steps = max(1, int(math.ceil(distance / 8.0)))
            for step in range(1, steps + 1):
                ratio = step / steps
                replay.append(
                    (
                        start[0] + (end[0] - start[0]) * ratio,
                        start[1] + (end[1] - start[1]) * ratio,
                    )
                )
        total = max(0.02, float(duration) * (len(path) - 1))
        interval = total / max(1, len(replay) - 1)
        with _GESTURE_LOCK:
            self._touch_event("down", *replay[0])
            try:
                for point in replay[1:]:
                    time.sleep(interval)
                    self._touch_event("move", *point)
                self._touch_event("up", *replay[-1])
            except Exception:
                try:
                    self._touch_event("up", *replay[-1])
                except Exception:
                    pass
                raise

    @property
    def info(self) -> dict:
        return {
            "displayWidth": self.reference_size[0],
            "displayHeight": self.reference_size[1],
            "pid": self.pid,
            "platform": "clientjs-cocos-dll",
            "pipe": self.pipe_name,
            "ping": self.ping_response,
            "captureMode": (
                "dll-shared-memory"
                if self.shared_capture_supported
                else "win32-fallback"
            ),
        }

    def app_current(self) -> dict:
        return {
            "package": "vn.kvtm.js",
            "activity": "GameClientJS",
            "pid": self.pid,
        }

    def disconnect(self) -> None:
        return None
