from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import json
import math
import os
from pathlib import Path
import subprocess
import struct
import threading
import time

from pc_driver import PCDriver, find_window
from adaptive_cv import set_capture_scale


ROOT = Path(__file__).resolve().parent
BIN = ROOT / "bin"
LOADER = BIN / "kvtm_loader.exe"
BRIDGE = BIN / "kvtm_bridge.dll"
_GESTURE_LOCK = threading.RLock()
PROFILE_FILE = Path(os.environ.get("APPDATA", Path.home())) / "KVTM Multi" / "profiles.json"
SPEED_FILE = Path(os.environ.get("APPDATA", Path.home())) / "KVTM Multi" / "engine_bridge.json"


def load_swipe_speed() -> dict:
    defaults = {"segment_ms": 55, "duration_multiplier": 2.0, "minimum_ms": 300}
    try:
        saved = json.loads(SPEED_FILE.read_text(encoding="utf-8"))
        defaults["segment_ms"] = max(10, min(500, int(saved.get("segment_ms", 55))))
        defaults["duration_multiplier"] = max(
            0.1, min(10.0, float(saved.get("duration_multiplier", 2.0)))
        )
        defaults["minimum_ms"] = max(20, min(5000, int(saved.get("minimum_ms", 300))))
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        pass
    return defaults


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes):
    buffer = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def _unprotect(value: str) -> bytes:
    source, source_buffer = _blob(base64.b64decode(value))
    entropy, entropy_buffer = _blob(b"KVTM-MULTI-v1")
    result = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(source), None, ctypes.byref(entropy), None, None,
        0x01, ctypes.byref(result),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(result.pbData)
        del source_buffer, entropy_buffer


def _split_command_line(command_line: str) -> list[str]:
    count = ctypes.c_int()
    parser = ctypes.windll.shell32.CommandLineToArgvW
    parser.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    parser.restype = ctypes.POINTER(wintypes.LPWSTR)
    argv = parser(command_line, ctypes.byref(count))
    if not argv:
        raise ctypes.WinError()
    try:
        return [argv[index] for index in range(count.value)]
    finally:
        ctypes.windll.kernel32.LocalFree(argv)

if hasattr(ctypes, "windll"):
    kernel32 = ctypes.windll.kernel32
    kernel32.CallNamedPipeW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPVOID, wintypes.DWORD,
        wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.DWORD,
    ]
    kernel32.CallNamedPipeW.restype = wintypes.BOOL
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.OpenFileMappingW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.OpenFileMappingW.restype = wintypes.HANDLE
    kernel32.MapViewOfFile.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t,
    ]
    kernel32.MapViewOfFile.restype = wintypes.LPVOID
    kernel32.UnmapViewOfFile.argtypes = [wintypes.LPCVOID]
    kernel32.UnmapViewOfFile.restype = wintypes.BOOL


class EngineDriver(PCDriver):
    """PCDriver whose coordinates are delivered inside the Cocos engine."""

    def __init__(self, pid: int, reference_size=(1000, 1000)) -> None:
        super().__init__(pid, reference_size=reference_size)
        self._restart_profile = self._resolve_restart_profile(pid)
        self._restart_pending = False
        self._restart_window_rect = None
        self._ensure_bridge()
        self._trace(
            "engine_bridge_connected", pipe=self.pipe_name,
            restart_profile=bool(self._restart_profile),
        )

    def _resolve_restart_profile(self, pid: int):
        """Match the running PID to one DPAPI-protected KVTM Multi profile."""
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            script = (
                f"$p=Get-CimInstance Win32_Process -Filter \"ProcessId={int(pid)}\";"
                "$p|Select-Object ExecutablePath,CommandLine|ConvertTo-Json -Compress"
            )
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, text=True, encoding="utf-8-sig", errors="replace",
                creationflags=flags, timeout=15, check=True,
            )
            running = json.loads(result.stdout or "{}")
            args = _split_command_line(running.get("CommandLine") or "")
            if len(args) < 2:
                return None
            profiles = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
            running_game = os.path.normcase(os.path.abspath(args[1]))
            running_secret = args[2:]
            for profile in profiles:
                secret = json.loads(_unprotect(profile["secret"]).decode("utf-8"))
                game_dir = os.path.normcase(os.path.abspath(profile.get("game_dir") or ""))
                if game_dir == running_game and secret == running_secret:
                    return profile
        except Exception as exc:
            self._trace("restart_profile_error", error=str(exc))
        return None

    def _is_process_alive(self, pid: int) -> bool:
        handle = kernel32.OpenProcess(0x00100000, False, int(pid))  # SYNCHRONIZE
        if not handle:
            return False
        try:
            return kernel32.WaitForSingleObject(handle, 0) == 0x00000102
        finally:
            kernel32.CloseHandle(handle)

    def _close_exact_process(self) -> None:
        old_pid = self.pid
        hwnd = find_window(old_pid)
        if hwnd:
            rect = wintypes.RECT()
            if ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                self._restart_window_rect = (
                    rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top,
                )
            self._trace("pc_restart_close", old_pid=old_pid)
            ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
        for _ in range(60):
            if not self._is_process_alive(old_pid):
                return
            time.sleep(0.10)
        handle = kernel32.OpenProcess(0x0001 | 0x00100000, False, old_pid)
        if handle:
            try:
                kernel32.TerminateProcess(handle, 0)
                kernel32.WaitForSingleObject(handle, 3000)
            finally:
                kernel32.CloseHandle(handle)

    def _resize_restarted_client(self, hwnd: int) -> None:
        ref_w, ref_h = self.reference_size
        rect = wintypes.RECT(0, 0, int(ref_w), int(ref_h))
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -16)
        ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        ctypes.windll.user32.AdjustWindowRectEx(ctypes.byref(rect), style, False, ex_style)
        ctypes.windll.user32.SetWindowPos(
            hwnd, 0, 0, 0, rect.right - rect.left, rect.bottom - rect.top,
            0x0002 | 0x0004 | 0x0040,
        )

    @property
    def pipe_name(self) -> str:
        return rf"\\.\pipe\KVTM-Cocos-{self.pid}"

    def _pipe(self, command: str, timeout_ms: int = 3000) -> str:
        payload = command.encode("ascii")
        deadline = time.monotonic() + max(0.15, timeout_ms / 1000.0)
        last_error = 2
        while time.monotonic() < deadline:
            output = ctypes.create_string_buffer(256)
            read = wintypes.DWORD()
            remaining_ms = max(25, min(250, int((deadline - time.monotonic()) * 1000)))
            ok = kernel32.CallNamedPipeW(
                self.pipe_name, ctypes.c_char_p(payload), len(payload), output,
                len(output), ctypes.byref(read), remaining_ms,
            )
            if ok:
                response = output.raw[:read.value].decode("ascii", "replace").strip()
                if not response.startswith("OK"):
                    raise RuntimeError(f"Engine bridge trả về: {response}")
                return response
            last_error = int(kernel32.GetLastError())
            if last_error not in (2, 231):  # FILE_NOT_FOUND / PIPE_BUSY
                raise ctypes.WinError(last_error)
            time.sleep(0.005)
        raise ctypes.WinError(last_error)

    def _ensure_bridge(self) -> None:
        if not LOADER.is_file() or not BRIDGE.is_file():
            raise RuntimeError("Thiếu bin\\kvtm_loader.exe hoặc bin\\kvtm_bridge.dll; chạy BUILD_X86.bat trước")
        try:
            if self._pipe("PING\n", 150).startswith("OK"):
                return
        except Exception:
            pass
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(
            [str(LOADER), str(self.pid), str(BRIDGE)], capture_output=True,
            text=True, creationflags=flags, timeout=15,
        )
        if result.returncode:
            raise RuntimeError(
                f"Không nạp được engine bridge (code {result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        last_error = None
        for _ in range(50):
            try:
                self._pipe("PING\n", 150)
                return
            except Exception as exc:
                last_error = exc
                time.sleep(0.10)
        raise RuntimeError(f"DLL đã nạp nhưng named pipe chưa sẵn sàng: {last_error}")

    def _touch_event(self, phase: str, x: float, y: float) -> None:
        name = {"down": "DOWN", "move": "MOVE", "up": "UP"}[phase]
        try:
            self._pipe(f"{name} {float(x):.3f} {float(y):.3f}\n")
        except Exception as exc:
            self._trace(
                "engine_touch_error", phase=phase,
                logical=[float(x), float(y)], error=str(exc),
            )
            raise RuntimeError(f"Cocos touch {phase} thất bại: {exc}") from exc

    @property
    def capture_mapping_name(self) -> str:
        return rf"Local\KVTM-Capture-{self.pid}"

    def _capture_shared_bgra(self) -> tuple[bytes, int, int]:
        response = self._pipe("CAPTURE\n", 3000)
        parts = response.split()
        if len(parts) != 7 or parts[:2] != ["OK", "FRAME"]:
            raise RuntimeError(f"Phản hồi capture không hợp lệ: {response}")
        expected_frame, expected_width, expected_height, expected_stride = map(int, parts[2:])
        handle = kernel32.OpenFileMappingW(0x0004, False, self.capture_mapping_name)  # FILE_MAP_READ
        if not handle:
            raise ctypes.WinError()
        view = None
        try:
            view = kernel32.MapViewOfFile(handle, 0x0004, 0, 0, 0)
            if not view:
                raise ctypes.WinError()
            header_format = "<4s9IQ"
            header_size = struct.calcsize(header_format)
            values = struct.unpack(header_format, ctypes.string_at(view, header_size))
            (
                magic, version, mapped_header_size, width, height, stride,
                pixel_format, buffer_size, frame_id, status, _timestamp_ms,
            ) = values
            if magic != b"KCAP" or version != 1 or mapped_header_size < header_size:
                raise RuntimeError("Shared capture header không hợp lệ")
            if status != 2 or frame_id != expected_frame:
                raise RuntimeError("Shared capture frame chưa hoàn tất hoặc đã thay đổi")
            if (width, height, stride) != (
                expected_width, expected_height, expected_stride
            ):
                raise RuntimeError("Kích thước shared capture không khớp phản hồi")
            if pixel_format != 1 or stride != width * 4 or buffer_size != stride * height:
                raise RuntimeError("Định dạng shared capture không được hỗ trợ")
            raw = ctypes.string_at(int(view) + mapped_header_size, buffer_size)
            return raw, width, height
        finally:
            if view:
                kernel32.UnmapViewOfFile(view)
            kernel32.CloseHandle(handle)

    def screenshot(self, format: str | None = None):
        try:
            raw, width, height = self._capture_shared_bgra()
            set_capture_scale(min(
                width / self.reference_size[0],
                height / self.reference_size[1],
                1.0,
            ))
            if format == "opencv":
                import numpy as np
                import cv2
                frame = np.frombuffer(raw, dtype=np.uint8).reshape(
                    (height, width, 4)
                )[::-1, :, :3].copy()
                if (width, height) != self.reference_size:
                    frame = cv2.resize(
                        frame, self.reference_size, interpolation=cv2.INTER_AREA
                    )
                return frame
            from PIL import Image
            image = Image.frombuffer(
                "RGBA", (width, height), raw, "raw", "BGRA", 0, -1
            ).convert("RGB")
            if image.size != self.reference_size:
                image = image.resize(self.reference_size, Image.Resampling.LANCZOS)
            return image
        except Exception as exc:
            self._trace("shared_capture_fallback", error=str(exc))
            hwnd = find_window(self.pid)
            rect = wintypes.RECT()
            scale = 1.0
            if hwnd and ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect)):
                width, height = rect.right - rect.left, rect.bottom - rect.top
                scale = min(
                    width / self.reference_size[0],
                    height / self.reference_size[1],
                    1.0,
                )
            set_capture_scale(scale)
            return super().screenshot(format=format)

    def swipe_points(self, points, duration: float = 0.5) -> None:
        """uiautomator2-compatible continuous gesture through every point."""
        path = [(float(point[0]), float(point[1])) for point in points]
        if len(path) < 2:
            raise ValueError("swipe_points cần ít nhất hai tọa độ")
        for x, y in path:
            if not (0 <= x <= 1000 and 0 <= y <= 1000):
                raise ValueError(f"Tọa độ swipe_points ngoài vùng 1000x1000: {(x, y)}")

        # Android interpolates swipePoints between waypoints. Do the same so
        # Cocos receives a real continuous drag instead of large coordinate jumps.
        replay_path = [path[0]]
        for start, end in zip(path, path[1:]):
            dx, dy = end[0] - start[0], end[1] - start[1]
            steps = max(1, int(math.ceil(math.hypot(dx, dy) / 8.0)))
            for step in range(1, steps + 1):
                ratio = step / steps
                replay_path.append((start[0] + dx * ratio, start[1] + dy * ratio))

        requested_duration = max(0.0, float(duration))
        # AUTO PRO is authoritative for gesture timing. For swipe_points its
        # duration is the requested time of each logical segment, matching the
        # old Android implementation. Shop drags use PCDriver.swipe directly.
        speed = {"source": "auto_pro", "requested_seconds": requested_duration}
        total_duration = max(0.02, requested_duration * (len(path) - 1))
        interval = total_duration / max(1, len(replay_path) - 1)
        with _GESTURE_LOCK:
            self._trace(
                "swipe_points_attempt", logical_path=[list(point) for point in path],
                point_count=len(path), requested_duration=requested_duration,
                duration=total_duration, interval=interval,
                replay_point_count=len(replay_path), interpolation_px=8,
                speed_settings=speed, mode="engine_bridge",
            )
            self._touch_event("down", *replay_path[0])
            try:
                for point in replay_path[1:]:
                    time.sleep(interval)
                    self._touch_event("move", *point)
                self._touch_event("up", *replay_path[-1])
            except Exception:
                try:
                    self._touch_event("up", *replay_path[-1])
                except Exception:
                    pass
                raise
            self._trace(
                "touch_path", logical_path=[list(point) for point in path],
                point_count=len(path), replay_point_count=len(replay_path),
                duration=total_duration, mode="engine_bridge",
            )

    def app_stop(self, _package: str) -> None:
        """Close only when this PID can be relaunched from a saved Multi profile."""
        if not self._restart_profile:
            self._trace("pc_restart_skipped", reason="profile_not_matched")
            self._restart_pending = False
            return
        self._restart_pending = True
        self._close_exact_process()

    def app_start(self, _package: str, **_kwargs) -> int:
        """Relaunch the same saved profile and move this driver to its new PID."""
        if not self._restart_pending and self._is_process_alive(self.pid):
            return self.pid
        profile = self._restart_profile
        if not profile:
            return self.pid
        client = Path(profile["client"])
        game_dir = Path(profile["game_dir"])
        secret_args = json.loads(_unprotect(profile["secret"]).decode("utf-8"))
        process = subprocess.Popen(
            [str(client), str(game_dir), *secret_args], cwd=str(game_dir),
        )
        old_pid = self.pid
        self.pid = int(process.pid)
        self._process = process
        self._restart_pending = False
        hwnd = None
        for _ in range(150):
            hwnd = find_window(self.pid)
            if hwnd:
                break
            if process.poll() is not None:
                raise RuntimeError(f"Client restart đã thoát với code {process.returncode}")
            time.sleep(0.10)
        if not hwnd:
            raise RuntimeError("Client restart không tạo cửa sổ sau 15 giây")
        self._resize_restarted_client(hwnd)
        if self._restart_window_rect:
            old_x, old_y, _old_w, _old_h = self._restart_window_rect
            rect = wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            ctypes.windll.user32.SetWindowPos(
                hwnd, 0, old_x, old_y,
                rect.right - rect.left, rect.bottom - rect.top,
                0x0004 | 0x0010 | 0x0040,
            )
        self._ensure_bridge()
        self._trace(
            "pc_restart_complete", old_pid=old_pid, new_pid=self.pid,
            profile_name=profile.get("name", ""),
        )
        return self.pid
