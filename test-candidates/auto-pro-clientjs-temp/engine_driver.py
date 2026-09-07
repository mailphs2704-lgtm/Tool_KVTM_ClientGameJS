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
import sys
import threading
import time

from pc_driver import PCDriver, find_window
from adaptive_cv import set_capture_scale


ROOT = Path(__file__).resolve().parent
BIN = ROOT / "bin"
LOADER = BIN / "kvtm_loader_v3.exe"
BRIDGE = BIN / "kvtm_bridge_v3.dll"
_PROTOCOL_PREFIX = "OK PONG KVTM_BRIDGE_V3"
_GESTURE_LOCK = threading.RLock()
PROFILE_FILE = Path(
    os.environ.get("KVTM_MULTI_PROFILE_FILE")
    or (Path(os.environ.get("APPDATA", Path.home())) / "KVTM Multi" / "profiles.json")
)

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
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.ReadFile.argtypes = [
        wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
    ]
    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.WriteFile.argtypes = [
        wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
    ]
    kernel32.WriteFile.restype = wintypes.BOOL
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


class EngineTouchProxy:
    """Chained touch API that never delegates to Windows or the real cursor."""

    def __init__(self, driver) -> None:
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


class EngineDriver(PCDriver):
    """PCDriver whose coordinates are delivered inside the Cocos engine."""

    def _trace(self, _action: str, **_details) -> None:
        """Keep Bridge V3 independent from whichever resident PCDriver is loaded.

        AUTO MULTI DEV owns user-facing logging. Per-input screenshot tracing here
        would add another capture layer and distort native batch timing.
        """
        return None

    def __init__(self, device_key: int | str, reference_size=(1000, 1000)) -> None:
        self.profile_id = None
        self._restart_profile = None
        if isinstance(device_key, str) and not device_key.isdigit():
            self.profile_id = device_key
            self._restart_profile = self._profile_by_id(device_key)
            if not self._restart_profile:
                raise RuntimeError(f"Không tìm thấy hồ sơ cố định {device_key}")
            pid = self._find_profile_pid(self._restart_profile)
            if not pid:
                raise RuntimeError(
                    f"Hồ sơ {self._restart_profile.get('name', device_key)} đang offline"
                )
        else:
            pid = int(device_key)
        super().__init__(pid, reference_size=reference_size)
        # Never retain TouchProxy from whichever resident PCDriver happened to
        # be imported. Every chained touch must enter the Cocos V3 pipe.
        self.touch = EngineTouchProxy(self)
        if self._restart_profile is None:
            self._restart_profile = self._resolve_restart_profile(pid)
            if self._restart_profile:
                self.profile_id = str(self._restart_profile.get("id") or "") or None
        self._restart_pending = False
        self._restart_window_rect = None
        self._pipe_handle = None
        self._pipe_lock = threading.RLock()
        self._ensure_bridge()
        self._trace(
            "engine_bridge_connected", pipe=self.pipe_name,
            restart_profile=bool(self._restart_profile),
        )

    def _profile_by_id(self, profile_id: str):
        try:
            profiles = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
            return next(
                (item for item in profiles if str(item.get("id") or "") == str(profile_id)),
                None,
            )
        except Exception:
            return None

    def _find_profile_pid(self, profile: dict) -> int | None:
        """Resolve the current runtime PID from the profile's immutable account ID."""
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            script = (
                "$p=Get-CimInstance Win32_Process -Filter \"Name='GameClientJS.exe'\" | "
                "Select-Object ProcessId,CommandLine;@($p)|ConvertTo-Json -Compress"
            )
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, text=True, encoding="utf-8-sig", errors="replace",
                creationflags=flags, timeout=15, check=True,
            )
            rows = json.loads(result.stdout or "[]")
            if isinstance(rows, dict):
                rows = [rows]
            wanted_game = os.path.normcase(os.path.abspath(profile.get("game_dir") or ""))
            wanted_secret = json.loads(_unprotect(profile["secret"]).decode("utf-8"))
            for row in rows:
                args = _split_command_line(row.get("CommandLine") or "")
                if len(args) < 2:
                    continue
                running_game = os.path.normcase(os.path.abspath(args[1]))
                if running_game == wanted_game and args[2:] == wanted_secret:
                    return int(row["ProcessId"])
        except Exception as exc:
            if hasattr(self, "_trace_count"):
                self._trace("profile_pid_lookup_error", error=str(exc))
        return None

    def _refresh_profile_pid(self) -> bool:
        """Adopt a replacement PID after ClientGameJS resets without changing device ID."""
        if self._is_process_alive(self.pid):
            return False
        if not self._restart_profile:
            raise RuntimeError(f"ClientGameJS PID {self.pid} đã dừng")
        replacement = self._find_profile_pid(self._restart_profile)
        if not replacement:
            raise RuntimeError(
                f"Tài khoản {self._restart_profile.get('name', self.profile_id)} chưa khởi động lại"
            )
        old_pid = self.pid
        self._close_pipe()
        self.pid = int(replacement)
        self._ensure_bridge()
        self._trace(
            "profile_pid_rebound", profile_id=self.profile_id,
            old_pid=old_pid, new_pid=self.pid,
        )
        return True

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
        """Close the old client completely without modifying its saved profile."""
        old_pid = int(self.pid)
        hwnd = find_window(old_pid)
        if hwnd:
            rect = wintypes.RECT()
            if ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                self._restart_window_rect = (
                    rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top,
                )
            self._trace("pc_restart_close_requested", old_pid=old_pid)
            ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE

        # Give ClientJS/ZingPC up to eight seconds to persist and exit naturally.
        natural_deadline = time.monotonic() + 8.0
        while time.monotonic() < natural_deadline:
            if not self._is_process_alive(old_pid):
                self._trace("pc_restart_old_pid_exited", old_pid=old_pid, forced=False)
                return
            time.sleep(0.10)

        # Kill only the verified old PID and its descendants. Profiles/settings
        # remain read-only; no account file is rewritten during restart.
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(
            ["taskkill.exe", "/PID", str(old_pid), "/T", "/F"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=flags,
            timeout=10,
        )
        self._trace(
            "pc_restart_process_tree_terminated",
            old_pid=old_pid,
            exit_code=int(result.returncode),
        )

        forced_deadline = time.monotonic() + 5.0
        while time.monotonic() < forced_deadline:
            if not self._is_process_alive(old_pid):
                self._trace("pc_restart_old_pid_exited", old_pid=old_pid, forced=True)
                return
            time.sleep(0.10)
        raise RuntimeError(
            f"Không thể xác nhận PID ClientJS cũ {old_pid} đã dừng; không mở trùng client"
        )

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
        return rf"\\.\pipe\KVTM-CocosV3-{self.pid}"

    def _close_pipe(self) -> None:
        handle = getattr(self, "_pipe_handle", None)
        self._pipe_handle = None
        if handle:
            kernel32.CloseHandle(handle)

    def _open_pipe(self):
        invalid = ctypes.c_void_p(-1).value
        handle = kernel32.CreateFileW(
            self.pipe_name, 0xC0000000, 0, None, 3, 0, None,
        )
        if not handle or int(handle) == int(invalid):
            raise ctypes.WinError()
        self._pipe_handle = handle
        return handle

    def _pipe(self, command: str, timeout_ms: int = 3000) -> str:
        payload = command.encode("ascii")
        deadline = time.monotonic() + max(0.15, timeout_ms / 1000.0)
        last_error = 2
        with self._pipe_lock:
            while time.monotonic() < deadline:
                try:
                    handle = self._pipe_handle or self._open_pipe()
                    written = wintypes.DWORD()
                    if not kernel32.WriteFile(
                        handle, ctypes.c_char_p(payload), len(payload),
                        ctypes.byref(written), None,
                    ):
                        raise ctypes.WinError()
                    output = ctypes.create_string_buffer(256)
                    read = wintypes.DWORD()
                    if not kernel32.ReadFile(
                        handle, output, len(output), ctypes.byref(read), None,
                    ):
                        raise ctypes.WinError()
                    response = output.raw[:read.value].decode("ascii", "replace").strip()
                    if not response.startswith("OK"):
                        raise RuntimeError(f"Engine bridge trả về: {response}")
                    return response
                except RuntimeError:
                    raise
                except Exception:
                    last_error = int(kernel32.GetLastError()) or 2
                    self._close_pipe()
                    if last_error not in (2, 109, 231, 232, 233):
                        raise ctypes.WinError(last_error)
                    time.sleep(0.005)
        raise ctypes.WinError(last_error)

    def _ensure_bridge(self) -> None:
        if not LOADER.is_file() or not BRIDGE.is_file():
            raise RuntimeError("Thiếu binary Bridge V3 trong AUTO_PRO\\bin; chạy Control Center build trước")
        try:
            if self._pipe("PING\n", 150).startswith(_PROTOCOL_PREFIX):
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
                response = self._pipe("PING\n", 150)
                if not response.startswith(_PROTOCOL_PREFIX):
                    raise RuntimeError(f"Protocol bridge không đúng V3: {response}")
                return
            except Exception as exc:
                last_error = exc
                time.sleep(0.10)
        raise RuntimeError(f"DLL đã nạp nhưng named pipe chưa sẵn sàng: {last_error}")

    def _touch_event(self, phase: str, x: float, y: float) -> None:
        if phase == "down":
            self._refresh_profile_pid()
        name = {"down": "DOWN", "move": "MOVE", "up": "UP"}[phase]
        try:
            self._pipe(f"{name} {float(x):.3f} {float(y):.3f}\n")
        except Exception as exc:
            self._trace(
                "engine_touch_error", phase=phase,
                logical=[float(x), float(y)], error=str(exc),
            )
            raise RuntimeError(f"Cocos touch {phase} thất bại: {exc}") from exc

    def click(self, x: float, y: float) -> None:
        """Tap through INPUT4 without Windows mouse/touch injection."""
        with _GESTURE_LOCK:
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
    ):
        """Send a two-point gesture as one native BATCH_SWIPE command."""
        return self.swipe_points(
            [(float(x1), float(y1)), (float(x2), float(y2))],
            duration=duration,
        )

    @property
    def capture_mapping_name(self) -> str:
        return rf"Local\KVTM-CaptureV3-{self.pid}"

    def _capture_shared_bgra_once(self) -> tuple[bytes, int, int]:
        # Keep the pipe transaction and shared-memory copy atomic relative to
        # every other command from this driver. Without this outer RLock,
        # another screenshot can publish a newer frame after OK FRAME but
        # before the current pixels/header have been copied.
        with self._pipe_lock:
            return self._capture_shared_bgra_once_locked()

    def _capture_shared_bgra_once_locked(self) -> tuple[bytes, int, int]:
        response = self._pipe("CAPTURE\n", 3000)
        parts = response.split()
        if len(parts) != 6 or parts[:2] != ["OK", "FRAME"]:
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
            if magic != b"KCAP" or version != 3 or mapped_header_size < header_size:
                raise RuntimeError("Shared capture header không hợp lệ")
            if status != 2 or frame_id < expected_frame:
                raise RuntimeError(
                    "Shared capture frame chưa hoàn tất hoặc cũ hơn phản hồi "
                    f"(expected={expected_frame}, actual={frame_id}, status={status})"
                )
            # Another CAPTURE3 consumer for the same PID may publish a newer
            # complete frame after this command returns. That frame is valid;
            # require response dimensions only when it is the exact response.
            if frame_id == expected_frame and (width, height, stride) != (
                expected_width, expected_height, expected_stride
            ):
                raise RuntimeError(
                    "Kích thước shared capture không khớp phản hồi "
                    f"(frame={frame_id}, response={expected_width}x{expected_height} "
                    f"stride={expected_stride}, shared={width}x{height} stride={stride})"
                )
            if (
                pixel_format != 2
                or stride != width * 4
                or buffer_size != stride * height
                or buffer_size > 64 * 1024 * 1024
            ):
                raise RuntimeError("Định dạng shared capture không được hỗ trợ")
            snapshot_key = (
                version, mapped_header_size, width, height, stride,
                pixel_format, buffer_size, frame_id, status,
            )
            raw = ctypes.string_at(int(view) + mapped_header_size, buffer_size)
            # Seqlock-style verification: accept an exact or newer completed
            # frame only if no header field changed while pixels were copied.
            verified = struct.unpack(header_format, ctypes.string_at(view, header_size))
            verified_key = tuple(verified[1:10])
            if verified_key != snapshot_key or verified[9] != 2:
                raise RuntimeError("Shared capture frame thay đổi trong lúc sao chép")
            return raw, width, height
        finally:
            if view:
                kernel32.UnmapViewOfFile(view)
            kernel32.CloseHandle(handle)

    def _capture_shared_bgra(self) -> tuple[bytes, int, int]:
        last_error = None
        for attempt in range(12):
            try:
                return self._capture_shared_bgra_once()
            except Exception as exc:
                last_error = exc
                message = str(exc)
                transient = (
                    "frame chưa hoàn tất hoặc cũ hơn phản hồi" in message
                    or "frame thay đổi trong lúc sao chép" in message
                    or "Kích thước shared capture không khớp phản hồi" in message
                )
                if not transient:
                    raise
                self._trace(
                    "v3_capture_frame_retry",
                    attempt=attempt + 1,
                    max_attempts=12,
                    error=message,
                )
                time.sleep(0.01)
        raise RuntimeError(
            f"Shared capture không ổn định sau 12 lần thử: {last_error}"
        )

    def screenshot(self, format: str | None = None):
        self._refresh_profile_pid()
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
                )[:, :, :3].copy()
                if (width, height) != self.reference_size:
                    frame = cv2.resize(
                        frame, self.reference_size, interpolation=cv2.INTER_AREA
                    )
                return frame
            from PIL import Image
            image = Image.frombuffer(
                "RGBA", (width, height), raw, "raw", "BGRA", 0, 1
            ).convert("RGB")
            if image.size != self.reference_size:
                image = image.resize(self.reference_size, Image.Resampling.LANCZOS)
            return image
        except Exception as exc:
            self._trace("v3_capture_error", error=str(exc), fallback="disabled")
            raise RuntimeError(f"Bridge V3 capture thất bại; không dùng HWND fallback: {exc}") from exc

    def swipe_points(self, points, duration: float = 0.5) -> None:
        """Match AUTO PRO/uiautomator2: one batch, duration per segment."""
        path = [(float(point[0]), float(point[1])) for point in points]
        if len(path) < 2:
            raise ValueError("swipe_points cần ít nhất hai tọa độ")
        if len(path) > 32:
            raise ValueError("swipe_points hỗ trợ tối đa 32 mốc logic")
        for x, y in path:
            if not (0 <= x <= 1000 and 0 <= y <= 1000):
                raise ValueError(
                    f"Tọa độ swipe_points ngoài vùng 1000x1000: {(x, y)}"
                )

        configured_duration = max(0.005, float(duration))
        # AUTO PRO's uiautomator2 adapter uses int(duration / 0.005).
        segment_steps = max(1, min(400, int(configured_duration / 0.005)))
        expected_total = (
            segment_steps * 0.005 * max(1, len(path) - 1)
        )
        try:
            caller_name = sys._getframe(1).f_code.co_name
        except Exception:
            caller_name = "unknown"

        coordinates = " ".join(
            f"{x:.3f} {y:.3f}" for x, y in path
        )
        command = f"SWIPE {segment_steps} {len(path)} {coordinates}\n"
        with _GESTURE_LOCK:
            started = time.perf_counter()
            self._trace(
                "swipe_points_attempt",
                logical_path=[list(point) for point in path],
                logical_point_count=len(path),
                configured_seconds_per_segment=configured_duration,
                segment_steps=segment_steps,
                expected_total_seconds=expected_total,
                pipe_mode="single_batch",
                timing_owner="bridge_v3_native",
                mode="engine_bridge_v3",
            )
            response = self._pipe(
                command,
                max(3000, int(expected_total * 1000) + 3000),
            )
            actual_duration = time.perf_counter() - started
            parts = response.split()
            if len(parts) != 4 or parts[:2] != ["OK", "SWIPE"]:
                raise RuntimeError(
                    f"Phản hồi batch swipe không hợp lệ: {response}"
                )
            native_actual_ms = int(parts[2])
            move_count = int(parts[3])
            timing = {
                "caller": caller_name,
                # Keep the UI value visible while exposing original per-segment
                # semantics and the expected duration of the complete polyline.
                "requested_seconds": configured_duration,
                "configured_seconds_per_segment": configured_duration,
                "expected_total_seconds": expected_total,
                "actual_seconds": actual_duration,
                "native_actual_seconds": native_actual_ms / 1000.0,
                "point_count": len(path),
                "logical_point_count": len(path),
                "move_count": move_count,
                "segment_steps": segment_steps,
                "timing_error_ms": (
                    actual_duration - expected_total
                ) * 1000.0,
                "pipe_mode": "single_batch",
            }
            self._trace(
                "touch_path",
                logical_path=[list(point) for point in path],
                mode="engine_bridge_v3_batch",
                **timing,
            )
            observer = getattr(self, "gesture_observer", None)
            if callable(observer):
                try:
                    observer(dict(timing))
                except Exception:
                    pass
            return timing

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
        self._close_pipe()
        self.pid = int(process.pid)
        self._process = process
        self._restart_pending = False
        hwnd = None
        hwnd_deadline = time.monotonic() + 60.0
        while time.monotonic() < hwnd_deadline:
            hwnd = find_window(self.pid)
            if hwnd:
                break
            if process.poll() is not None:
                raise RuntimeError(f"Client restart đã thoát với code {process.returncode}")
            time.sleep(0.10)
        if not hwnd:
            raise RuntimeError("Client restart không tạo HWND sau 60 giây")
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
            "pc_restart_runtime_ready",
            old_pid=old_pid,
            new_pid=self.pid,
            hwnd=int(hwnd),
            bridge_ready=True,
            profile_name=profile.get("name", ""),
            profile_storage="READ_ONLY",
        )
        return self.pid
