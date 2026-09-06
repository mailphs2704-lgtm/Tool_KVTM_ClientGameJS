from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import uuid

from pc_driver import (
    BITMAPINFO, capture_bgra, capture_shared_bgra,
    save_diagnostic, save_four_floor_swipe_preview,
)


APP_NAME = os.environ.get("KVTM_MULTI_INSTANCE_NAME", "KVTM Multi")
ISOLATED_INSTANCE = os.environ.get("KVTM_MULTI_ISOLATED", "").strip().lower() in {"1", "true", "yes", "on"}
GAME_ID = "24"
APP_DIR = Path(os.environ.get("KVTM_MULTI_APP_DIR") or (Path(os.environ.get("APPDATA", Path.home())) / "KVTM Multi"))
PROFILE_FILE = APP_DIR / "profiles.json"
SETTINGS_FILE = APP_DIR / "settings.json"
RUNNING_MAP_FILE = APP_DIR / "running_clients.json"
PROFILE_BACKUP_DIR = APP_DIR / "profile-backups"
CLEAR_STALL_HISTORY_FILE = APP_DIR / "clear-stall-history.jsonl"
DEFAULT_CLIENT = Path(r"C:\Program Files\ZingPlay\data\flutter_assets\assets\runtime\GameClientJS.exe")
DEFAULT_GAME = Path(os.environ.get("APPDATA", Path.home())) / "VNG Corporation" / "ZingPlay" / "zpp" / GAME_ID / "game"
DEFAULT_DISPLAY = {"width": 1000, "height": 1000, "dpi": 240}
CLEAR_STALL_ITEM_OPTIONS = (
    ("nuoc_hoa_hong", "Nước hoa hồng"),
    ("tinh_dau_hh", "Tinh dầu hoa hồng"),
    ("vai_vang", "Vải vàng"),
    ("tao_say", "Táo sấy"),
    ("tra_da", "Trà đá"),
)

DEFAULT_AUTO_TUNING = {
    # AUTO MULTI DEV: three independent controls. Legacy AUTO PRO keys below
    # remain intact for compatibility with the historical worker.
    "floor_swipe_duration": 0.35,
    "plant_harvest_duration": 0.035,
    "vp_production_delay": 0.4,
    "harvest_speed": 0.045,
    "go_up_wait": 0.7,
    "production_wait": 0.4,
    "swipe_count": 4,
    "quay_speed": 0.5,
    "shop_drag_speed": 0.35,
    "speed_sell_item": 0.5,
    "check_harvest": 0.3,
    "click_speed": 0.3,
    "delete_check_speed": 0.5,
    "next_gieo": 0.4,
    "delete_count": 10,
    "max_sell_times": 1,
    "collect_gold_speed": 0.4,
    "check_nang_kho": 0.5,
    "delay_vao_game": 55,
}
AUTO_TUNING_SPECS = {
    "floor_swipe_duration": ("MULTI DEV • Kéo tầng (giây/swipe)", 0.05, 3.0, False),
    "plant_harvest_duration": ("MULTI DEV • Trồng/thu cây (giây/đoạn)", 0.01, 3.0, False),
    "vp_production_delay": ("MULTI DEV • Sản xuất VP (giây/thao tác)", 0.05, 10.0, False),
    "harvest_speed": ("AUTO PRO cũ • Tốc độ cào", 0.01, 3.0, False),
    "go_up_wait": ("Chờ sau khi kéo tầng", 0.05, 10.0, False),
    "production_wait": ("Chờ sản xuất", 0.05, 10.0, False),
    "swipe_count": ("Số lần kéo màn", 1, 20, True),
    "quay_speed": ("Tốc độ quay/kéo", 0.05, 5.0, False),
    "shop_drag_speed": ("Tốc độ kéo quầy", 0.05, 3.0, False),
    "speed_sell_item": ("Tốc độ bán vật phẩm", 0.05, 5.0, False),
    "check_harvest": ("Chu kỳ kiểm tra thu hoạch", 0.05, 5.0, False),
    "click_speed": ("Khoảng nghỉ giữa click", 0.02, 5.0, False),
    "delete_check_speed": ("Chu kỳ kiểm tra xóa", 0.05, 5.0, False),
    "next_gieo": ("Chờ chuyển lượt gieo", 0.05, 5.0, False),
    "delete_count": ("Số lượt xóa tối đa", 1, 100, True),
    "max_sell_times": ("Số lượt bán tối đa", 1, 50, True),
    "collect_gold_speed": ("Tốc độ thu vàng", 0.05, 5.0, False),
    "check_nang_kho": ("Chu kỳ kiểm tra nâng kho", 0.05, 10.0, False),
    "delay_vao_game": ("Chờ sau khi vào game (giây)", 0, 300, True),
}
TOOL_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent

DWM_TNP_RECTDESTINATION = 0x00000001
DWM_TNP_VISIBLE = 0x00000008
DWM_TNP_SOURCECLIENTAREAONLY = 0x00000010


class DWM_THUMBNAIL_PROPERTIES(ctypes.Structure):
    _fields_ = [
        ("dwFlags", wintypes.DWORD),
        ("rcDestination", wintypes.RECT),
        ("rcSource", wintypes.RECT),
        ("opacity", ctypes.c_ubyte),
        ("fVisible", wintypes.BOOL),
        ("fSourceClientAreaOnly", wintypes.BOOL),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


class RunningProcessRef:
    """Small Popen-compatible reference for a client adopted after Multi restarts."""

    def __init__(self, pid: int):
        self.pid = int(pid)

    def poll(self):
        handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, self.pid)
        if not handle:
            return 1
        try:
            return None if ctypes.windll.kernel32.WaitForSingleObject(handle, 0) == 0x102 else 0
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)

    def terminate(self):
        handle = ctypes.windll.kernel32.OpenProcess(0x0001 | 0x00100000, False, self.pid)
        if not handle:
            return
        try:
            ctypes.windll.kernel32.TerminateProcess(handle, 0)
            ctypes.windll.kernel32.WaitForSingleObject(handle, 3000)
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)


class PreviewWindow(tk.Toplevel):
    """Low-latency OpenGL preview backed by the bridge KCAP mapping."""

    def __init__(self, owner, profile_id: str, title: str, source_hwnd: int):
        super().__init__(owner)
        self.owner = owner
        self.profile_id = profile_id
        self.source_hwnd = source_hwnd
        self._closing = False
        self._square_job = None
        self._stop = threading.Event()
        self._frames: queue.Queue = queue.Queue(maxsize=1)
        self._latest = None
        self._dib_pixels = None
        self._dib_size = 0
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        user32.GetDC.argtypes = [wintypes.HWND]
        user32.GetDC.restype = wintypes.HANDLE
        user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HANDLE]
        user32.ReleaseDC.restype = ctypes.c_int
        gdi32.SetStretchBltMode.argtypes = [wintypes.HANDLE, ctypes.c_int]
        gdi32.SetStretchBltMode.restype = ctypes.c_int
        gdi32.StretchDIBits.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.LPVOID, ctypes.POINTER(BITMAPINFO),
            wintypes.UINT, wintypes.DWORD,
        ]
        gdi32.StretchDIBits.restype = ctypes.c_int
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(source_hwnd, ctypes.byref(pid))
        self.pid = int(pid.value)
        self.title(f"{title} - Live View")
        self.configure(background="black")
        self.geometry("540x540")
        self.minsize(260, 260)
        self.canvas = tk.Canvas(self, background="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.status = tk.StringVar(value="Đang kết nối OpenGL capture...")
        ttk.Label(self, textvariable=self.status, anchor="center").pack(fill="x")
        self.bind("<Configure>", self._on_configure)
        self.canvas.bind("<Expose>", lambda _event: self._paint_latest())
        self.protocol("WM_DELETE_WINDOW", self.close)
        threading.Thread(target=self._capture_loop, daemon=True).start()
        self.after(20, self._poll_frame)

    def _on_configure(self, _event=None):
        if self._closing:
            return
        width, height = self.winfo_width(), self.winfo_height()
        side = min(width, height)
        if abs(width - height) > 2 and not self._square_job:
            self._square_job = self.after_idle(lambda s=side: self._force_square(s))

    def _force_square(self, side: int):
        self._square_job = None
        if not self._closing:
            self.geometry(f"{max(260, side)}x{max(260, side)}")

    def _capture_loop(self):
        fallback_count = 0
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                raw, width, height = capture_shared_bgra(self.pid, timeout_ms=2000)
                source = "OpenGL shared memory"
                fallback_count = 0
            except Exception:
                fallback_count += 1
                try:
                    raw, width, height = capture_bgra(self.source_hwnd)
                    source = "Windows fallback"
                except Exception:
                    self._stop.wait(0.15)
                    continue
            item = (raw, width, height, source)
            try:
                self._frames.put_nowait(item)
            except queue.Full:
                try:
                    self._frames.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._frames.put_nowait(item)
                except queue.Full:
                    pass
            # Target 30 FPS while the preview is open; no capture when closed.
            elapsed = time.monotonic() - started
            self._stop.wait(max(0.0, (1.0 / 30.0) - elapsed))

    def _poll_frame(self):
        if self._closing:
            return
        newest = None
        try:
            while True:
                newest = self._frames.get_nowait()
        except queue.Empty:
            pass
        if newest:
            raw, width, height, source = newest
            size = len(raw)
            if self._dib_pixels is None or self._dib_size != size:
                self._dib_pixels = ctypes.create_string_buffer(size)
                self._dib_size = size
            ctypes.memmove(self._dib_pixels, raw, size)
            self._latest = (self._dib_pixels, width, height, source)
            self._paint_latest()
        self.after(16, self._poll_frame)

    def _paint_latest(self):
        if self._closing or not self._latest or not self.canvas.winfo_exists():
            return
        pixels, width, height, source = self._latest
        target_w = max(1, self.canvas.winfo_width())
        target_h = max(1, self.canvas.winfo_height())
        side = min(target_w, target_h)
        left = (target_w - side) // 2
        top = (target_h - side) // 2
        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(info.bmiHeader)
        info.bmiHeader.biWidth = width
        # Bridge v2 normalizes ClientJS capture to top-down BGRA.
        info.bmiHeader.biHeight = -height
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = 0
        canvas_hwnd = self.canvas.winfo_id()
        dc = ctypes.windll.user32.GetDC(canvas_hwnd)
        if dc:
            try:
                ctypes.windll.gdi32.SetStretchBltMode(dc, 4)  # HALFTONE
                ctypes.windll.gdi32.StretchDIBits(
                    dc, left, top, side, side,
                    0, 0, width, height,
                    pixels, ctypes.byref(info), 0, 0x00CC0020,
                )
            finally:
                ctypes.windll.user32.ReleaseDC(canvas_hwnd, dc)
        self.status.set(f"{source} • {width}×{height} • mục tiêu 30 FPS")

    def close(self, restore=True):
        if self._closing:
            return
        self._closing = True
        self._stop.set()
        self.owner.previews.pop(self.profile_id, None)
        self.destroy()


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes) -> tuple[DATA_BLOB, object]:
    buf = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))), buf


def protect(data: bytes) -> str:
    """Encrypt profile secrets for the current Windows user with DPAPI."""
    if os.name != "nt":
        raise RuntimeError("DPAPI is only available on Windows")
    source, keepalive = _blob(data)
    result = DATA_BLOB()
    entropy, entropy_keepalive = _blob(b"KVTM-MULTI-v1")
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(source), APP_NAME, ctypes.byref(entropy), None, None,
        0x01, ctypes.byref(result),
    )
    if not ok:
        raise ctypes.WinError()
    try:
        raw = ctypes.string_at(result.pbData, result.cbData)
        return base64.b64encode(raw).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(result.pbData)
        del keepalive, entropy_keepalive


def unprotect(value: str) -> bytes:
    """Decrypt a DPAPI value created by the current Windows user."""
    raw = base64.b64decode(value)
    source, keepalive = _blob(raw)
    result = DATA_BLOB()
    entropy, entropy_keepalive = _blob(b"KVTM-MULTI-v1")
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(source), None, ctypes.byref(entropy), None, None,
        0x01, ctypes.byref(result),
    )
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(result.pbData)
        del keepalive, entropy_keepalive


def split_windows_command_line(command_line: str) -> list[str]:
    argc = ctypes.c_int()
    parser = ctypes.windll.shell32.CommandLineToArgvW
    parser.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    parser.restype = ctypes.POINTER(wintypes.LPWSTR)
    argv = parser(command_line, ctypes.byref(argc))
    if not argv:
        raise ctypes.WinError()
    try:
        return [argv[i] for i in range(argc.value)]
    finally:
        ctypes.windll.kernel32.LocalFree(argv)


def running_clients() -> list[dict]:
    """Read running GameClientJS command lines without writing secrets to disk."""
    script = (
        "$p=Get-CimInstance Win32_Process -Filter \"Name='GameClientJS.exe'\" | "
        "Select-Object ProcessId,ExecutablePath,CommandLine;"
        "@($p)|ConvertTo-Json -Compress"
    )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    run = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, encoding="utf-8-sig", errors="replace",
        creationflags=flags, timeout=15, check=True,
    )
    data = json.loads(run.stdout or "[]")
    if isinstance(data, dict):
        data = [data]
    return [row for row in data if row.get("CommandLine")]


def _read_profile_list(path: Path) -> list[dict] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else None
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _snapshot_profile_file(source: Path) -> None:
    """Keep timestamped recovery points outside the active profile file."""
    if not source.is_file() or _read_profile_list(source) is None:
        return
    try:
        PROFILE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        unique = f"{time.time_ns() % 1_000_000_000:09d}"
        destination = PROFILE_BACKUP_DIR / f"profiles-{stamp}-{unique}.json"
        shutil.copy2(source, destination)
        snapshots = sorted(
            PROFILE_BACKUP_DIR.glob("profiles-*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        for expired in snapshots[30:]:
            expired.unlink()
    except OSError:
        pass


def load_profiles() -> list[dict]:
    primary = _read_profile_list(PROFILE_FILE)
    if primary is not None:
        _snapshot_profile_file(PROFILE_FILE)
        return primary
    # Recover automatically from the newest valid rotating backup.
    for index in range(1, 6):
        backup = APP_DIR / f"profiles.bak{index}"
        recovered = _read_profile_list(backup)
        if recovered is not None:
            try:
                shutil.copy2(backup, PROFILE_FILE)
            except OSError:
                pass
            return recovered
    return []


def _backup_profiles() -> None:
    if not PROFILE_FILE.is_file():
        return
    _snapshot_profile_file(PROFILE_FILE)
    # Keep five generations; bak1 is always the newest pre-write state.
    oldest = APP_DIR / "profiles.bak5"
    try:
        if oldest.exists():
            oldest.unlink()
        for index in range(4, 0, -1):
            source = APP_DIR / f"profiles.bak{index}"
            if source.exists():
                os.replace(source, APP_DIR / f"profiles.bak{index + 1}")
        shutil.copy2(PROFILE_FILE, APP_DIR / "profiles.bak1")
    except OSError:
        pass


def save_profiles(profiles: list[dict], *, allow_shrink: bool = False) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    on_disk = _read_profile_list(PROFILE_FILE)
    if (
        not allow_shrink
        and on_disk is not None
        and len(on_disk) > len(profiles)
    ):
        raise RuntimeError(
            f"Đã chặn ghi đè: ổ đĩa có {len(on_disk)} hồ sơ nhưng bộ nhớ chỉ còn {len(profiles)}."
        )
    _backup_profiles()
    temp = PROFILE_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")
    # Validate the complete temporary JSON before atomically replacing the active file.
    if _read_profile_list(temp) is None:
        raise RuntimeError("File hồ sơ tạm không hợp lệ; đã giữ nguyên dữ liệu cũ.")
    os.replace(temp, PROFILE_FILE)
    _snapshot_profile_file(PROFILE_FILE)


def load_settings() -> dict:
    try:
        saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        saved = {}
    display = saved.get("display", {}) if isinstance(saved, dict) else {}
    raw_tuning = saved.get("auto_tuning", {}) if isinstance(saved, dict) else {}
    raw_delete_profiles = (
        saved.get("auto_delete_profiles", {}) if isinstance(saved, dict) else {}
    )
    delete_profiles = raw_delete_profiles if isinstance(raw_delete_profiles, dict) else {}
    raw_quay_he_profiles = (
        saved.get("auto_quay_he_profiles", {}) if isinstance(saved, dict) else {}
    )
    quay_he_profiles = (
        raw_quay_he_profiles if isinstance(raw_quay_he_profiles, dict) else {}
    )
    raw_nang_kho_profiles = (
        saved.get("auto_nang_kho_profiles", {}) if isinstance(saved, dict) else {}
    )
    nang_kho_profiles = (
        raw_nang_kho_profiles if isinstance(raw_nang_kho_profiles, dict) else {}
    )
    raw_clear_stall_jobs = (
        saved.get("clear_stall_jobs", {}) if isinstance(saved, dict) else {}
    )
    clear_stall_jobs = (
        raw_clear_stall_jobs if isinstance(raw_clear_stall_jobs, dict) else {}
    )
    tuning = dict(DEFAULT_AUTO_TUNING)
    if isinstance(raw_tuning, dict):
        for key, default in DEFAULT_AUTO_TUNING.items():
            try:
                _label, minimum, maximum, integer = AUTO_TUNING_SPECS[key]
                value = int(raw_tuning[key]) if integer else float(raw_tuning[key])
                if minimum <= value <= maximum:
                    tuning[key] = value
            except (KeyError, TypeError, ValueError):
                pass
    return {
        "display": {
            "width": int(display.get("width", DEFAULT_DISPLAY["width"])),
            "height": int(display.get("height", DEFAULT_DISPLAY["height"])),
            "dpi": int(display.get("dpi", DEFAULT_DISPLAY["dpi"])),
        },
        "bridge_bin": str(saved.get("bridge_bin", "")) if isinstance(saved, dict) else "",
        "auto_tuning": tuning,
        "auto_delete_profiles": delete_profiles,
        "auto_quay_he_profiles": quay_he_profiles,
        "auto_nang_kho_profiles": nang_kho_profiles,
        "clear_stall_jobs": clear_stall_jobs,
    }


def save_settings(settings: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def load_clientjs_auto_catalog() -> list[dict]:
    """Load allow-listed ClientJS AUTO functions from the component catalog."""
    candidates = [
        TOOL_DIR.parent / "components" / "clientjs-auto" / "catalog" / "functions.json",
        Path(__file__).resolve().parents[3] / "components" / "clientjs-auto" / "catalog" / "functions.json",
    ]
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            functions = payload.get("functions", [])
            if isinstance(functions, list):
                return [
                    item for item in functions
                    if isinstance(item, dict) and item.get("enabled_for_test")
                ]
        except (FileNotFoundError, OSError, json.JSONDecodeError, AttributeError):
            continue
    return []


class MultiApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        # Fit the complete control surface inside the primary work area,
        # including the Windows taskbar.
        work_w = max(800, self.winfo_screenwidth())
        work_h = max(560, self.winfo_screenheight() - 80)
        try:
            primary = next(
                (item for item in self._monitors() if item["primary"]), None
            )
            if primary:
                work_w = primary["right"] - primary["left"]
                work_h = primary["bottom"] - primary["top"]
        except Exception:
            pass
        initial_w = min(1180, max(860, work_w))
        initial_h = min(900, max(560, work_h))
        self.geometry(f"{initial_w}x{initial_h}")
        self.minsize(min(820, initial_w), min(520, initial_h))
        self._workspace_height = 305
        self.configure(background="#f3f6fa")
        self.option_add("*Font", ("Segoe UI", 10))
        self.profiles = load_profiles()
        self.settings = load_settings()
        self.processes: dict[str, subprocess.Popen] = {}
        self.previews: dict[str, PreviewWindow] = {}
        self._bridged_pids: set[int] = set()
        self._bridge_lock = threading.Lock()
        self._bridge_stop = threading.Event()
        self._bridge_error = ""
        self._live_images: dict[str, tk.PhotoImage] = {}
        self._live_enabled: set[str] = set()
        self._live_thumbnails: dict[str, ctypes.c_void_p] = {}
        self._live_queue: queue.Queue = queue.Queue(maxsize=64)
        self._checked_profiles: set[str] = set()
        self._active_profile_id: str | None = None
        self._game_data: dict[str, dict] = {}
        self._auto_profile_states: dict[str, dict] = {}
        self._auto_workers: dict[str, subprocess.Popen] = {}
        self._auto_worker_queue: queue.Queue = queue.Queue(maxsize=512)
        self._clean_auto_workers: dict[str, subprocess.Popen] = {}
        self._clean_auto_worker_queue: queue.Queue = queue.Queue(maxsize=256)
        self._clear_stall_workers: dict[str, subprocess.Popen] = {}
        self._clear_stall_worker_queue: queue.Queue = queue.Queue(maxsize=256)
        self._clear_stall_starting: set[str] = set()
        self._auto_catalog = load_clientjs_auto_catalog()
        self._auto_functions_by_label = {
            str(item.get("label")): item
            for item in self._auto_catalog if item.get("label")
        }
        self._auto_function_names = (
            "Chọn chức năng AUTO",
            *self._auto_functions_by_label.keys(),
        )
        self._build_ui()
        self.after_idle(self._keep_control_on_primary)
        self.refresh()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        threading.Thread(target=self._bridge_monitor, daemon=True).start()
        self.after(100, self._update_live_dwm)
        self.after(100, self._poll_auto_workers)
        self.after(120, self._poll_clean_auto_workers)
        self.after(150, self._poll_clear_stall_workers)
        self.after(1000, self._poll_clear_stall_schedule)
        self.after(1500, self._poll)

    def _keep_control_on_primary(self) -> None:
        """Keep the Multi control panel visible when clients move off-screen."""
        primary = next((item for item in self._monitors() if item["primary"]), None)
        if not primary:
            return
        self.update_idletasks()
        work_w = primary["right"] - primary["left"]
        work_h = primary["bottom"] - primary["top"]
        # Fixed-height layout keeps controls, account center and AUTO visible
        # without a vertical scrollbar on a normal 1080p desktop.
        width = min(820, work_w)
        height = min(790, work_h)
        x = primary["left"] + max(0, (work_w - width) // 2)
        y = primary["top"] + max(0, (work_h - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(600, lambda: self.attributes("-topmost", False))

    @staticmethod
    def _profile_signature(profile: dict):
        try:
            game_dir = os.path.normcase(os.path.abspath(profile.get("game_dir") or ""))
            secret = json.loads(unprotect(profile["secret"]).decode("utf-8"))
            return game_dir, secret
        except Exception:
            return None

    def _adopt_running_clients(self, rows: list[dict]) -> None:
        """Reconnect saved profiles to PIDs opened by an older Multi/AUTO run."""
        signatures = {
            profile["id"]: self._profile_signature(profile) for profile in self.profiles
        }
        adopted = 0
        live_pids = set()
        for row in rows:
            try:
                pid = int(row.get("ProcessId", 0))
                args = split_windows_command_line(row.get("CommandLine") or "")
                if pid <= 0 or len(args) < 2:
                    continue
                live_pids.add(pid)
                running_game = os.path.normcase(os.path.abspath(args[1]))
                running_secret = args[2:]
                for profile in self.profiles:
                    signature = signatures.get(profile["id"])
                    if not signature or signature != (running_game, running_secret):
                        continue
                    current = self.processes.get(profile["id"])
                    if not current or current.pid != pid or current.poll() is not None:
                        self.processes[profile["id"]] = RunningProcessRef(pid)
                        adopted += 1
                    break
            except Exception:
                continue

        for profile_id, process in list(self.processes.items()):
            if isinstance(process, RunningProcessRef) and process.pid not in live_pids:
                self.processes.pop(profile_id, None)
        if adopted:
            self.note.set(f"Đã nhận lại {adopted} client đang chạy; có thể chuyển màn hình")
            self.refresh()

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", font=("Segoe UI", 10))
        style.configure("App.TFrame", background="#f3f6fa")
        style.configure("Header.TFrame", background="#17233b")
        style.configure(
            "Title.TLabel", background="#17233b", foreground="#ffffff",
            font=("Segoe UI Semibold", 19),
        )
        style.configure(
            "Subtitle.TLabel", background="#17233b", foreground="#aebbd0",
            font=("Segoe UI", 10),
        )
        style.configure(
            "Panel.TLabelframe", background="#ffffff", bordercolor="#dbe3ef",
            relief="solid", borderwidth=1,
        )
        style.configure(
            "Panel.TLabelframe.Label", background="#f3f6fa",
            foreground="#263653", font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "Action.TButton", background="#e8eef7", foreground="#17233b",
            bordercolor="#cbd6e6", padding=(11, 7), relief="flat",
            font=("Segoe UI Semibold", 9),
        )
        style.map(
            "Action.TButton",
            background=[("pressed", "#c9d8ec"), ("active", "#d9e5f5")],
            foreground=[("disabled", "#98a3b5"), ("active", "#0b57a4")],
            bordercolor=[("focus", "#3b82f6"), ("active", "#9eb9dc")],
        )
        style.configure(
            "Account.Treeview", background="#ffffff", fieldbackground="#ffffff",
            foreground="#24324a", rowheight=34, borderwidth=0,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Account.Treeview.Heading", background="#eaf0f8", foreground="#34445f",
            relief="flat", borderwidth=0, padding=(7, 7),
            font=("Segoe UI Semibold", 9),
        )
        style.map(
            "Account.Treeview",
            background=[("selected", "#d9eaff")],
            foreground=[("selected", "#0b4d91")],
        )
        style.map(
            "Account.Treeview.Heading",
            background=[("active", "#dbe6f4")],
        )
        style.configure("Detail.TFrame", background="#ffffff")
        style.configure(
            "DetailTitle.TLabel", background="#ffffff", foreground="#17233b",
            font=("Segoe UI Semibold", 13),
        )
        style.configure(
            "Key.TLabel", background="#ffffff", foreground="#66738a",
            font=("Segoe UI", 9),
        )
        style.configure(
            "Value.TLabel", background="#ffffff", foreground="#1d2b43",
            font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "Status.TLabel", background="#e8eef7", foreground="#4d5d75",
            padding=(12, 4), font=("Segoe UI", 9),
        )
        style.configure(
            "Auto.TLabelframe", background="#ffffff", bordercolor="#bfd1e8",
            relief="solid", borderwidth=1,
        )
        style.configure(
            "Auto.TLabelframe.Label", background="#f3f6fa",
            foreground="#174a7e", font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "AutoKey.TLabel", background="#ffffff", foreground="#52627a",
            font=("Segoe UI Semibold", 9),
        )
        style.configure(
            "AutoValue.TLabel", background="#ffffff", foreground="#17233b",
            font=("Segoe UI", 10),
        )
        style.configure(
            "AutoStart.TButton", background="#16a36a", foreground="#ffffff",
            bordercolor="#128458", padding=(13, 7), relief="flat",
            font=("Segoe UI Semibold", 9),
        )
        style.map(
            "AutoStart.TButton",
            background=[("pressed", "#0f704c"), ("active", "#138b5c")],
            foreground=[("disabled", "#d5ddd9"), ("active", "#ffffff")],
        )
        style.configure(
            "AutoStop.TButton", background="#e8eef7", foreground="#9f2530",
            bordercolor="#cbd6e6", padding=(11, 7), relief="flat",
            font=("Segoe UI Semibold", 9),
        )
        style.map(
            "AutoStop.TButton",
            background=[("pressed", "#f2cfd2"), ("active", "#f8e0e2")],
        )
        style.configure(
            "Auto.Horizontal.TProgressbar", troughcolor="#e8eef7",
            background="#2f80ed", bordercolor="#e8eef7", lightcolor="#2f80ed",
            darkcolor="#2f80ed",
        )
        style.configure(
            "AutoOption.TCheckbutton", background="#ffffff",
            foreground="#263653", font=("Segoe UI", 9), padding=(4, 2),
        )
        style.map(
            "AutoOption.TCheckbutton",
            background=[("active", "#edf2f8")],
            foreground=[("disabled", "#9aa6b8"), ("active", "#1768c4")],
        )
        style.configure(
            "Queue.Treeview", background="#ffffff", fieldbackground="#ffffff",
            foreground="#263653", rowheight=28, bordercolor="#cbd6e6",
            font=("Segoe UI", 9),
        )
        style.configure(
            "Queue.Treeview.Heading", background="#e8eef7",
            foreground="#174a7e", relief="flat",
            font=("Segoe UI Semibold", 9), padding=(8, 6),
        )
        style.map(
            "Queue.Treeview",
            background=[("selected", "#2f80ed")],
            foreground=[("selected", "#ffffff")],
        )
        style.configure("Sash", sashthickness=6, background="#dbe3ef")

        # The control/account center has a fixed height and no scrollbar.
        # AUTO controls remain directly below it and are always visible.
        body = ttk.Frame(self, style="App.TFrame", height=475)
        body.pack(fill="x")
        body.pack_propagate(False)
        self.content_frame = ttk.Frame(body, style="App.TFrame")
        self.content_frame.pack(fill="both", expand=True)

        controls = ttk.LabelFrame(
            self.content_frame, text="BẢNG ĐIỀU KHIỂN", padding=(10, 8), style="Panel.TLabelframe"
        )
        controls.pack(fill="x", padx=12, pady=(8, 8))
        for column in range(5):
            controls.columnconfigure(column, weight=1, uniform="control")

        buttons = (
            (0, 0, "Lưu client", self.capture),
            (0, 1, "Mở chọn", self.launch_selected),
            (0, 2, "Mở tất cả", self.launch_all),
            (0, 3, "Dừng chọn", self.stop_selected),
            (0, 4, "Xóa hồ sơ", self.delete_selected),
            (1, 0, "Ẩn/Hiện client", self.toggle_selected_visibility),
            (1, 1, "Độ phân giải", self.configure_display),
            (1, 2, "Chụp ảnh", self.capture_diagnostic),
        )
        for row, column, label, command in buttons:
            ttk.Button(
                controls, text=label, command=command, style="Action.TButton"
            ).grid(row=row, column=column, sticky="ew", padx=4, pady=4)

        # Main workspace: account status on the left, selected account data on the right.
        workspace = ttk.Panedwindow(
            self.content_frame, orient="horizontal", height=self._workspace_height
        )
        workspace.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        account_panel = ttk.Frame(workspace, style="App.TFrame")
        detail_panel = ttk.LabelFrame(
            workspace, text="THÔNG TIN TRONG GAME", padding=14,
            style="Panel.TLabelframe",
        )
        workspace.add(account_panel, weight=3)
        workspace.add(detail_panel, weight=2)

        account_split = ttk.Panedwindow(account_panel, orient="vertical")
        account_split.pack(fill="both", expand=True)
        self.online_tree = self._create_account_tree(account_split, "Tài khoản Online")
        self.offline_tree = self._create_account_tree(account_split, "Tài khoản Offline")
        # Compatibility for the old optional inline-thumbnail worker. The new UI
        # opens Live View in a dedicated window instead of embedding it in a row.
        self.tree = self.online_tree

        title_row = ttk.Frame(detail_panel, style="Detail.TFrame")
        title_row.pack(fill="x", pady=(0, 12))
        self.detail_title = tk.StringVar(value="Chưa chọn tài khoản")
        ttk.Label(
            title_row, textvariable=self.detail_title, style="DetailTitle.TLabel"
        ).pack(side="left")
        ttk.Button(
            title_row, text="Live View", width=11, command=self.preview_selected,
            style="Action.TButton",
        ).pack(side="right")

        fields = (
            ("Tên", "name"), ("Level", "level"), ("Gold", "gold"),
            ("Kim cương", "diamond"), ("Kho 1", "storage_1"),
            ("Kho 2", "storage_2"), ("Kho 3", "storage_3"),
            ("Kho 4", "storage_4"), ("VPSK nâng được", "vpsk"),
            ("Thời gian chạy", "runtime"), ("Lượt bán AUTO", "sales"),
        )
        ttk.Separator(detail_panel, orient="horizontal").pack(fill="x", pady=(0, 8))
        fields_frame = ttk.Frame(detail_panel, style="Detail.TFrame")
        fields_frame.pack(fill="both", expand=True)
        self.detail_vars = {}
        # Two compact field groups keep every in-game value visible without
        # forcing a tall fixed window on 720p/768p desktops.
        split_at = (len(fields) + 1) // 2
        for index, (label, key) in enumerate(fields):
            group = 0 if index < split_at else 1
            row = index if group == 0 else index - split_at
            label_column = group * 2
            value_column = label_column + 1
            ttk.Label(fields_frame, text=label.upper(), style="Key.TLabel").grid(
                row=row, column=label_column, sticky="w",
                padx=(2 if group == 0 else 18, 10), pady=5
            )
            value = tk.StringVar(value="—")
            self.detail_vars[key] = value
            ttk.Label(
                fields_frame, textvariable=value, style="Value.TLabel"
            ).grid(row=row, column=value_column, sticky="w", pady=5)
        fields_frame.columnconfigure(1, weight=1)
        fields_frame.columnconfigure(3, weight=1)

        self._build_auto_panel()

        self.note = tk.StringVar(value="Sẵn sàng")
        ttk.Label(self, textvariable=self.note, style="Status.TLabel").pack(fill="x")

    def _scroll_auto_tabs(self, direction: int) -> None:
        """Move only the center tab strip; navigation arrows stay fixed."""
        self.auto_tabs_canvas.xview_scroll(int(direction) * 4, "units")
        self.after_idle(self._refresh_auto_tab_scroll)

    def _refresh_auto_tab_scroll(self, _event=None) -> None:
        """Keep the scroll bounds and arrow states synchronized with tab width."""
        canvas = getattr(self, "auto_tabs_canvas", None)
        tab_bar = getattr(self, "auto_tabs_window", None)
        if canvas is None or tab_bar is None:
            return
        bbox = canvas.bbox(tab_bar)
        if bbox:
            canvas.configure(scrollregion=bbox)
        first, last = canvas.xview()
        self.auto_tabs_left_button.configure(
            state=("disabled" if first <= 0.001 else "normal"),
            cursor=("arrow" if first <= 0.001 else "hand2"),
        )
        self.auto_tabs_right_button.configure(
            state=("disabled" if last >= 0.999 else "normal"),
            cursor=("arrow" if last >= 0.999 else "hand2"),
        )

    def _make_toggle_button(
        self, parent, label: str, variable: tk.BooleanVar, command=None
    ) -> tk.Button:
        """Create a flat state button used instead of native square checkboxes."""
        button = tk.Button(
            parent, relief="flat", borderwidth=0, highlightthickness=1,
            font=("Segoe UI Semibold", 9), cursor="hand2",
            padx=11, pady=5, anchor="w",
        )

        def redraw(*_args) -> None:
            enabled = bool(variable.get())
            button.configure(
                text=("✓  " if enabled else "＋  ") + label,
                background="#2f80ed" if enabled else "#edf2f8",
                foreground="#ffffff" if enabled else "#34445f",
                activebackground="#246fd0" if enabled else "#dfe8f4",
                activeforeground="#ffffff" if enabled else "#1768c4",
                highlightbackground="#2f80ed" if enabled else "#d5dfec",
                highlightcolor="#2f80ed",
            )

        def toggle() -> None:
            variable.set(not bool(variable.get()))
            if command:
                command()

        button.configure(command=toggle)
        variable.trace_add("write", redraw)
        redraw()
        return button

    def _select_auto_function(self, function_name: str) -> None:
        self.auto_function.set(function_name)
        self._refresh_auto_delete_panel()

    def _build_auto_panel(self) -> None:
        """Build the ClientJS AUTO control surface below the account workspace."""
        # Keep AUTO controls outside the scrollable account workspace so the
        # operator can always start/stop a task on short desktop work areas.
        panel = ttk.LabelFrame(
            self, text="AUTO CLIENTJS", padding=(12, 9), style="Auto.TLabelframe"
        )
        panel.pack(fill="x", padx=12, pady=(5, 7))

        tab_navigation = tk.Frame(panel, background="#ffffff", height=36)
        tab_navigation.pack(fill="x", pady=(0, 8))
        tab_navigation.pack_propagate(False)

        arrow_style = {
            "relief": "flat",
            "borderwidth": 0,
            "highlightthickness": 0,
            "background": "#e8eef7",
            "foreground": "#263653",
            "activebackground": "#dce8f8",
            "activeforeground": "#1768c4",
            "disabledforeground": "#9aa6b8",
            "font": ("Segoe UI Semibold", 12),
            "cursor": "hand2",
            "width": 3,
        }
        self.auto_tabs_left_button = tk.Button(
            tab_navigation, text="‹", command=lambda: self._scroll_auto_tabs(-1),
            **arrow_style,
        )
        self.auto_tabs_left_button.pack(side="left", fill="y")

        self.auto_tabs_canvas = tk.Canvas(
            tab_navigation, background="#ffffff", height=36,
            borderwidth=0, highlightthickness=0,
        )
        self.auto_tabs_canvas.pack(side="left", fill="both", expand=True, padx=3)
        tab_bar = tk.Frame(self.auto_tabs_canvas, background="#ffffff", height=36)
        self.auto_tabs_window = self.auto_tabs_canvas.create_window(
            (0, 0), window=tab_bar, anchor="nw"
        )

        self.auto_tabs_right_button = tk.Button(
            tab_navigation, text="›", command=lambda: self._scroll_auto_tabs(1),
            **arrow_style,
        )
        self.auto_tabs_right_button.pack(side="right", fill="y")
        tab_bar.bind("<Configure>", self._refresh_auto_tab_scroll, add="+")
        self.auto_tabs_canvas.bind(
            "<Configure>", self._refresh_auto_tab_scroll, add="+"
        )
        self.auto_tabs_canvas.bind(
            "<MouseWheel>",
            lambda event: self._scroll_auto_tabs(-1 if event.delta > 0 else 1),
            add="+",
        )

        tab_host = ttk.Frame(panel, style="Detail.TFrame", height=220)
        tab_host.pack(fill="x")
        tab_host.pack_propagate(False)

        feature_tabs = (
            ("main", "Chức năng chính"),
            ("multi_dev", "AUTO MULTI DEV"),
            ("delete_items", "Xóa VP bằng KC"),
            ("summer_spin", "Quay Hề"),
            ("upgrade_storage", "Nâng kho"),
            ("hire_shrimp", "Thuê tôm"),
            ("deliver_sheep", "Giao cừu"),
            ("produce_gems", "Sản xuất ngọc"),
            ("clear_stall", "Dọn quầy"),
            ("clear_stall_designer", "Thiết kế"),
        )
        self.auto_feature_tabs = {}
        self.auto_tab_buttons = {}
        for column, (key, label) in enumerate(feature_tabs):
            button = tk.Button(
                tab_bar, text=label, relief="flat", borderwidth=0,
                highlightthickness=0, background="#e8eef7",
                foreground="#263653", activebackground="#dce8f8",
                activeforeground="#1768c4", font=("Segoe UI Semibold", 9),
                cursor="hand2", padx=6, pady=7,
                command=lambda selected=key: self._show_auto_tab(selected),
            )
            button.pack(
                side="left", fill="y",
                padx=(0 if column == 0 else 3, 0),
            )
            self.auto_tab_buttons[key] = button

            frame = ttk.Frame(tab_host, padding=(4, 7), style="Detail.TFrame")
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            frame.place_forget()
            self.auto_feature_tabs[key] = frame

        multi_dev_tab = self.auto_feature_tabs["multi_dev"]
        multi_dev_header = ttk.Frame(multi_dev_tab, style="Detail.TFrame")
        multi_dev_header.pack(fill="x", padx=8, pady=(4, 0))
        ttk.Label(
            multi_dev_header, text="AUTO MULTI DEV SẠCH",
            style="AutoKey.TLabel",
        ).pack(side="left")
        self.auto_multi_dev_status = tk.StringVar(
            value="Khung AUTO sạch đã sẵn sàng • chuyển từng chức năng có kiểm chứng"
        )
        ttk.Label(
            multi_dev_header, textvariable=self.auto_multi_dev_status,
            style="AutoValue.TLabel", anchor="e",
        ).pack(side="right", fill="x", expand=True, padx=(18, 0))
        ttk.Separator(multi_dev_tab, orient="horizontal").pack(
            fill="x", padx=8, pady=(7, 9)
        )
        clean_body = ttk.Frame(multi_dev_tab, style="Detail.TFrame")
        clean_body.pack(fill="x", padx=8)
        ttk.Label(
            clean_body,
            text="Nền chạy sạch",
            style="AutoKey.TLabel",
        ).grid(row=0, column=0, sticky="w", padx=(0, 26))
        ttk.Label(
            clean_body,
            text="Bridge V3 • EngineDriver • profile cố định",
            style="AutoValue.TLabel",
        ).grid(row=1, column=0, sticky="w", padx=(0, 26), pady=(5, 0))
        ttk.Label(
            clean_body,
            text="Nguồn đối chiếu",
            style="AutoKey.TLabel",
        ).grid(row=0, column=1, sticky="w", padx=(0, 26))
        ttk.Label(
            clean_body,
            text="AUTO PRO gốc • chuyển theo từng chức năng",
            style="AutoValue.TLabel",
        ).grid(row=1, column=1, sticky="w", padx=(0, 26), pady=(5, 0))
        ttk.Label(
            clean_body,
            text="Trạng thái",
            style="AutoKey.TLabel",
        ).grid(row=0, column=2, sticky="w")
        ttk.Label(
            clean_body,
            text="Không sửa profile • chưa thay runtime đang chạy",
            style="AutoValue.TLabel",
        ).grid(row=1, column=2, sticky="w", pady=(5, 0))
        for column in range(3):
            clean_body.columnconfigure(column, weight=1)
        clean_actions = ttk.Frame(multi_dev_tab, style="Detail.TFrame")
        clean_actions.pack(fill="x", padx=8, pady=(16, 0))
        self.auto_multi_dev_start_button = ttk.Button(
            clean_actions, text="▶ Vào game + đóng popup", width=28,
            style="AutoStart.TButton", command=self._start_clean_auto_session,
        )
        self.auto_multi_dev_start_button.pack(side="left", padx=(0, 8))
        self.auto_multi_dev_stop_button = ttk.Button(
            clean_actions, text="■ Dừng AUTO sạch", width=22,
            style="AutoStop.TButton", command=self._stop_clean_auto_session,
        )
        self.auto_multi_dev_stop_button.pack(side="left", padx=(0, 8))
        self.auto_multi_dev_action_log_button = ttk.Button(
            clean_actions, text="≡ Log hành động", width=18,
            style="Action.TButton",
            command=lambda: self._open_clean_main_log("action"),
        )
        self.auto_multi_dev_action_log_button.pack(side="left", padx=(0, 8))
        self.auto_multi_dev_detail_log_button = ttk.Button(
            clean_actions, text="⌕ Log chi tiết", width=18,
            style="Action.TButton",
            command=lambda: self._open_clean_main_log("detail"),
        )
        self.auto_multi_dev_detail_log_button.pack(side="left")

        clean_probe_actions = ttk.Frame(multi_dev_tab, style="Detail.TFrame")
        clean_probe_actions.pack(fill="x", padx=8, pady=(8, 0))
        self.auto_multi_dev_vp_probe_button = ttk.Button(
            clean_probe_actions,
            text="⌕ Kiểm tra nhận diện VP (READ-ONLY)",
            width=36,
            style="Action.TButton",
            command=self._start_clean_vp_recognition_probe,
        )
        self.auto_multi_dev_vp_probe_button.pack(side="left", padx=(0, 8))
        sale_command = getattr(self, "_start_clean_vp_sale", None)
        if sale_command is not None:
            self.auto_multi_dev_vp_sale_button = ttk.Button(
                clean_probe_actions,
                text="▶ Bán VP AUTO",
                width=22,
                style="AutoStart.TButton",
                command=sale_command,
            )
            self.auto_multi_dev_vp_sale_button.pack(side="left", padx=(0, 8))
        plant_command = getattr(self, "_start_clean_rose_plant", None)
        if plant_command is not None:
            self.auto_multi_dev_rose_plant_button = ttk.Button(
                clean_probe_actions,
                text="▶ Trồng 27 Hoa hồng",
                width=22,
                style="AutoStart.TButton",
                command=plant_command,
            )
            self.auto_multi_dev_rose_plant_button.pack(side="left")

        main_tab = self.auto_feature_tabs["main"]
        # These switches map one-to-one to AUTO PRO's legacy option keys.
        # Every launch starts disabled deliberately; selecting a feature is an
        # explicit operator action and no old saved setting can turn it on.
        optional_keys = {
            "delete_items": "Xoa_vp_kc",
            "summer_spin": "auto_quay_he",
            "upgrade_storage": "auto_nang_kho",
            "hire_shrimp": "thue_tom",
            "deliver_sheep": "giao_cu",
            "produce_gems": "san_xuat_ngoc",
        }
        self.auto_optional_features = {
            option_key: tk.BooleanVar(value=False)
            for option_key in optional_keys.values()
        }
        legacy_optional_tabs = {
            "hire_shrimp", "deliver_sheep", "produce_gems"
        }
        for key, label in feature_tabs:
            if key not in legacy_optional_tabs:
                continue
            feature_frame = self.auto_feature_tabs[key]
            option_key = optional_keys[key]
            ttk.Label(
                feature_frame, text=label.upper(), style="AutoKey.TLabel"
            ).pack(anchor="w", padx=8, pady=(5, 0))
            ttk.Separator(feature_frame, orient="horizontal").pack(
                fill="x", padx=8, pady=(7, 8)
            )
            self._make_toggle_button(
                feature_frame, f"Bật {label}",
                self.auto_optional_features[option_key],
            ).pack(anchor="w", padx=8, pady=(2, 5))
            ttk.Label(
                feature_frame,
                text="Mặc định OFF • Chỉ chạy khi được bật trước lúc Bắt đầu.",
                style="AutoValue.TLabel", anchor="w",
            ).pack(fill="x", padx=8)

        clear_stall_tab = self.auto_feature_tabs["clear_stall"]
        clear_stall_header = ttk.Frame(clear_stall_tab, style="Detail.TFrame")
        clear_stall_header.pack(fill="x", padx=8, pady=(3, 0))
        ttk.Label(
            clear_stall_header, text="DỌN QUẦY CLIENTJS",
            style="AutoKey.TLabel",
        ).pack(side="left")
        self.auto_clear_stall_context = tk.StringVar(value="Chọn tài khoản clone")
        ttk.Label(
            clear_stall_header, textvariable=self.auto_clear_stall_context,
            style="AutoValue.TLabel", anchor="e",
        ).pack(side="right", fill="x", expand=True, padx=(18, 0))
        ttk.Separator(clear_stall_tab, orient="horizontal").pack(
            fill="x", padx=8, pady=(6, 6)
        )
        clear_stall_body = ttk.Frame(clear_stall_tab, style="Detail.TFrame")
        clear_stall_body.pack(fill="x", padx=8)
        self.auto_clear_stall_enabled = tk.BooleanVar(value=False)
        self.auto_clear_stall_enabled_button = self._make_toggle_button(
            clear_stall_body, "Bật lịch Dọn quầy",
            self.auto_clear_stall_enabled, self._save_clear_stall_config,
        )
        self.auto_clear_stall_enabled_button.grid(
            row=0, column=0, sticky="w", padx=(0, 12), pady=(0, 6)
        )
        ttk.Label(
            clear_stall_body, text="Số nhà cần duyệt:", style="AutoValue.TLabel"
        ).grid(row=0, column=1, sticky="e", padx=(0, 5), pady=(0, 6))
        self.auto_clear_stall_friend = tk.IntVar(value=1)
        self.auto_clear_stall_friend_spin = ttk.Spinbox(
            clear_stall_body, from_=1, to=500, width=5,
            textvariable=self.auto_clear_stall_friend,
            command=self._save_clear_stall_config,
        )
        self.auto_clear_stall_friend_spin.grid(
            row=0, column=2, sticky="w", padx=(0, 12), pady=(0, 6)
        )
        ttk.Label(
            clear_stall_body, text="Kho VP:", style="AutoValue.TLabel"
        ).grid(row=0, column=3, sticky="e", padx=(0, 5), pady=(0, 6))
        self.auto_clear_stall_stall = tk.IntVar(value=2)
        self.auto_clear_stall_stall_spin = ttk.Spinbox(
            clear_stall_body, from_=1, to=4, width=4,
            textvariable=self.auto_clear_stall_stall,
            command=self._save_clear_stall_config,
        )
        self.auto_clear_stall_stall_spin.grid(
            row=0, column=4, sticky="w", padx=(0, 12), pady=(0, 6)
        )
        ttk.Label(
            clear_stall_body, text="Số lượng mua:", style="AutoValue.TLabel"
        ).grid(row=0, column=5, sticky="e", padx=(0, 5), pady=(0, 6))
        self.auto_clear_stall_quantity = tk.IntVar(value=10)
        self.auto_clear_stall_quantity_spin = ttk.Spinbox(
            clear_stall_body, from_=10, to=1000, increment=10, width=6,
            textvariable=self.auto_clear_stall_quantity,
            command=self._save_clear_stall_config,
        )
        self.auto_clear_stall_quantity_spin.grid(
            row=0, column=6, sticky="w", pady=(0, 6)
        )

        # Compatibility state remains internal; the workflow always scans its
        # verified four views and closes the clone after a successful cycle.
        self.auto_clear_stall_pages = tk.IntVar(value=4)
        self.auto_clear_stall_close = tk.BooleanVar(value=True)
        ttk.Label(
            clear_stall_body, text="Chu kỳ:", style="AutoValue.TLabel"
        ).grid(row=1, column=0, sticky="e", padx=(0, 5), pady=(0, 6))
        self.auto_clear_stall_interval = tk.IntVar(value=65)
        self.auto_clear_stall_interval_spin = ttk.Spinbox(
            clear_stall_body, from_=5, to=1440, width=6,
            textvariable=self.auto_clear_stall_interval,
            command=self._save_clear_stall_config,
        )
        self.auto_clear_stall_interval_spin.grid(
            row=1, column=1, sticky="w", pady=(0, 6)
        )
        ttk.Label(
            clear_stall_body, text="phút", style="AutoValue.TLabel"
        ).grid(row=1, column=2, sticky="w", padx=(4, 10), pady=(0, 6))

        ttk.Label(
            clear_stall_body, text="Chỉ mua VP:", style="AutoValue.TLabel"
        ).grid(row=2, column=0, sticky="e", padx=(0, 5), pady=(0, 6))
        item_row = ttk.Frame(clear_stall_body, style="Detail.TFrame")
        item_row.grid(row=2, column=1, columnspan=6, sticky="w", pady=(0, 6))
        self.auto_clear_stall_items = {}
        self.auto_clear_stall_item_buttons = []
        for item_id, item_label in CLEAR_STALL_ITEM_OPTIONS:
            variable = tk.BooleanVar(value=True)
            button = self._make_toggle_button(
                item_row, item_label, variable, self._save_clear_stall_config
            )
            button.configure(anchor="center", padx=9, pady=4)
            button.pack(side="left", padx=(0, 6))
            self.auto_clear_stall_items[item_id] = variable
            self.auto_clear_stall_item_buttons.append(button)

        action_row = ttk.Frame(clear_stall_body, style="Detail.TFrame")
        action_row.grid(row=3, column=0, columnspan=7, sticky="w")
        self.auto_clear_stall_full_resale_probe_button = ttk.Button(
            action_row,
            text="▶ Bắt đầu Dọn quầy",
            width=25,
            style="AutoStart.TButton",
            command=self._start_clear_stall_full_resale_probe,
        )
        self.auto_clear_stall_full_resale_probe_button.pack(
            side="left", padx=(0, 8)
        )
        # Compatibility anchor for kvtm_multi_entry. This is an alias to the
        # single visible full-action button, not a restored legacy Gate button.
        self.auto_clear_stall_start_button = (
            self.auto_clear_stall_full_resale_probe_button
        )
        self.auto_clear_stall_stop_button = ttk.Button(
            action_row, text="■ Dừng Dọn quầy", width=25,
            style="AutoStop.TButton", command=self._stop_clear_stall,
        )
        self.auto_clear_stall_stop_button.pack(side="left", padx=(0, 8))
        self.auto_clear_stall_queue_button = ttk.Button(
            action_row, text="☷ Danh sách hàng chờ", width=25,
            style="Action.TButton", command=self._show_clear_stall_queue,
        )
        self.auto_clear_stall_queue_button.pack(side="left", padx=(0, 8))
        self.auto_clear_stall_log_button = ttk.Button(
            action_row, text="≡ Log Dọn quầy", width=25,
            style="Action.TButton", command=self._show_clear_stall_log,
        )
        self.auto_clear_stall_log_button.pack(side="left")
        for widget in (
            self.auto_clear_stall_friend_spin,
            self.auto_clear_stall_stall_spin,
            self.auto_clear_stall_quantity_spin,
            self.auto_clear_stall_interval_spin,
        ):
            widget.bind(
                "<FocusOut>", lambda _event: self._save_clear_stall_config(), add="+"
            )
            widget.bind(
                "<Return>", lambda _event: self._save_clear_stall_config(), add="+"
            )
        self.auto_clear_stall_status = tk.StringVar(
            value="Dọn quầy DEV • mua đủ, thu vàng và treo lại đúng VP"
        )
        ttk.Label(
            clear_stall_tab, textvariable=self.auto_clear_stall_status,
            style="AutoValue.TLabel", anchor="w",
        ).pack(fill="x", padx=8, pady=(7, 0))
        self._clear_stall_refreshing = False

        nang_kho_tab = self.auto_feature_tabs["upgrade_storage"]
        nang_kho_header = ttk.Frame(nang_kho_tab, style="Detail.TFrame")
        nang_kho_header.pack(fill="x", padx=8, pady=(3, 0))
        ttk.Label(
            nang_kho_header, text="TỰ ĐỘNG NÂNG KHO", style="AutoKey.TLabel"
        ).pack(side="left")
        self.auto_nang_kho_context = tk.StringVar(value="Chọn tài khoản để cấu hình")
        ttk.Label(
            nang_kho_header, textvariable=self.auto_nang_kho_context,
            style="AutoValue.TLabel", anchor="e",
        ).pack(side="right", fill="x", expand=True, padx=(18, 0))
        ttk.Separator(nang_kho_tab, orient="horizontal").pack(
            fill="x", padx=8, pady=(6, 6)
        )
        nang_kho_body = ttk.Frame(nang_kho_tab, style="Detail.TFrame")
        nang_kho_body.pack(fill="x", padx=8)
        self.auto_nang_kho_enabled = tk.BooleanVar(value=False)
        self.auto_nang_kho_enabled_button = self._make_toggle_button(
            nang_kho_body, "Bật tự động Nâng kho",
            self.auto_nang_kho_enabled, self._save_auto_nang_kho_config,
        )
        self.auto_nang_kho_enabled_button.grid(
            row=0, column=0, sticky="w", padx=(0, 12), pady=(0, 6)
        )
        self.auto_nang_kho_type = tk.StringVar(value="Kho 1 & 2")
        self.auto_nang_kho_type_buttons = {}
        type_box = ttk.Frame(nang_kho_body, style="Detail.TFrame")
        type_box.grid(row=0, column=1, columnspan=4, sticky="w", pady=(0, 6))
        for column, kho_type in enumerate(("Kho 1", "Kho 2", "Kho 1 & 2", "Max Kho")):
            button = tk.Button(
                type_box, text=kho_type, relief="flat", borderwidth=0,
                highlightthickness=1, font=("Segoe UI Semibold", 9),
                cursor="hand2", padx=10, pady=5,
                command=lambda value=kho_type: self._select_auto_nang_kho_type(value),
            )
            button.grid(row=0, column=column, padx=(0, 4))
            self.auto_nang_kho_type_buttons[kho_type] = button
        ttk.Label(
            nang_kho_body, text="Kiểm tra lại sau (giờ):",
            style="AutoValue.TLabel",
        ).grid(row=1, column=0, sticky="w", padx=(0, 8))
        self.auto_nang_kho_hours = tk.IntVar(value=2)
        self.auto_nang_kho_hours_spin = ttk.Spinbox(
            nang_kho_body, from_=1, to=168, width=6,
            textvariable=self.auto_nang_kho_hours,
            command=self._save_auto_nang_kho_config,
        )
        self.auto_nang_kho_hours_spin.grid(row=1, column=1, sticky="w", padx=(0, 12))
        self.auto_nang_kho_balance = tk.BooleanVar(value=True)
        self.auto_nang_kho_balance_button = self._make_toggle_button(
            nang_kho_body, "Cân bằng VP nâng kho",
            self.auto_nang_kho_balance, self._save_auto_nang_kho_config,
        )
        self.auto_nang_kho_balance_button.grid(
            row=1, column=2, sticky="w", padx=(0, 8)
        )
        self.auto_nang_kho_kc = tk.BooleanVar(value=False)
        self.auto_nang_kho_kc_button = self._make_toggle_button(
            nang_kho_body, "Dùng KC khi full quầy",
            self.auto_nang_kho_kc, self._save_auto_nang_kho_config,
        )
        self.auto_nang_kho_kc_button.grid(row=1, column=3, sticky="w")
        self.auto_nang_kho_note = tk.StringVar(
            value="Mặc định OFF • KC chỉ dùng khi bạn chủ động bật."
        )
        ttk.Label(
            nang_kho_tab, textvariable=self.auto_nang_kho_note,
            style="AutoValue.TLabel", anchor="w",
        ).pack(fill="x", padx=8, pady=(5, 0))
        self._auto_nang_kho_refreshing = False
        self._redraw_auto_nang_kho_types()

        quay_he_tab = self.auto_feature_tabs["summer_spin"]
        quay_he_header = ttk.Frame(quay_he_tab, style="Detail.TFrame")
        quay_he_header.pack(fill="x", padx=8, pady=(4, 0))
        ttk.Label(
            quay_he_header, text="TỰ ĐỘNG QUAY HỀ", style="AutoKey.TLabel"
        ).pack(side="left")
        self.auto_quay_he_context = tk.StringVar(value="Chọn tài khoản để cấu hình")
        ttk.Label(
            quay_he_header, textvariable=self.auto_quay_he_context,
            style="AutoValue.TLabel", anchor="e",
        ).pack(side="right", fill="x", expand=True, padx=(18, 0))
        ttk.Separator(quay_he_tab, orient="horizontal").pack(
            fill="x", padx=8, pady=(7, 7)
        )
        quay_he_body = ttk.Frame(quay_he_tab, style="Detail.TFrame")
        quay_he_body.pack(fill="x", padx=8)
        self.auto_quay_he_enabled = tk.BooleanVar(value=False)
        self.auto_quay_he_enabled_button = self._make_toggle_button(
            quay_he_body, "Bật tự động Quay Hề",
            self.auto_quay_he_enabled,
            self._save_auto_quay_he_config,
        )
        self.auto_quay_he_enabled_button.pack(side="left", padx=(0, 30))
        ttk.Label(
            quay_he_body, text="Số lượt quay:", style="AutoValue.TLabel"
        ).pack(side="left", padx=(0, 8))
        self.auto_quay_he_count = tk.IntVar(value=1)
        self.auto_quay_he_count_spin = ttk.Spinbox(
            quay_he_body, from_=1, to=100, width=7,
            textvariable=self.auto_quay_he_count,
            command=self._save_auto_quay_he_config,
        )
        self.auto_quay_he_count_spin.pack(side="left")
        self.auto_quay_he_count_spin.bind(
            "<FocusOut>", lambda _event: self._save_auto_quay_he_config(), add="+"
        )
        self.auto_quay_he_count_spin.bind(
            "<Return>", lambda _event: self._save_auto_quay_he_config(), add="+"
        )
        self.auto_quay_he_note = tk.StringVar(
            value="Mặc định OFF • 1 lượt là lượt quay miễn phí • Không quay bằng KC."
        )
        ttk.Label(
            quay_he_tab, textvariable=self.auto_quay_he_note,
            style="AutoValue.TLabel", anchor="w",
        ).pack(fill="x", padx=8, pady=(9, 0))
        self._auto_quay_he_refreshing = False

        delete_tab = self.auto_feature_tabs["delete_items"]
        delete_header = ttk.Frame(delete_tab, style="Detail.TFrame")
        delete_header.pack(fill="x", padx=8, pady=(4, 0))
        ttk.Label(
            delete_header, text="XÓA VẬT PHẨM BẰNG KC",
            style="AutoKey.TLabel",
        ).pack(side="left")
        self.auto_delete_context = tk.StringVar(
            value="Chọn tài khoản và chức năng AUTO để cấu hình"
        )
        ttk.Label(
            delete_header, textvariable=self.auto_delete_context,
            style="AutoValue.TLabel", anchor="e",
        ).pack(side="right", fill="x", expand=True, padx=(18, 0))
        ttk.Separator(delete_tab, orient="horizontal").pack(
            fill="x", padx=8, pady=(7, 7)
        )
        delete_body = ttk.Frame(delete_tab, style="Detail.TFrame")
        delete_body.pack(fill="x", padx=8)
        self.auto_delete_enabled = tk.BooleanVar(value=False)
        self.auto_delete_enabled_button = self._make_toggle_button(
            delete_body, "Bật Xóa VP bằng KC",
            self.auto_delete_enabled,
            self._save_auto_delete_config,
        )
        self.auto_delete_enabled_button.pack(side="left", anchor="n", padx=(0, 24))
        self.auto_delete_items_frame = ttk.Frame(
            delete_body, style="Detail.TFrame"
        )
        self.auto_delete_items_frame.pack(side="left", fill="x", expand=True)
        self.auto_delete_item_vars = {}
        self._auto_delete_refreshing = False
        self.auto_delete_note = tk.StringVar(
            value="Mặc định OFF • Không chọn VP = xóa tất cả VP của chức năng."
        )
        ttk.Label(
            delete_tab, textvariable=self.auto_delete_note,
            style="AutoValue.TLabel", anchor="w",
        ).pack(fill="x", padx=8, pady=(7, 0))

        designer_tab = self.auto_feature_tabs["clear_stall_designer"]
        try:
            from clear_stall_designer import build_clear_stall_designer
            self.clear_stall_designer = build_clear_stall_designer(
                designer_tab, APP_DIR, TOOL_DIR
            )
        except Exception as exc:
            ttk.Label(
                designer_tab,
                text=f"Không mở được trình thiết kế Dọn quầy: {exc}",
                foreground="#b42318",
            ).pack(anchor="w", padx=8, pady=8)

        self._show_auto_tab("main")

        main_tab.columnconfigure(0, weight=4)
        main_tab.columnconfigure(1, weight=3)
        main_tab.columnconfigure(2, weight=2)

        function_box = ttk.Frame(main_tab, style="Detail.TFrame")
        function_box.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        ttk.Label(function_box, text="CHỨC NĂNG", style="AutoKey.TLabel").pack(anchor="w")
        self.auto_function = tk.StringVar(value=self._auto_function_names[0])
        self.auto_function_button = tk.Menubutton(
            function_box, textvariable=self.auto_function,
            background="#ffffff", foreground="#263653",
            activebackground="#e8f1ff", activeforeground="#1768c4",
            relief="flat", borderwidth=0, highlightthickness=1,
            highlightbackground="#c7d3e3", highlightcolor="#2f80ed",
            font=("Segoe UI Semibold", 10), anchor="w",
            cursor="hand2", padx=11, pady=7, indicatoron=True,
        )
        function_menu = tk.Menu(
            self.auto_function_button, tearoff=False,
            background="#ffffff", foreground="#263653",
            activebackground="#2f80ed", activeforeground="#ffffff",
            relief="flat", borderwidth=1, font=("Segoe UI", 10),
        )
        for function_name in self._auto_function_names:
            function_menu.add_command(
                label=function_name,
                command=lambda selected=function_name: self._select_auto_function(selected),
            )
        self.auto_function_button.configure(menu=function_menu)
        self.auto_function_button.pack(fill="x", pady=(4, 0))

        target_box = ttk.Frame(main_tab, style="Detail.TFrame")
        target_box.grid(row=0, column=1, sticky="ew", padx=(0, 12))
        ttk.Label(target_box, text="TÀI KHOẢN ÁP DỤNG", style="AutoKey.TLabel").pack(anchor="w")
        self.auto_target = tk.StringVar(value="Chưa chọn tài khoản")
        ttk.Label(
            target_box, textvariable=self.auto_target, style="AutoValue.TLabel",
            anchor="w",
        ).pack(fill="x", pady=(7, 0))

        state_box = ttk.Frame(main_tab, style="Detail.TFrame")
        state_box.grid(row=0, column=2, sticky="ew")
        ttk.Label(state_box, text="TRẠNG THÁI", style="AutoKey.TLabel").pack(anchor="w")
        self.auto_status = tk.StringVar(value="Sẵn sàng")
        ttk.Label(
            state_box, textvariable=self.auto_status, style="AutoValue.TLabel",
            anchor="w",
        ).pack(fill="x", pady=(7, 0))

        # Worker progress values remain internal; the visual progress box was removed.
        self.auto_progress_text = tk.StringVar(value="0%")
        self.auto_progress = tk.DoubleVar(value=0.0)

        quick_options = ttk.Frame(main_tab, style="Detail.TFrame")
        quick_options.grid(
            row=1, column=0, columnspan=3, sticky="ew", pady=(9, 0)
        )
        self.auto_quick_options = {
            "open_chests": tk.BooleanVar(value=False),
            "produce_feed": tk.BooleanVar(value=False),
            "sell_all_scratch_items": tk.BooleanVar(value=False),
        }
        for column, (key, label) in enumerate((
            ("open_chests", "Mở rương"),
            ("produce_feed", "Sản xuất cám"),
            ("sell_all_scratch_items", "Bán hết VP cào"),
        )):
            self._make_toggle_button(
                quick_options, label, self.auto_quick_options[key]
            ).grid(row=0, column=column, sticky="w", padx=(0, 8))

        action_row = ttk.Frame(main_tab, style="Detail.TFrame")
        action_row.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self.auto_start_button = ttk.Button(
            action_row, text="▶ Bắt đầu", command=self._auto_ui_start,
            style="AutoStart.TButton",
        )
        self.auto_start_button.pack(side="left")
        ttk.Button(
            action_row, text="Ⅱ Tạm dừng", command=self._auto_ui_pause,
            style="Action.TButton",
        ).pack(side="left", padx=(7, 0))
        ttk.Button(
            action_row, text="■ Dừng", command=self._auto_ui_stop,
            style="AutoStop.TButton",
        ).pack(side="left", padx=(7, 0))
        ttk.Button(
            action_row, text="Cấu hình", command=self._auto_ui_configure,
            style="Action.TButton",
        ).pack(side="left", padx=(7, 0))

        self.auto_scope_note = tk.StringVar(
            value="Engine chưa được kết nối • UI sẵn sàng cho bước tích hợp AUTO PRO"
        )
        ttk.Label(
            action_row, textvariable=self.auto_scope_note, style="Key.TLabel",
            anchor="e",
        ).pack(side="right", fill="x", expand=True, padx=(14, 0))

    def _collect_auto_tuning(self) -> dict:
        tuning = self.settings.get("auto_tuning", {})
        return {
            key: tuning.get(key, default)
            for key, default in DEFAULT_AUTO_TUNING.items()
        }

    def _clear_stall_profile(self) -> tuple[str | None, dict | None]:
        profile_id = self._active_profile_id
        if not profile_id:
            ids = self.selected_ids()
            profile_id = ids[0] if len(ids) == 1 else None
        profile = next(
            (p for p in self.profiles if p.get("id") == profile_id), None
        )
        return profile_id, profile

    def _refresh_clear_stall_panel(self) -> None:
        if not hasattr(self, "auto_clear_stall_enabled_button"):
            return
        self._clear_stall_refreshing = True
        try:
            profile_id, profile = self._clear_stall_profile()
            state = "normal" if profile else "disabled"
            for widget in (
                self.auto_clear_stall_enabled_button,
                self.auto_clear_stall_friend_spin,
                self.auto_clear_stall_stall_spin,
                self.auto_clear_stall_quantity_spin,
                self.auto_clear_stall_interval_spin,
                self.auto_clear_stall_full_resale_probe_button,
                self.auto_clear_stall_stop_button,
            ):
                widget.configure(state=state)
            for widget in self.auto_clear_stall_item_buttons:
                widget.configure(state=state)
            if not profile:
                self.auto_clear_stall_enabled.set(False)
                self.auto_clear_stall_friend.set(1)
                self.auto_clear_stall_stall.set(2)
                self.auto_clear_stall_quantity.set(10)
                self.auto_clear_stall_pages.set(4)
                self.auto_clear_stall_interval.set(65)
                self.auto_clear_stall_close.set(True)
                for item_id, _label in CLEAR_STALL_ITEM_OPTIONS:
                    self.auto_clear_stall_items[item_id].set(True)
                self.auto_clear_stall_context.set("Chọn tài khoản clone")
                self.auto_clear_stall_status.set(
                    "Dọn quầy DEV • mua đủ, thu vàng và treo lại đúng VP"
                )
                return
            jobs = self.settings.setdefault("clear_stall_jobs", {})
            saved = jobs.get(profile_id, {})
            if not isinstance(saved, dict):
                saved = {}
            def bounded(key, default, minimum, maximum):
                try:
                    return max(minimum, min(maximum, int(saved.get(key, default))))
                except (TypeError, ValueError):
                    return default
            self.auto_clear_stall_enabled.set(bool(saved.get("enabled", False)))
            self.auto_clear_stall_friend.set(
                bounded("target_friend_ordinal", 1, 1, 7)
            )
            self.auto_clear_stall_stall.set(bounded("target_stall_id", 2, 1, 4))
            self.auto_clear_stall_quantity.set(bounded("buy_quantity", 10, 10, 1000))
            self.auto_clear_stall_pages.set(4)
            self.auto_clear_stall_interval.set(
                bounded("interval_minutes", 65, 5, 1440)
            )
            self.auto_clear_stall_close.set(True)
            allowed_items = saved.get(
                "allowed_item_ids",
                [item_id for item_id, _label in CLEAR_STALL_ITEM_OPTIONS],
            )
            if not isinstance(allowed_items, list):
                allowed_items = [item_id for item_id, _label in CLEAR_STALL_ITEM_OPTIONS]
            allowed_set = {str(item) for item in allowed_items}
            for item_id, _label in CLEAR_STALL_ITEM_OPTIONS:
                self.auto_clear_stall_items[item_id].set(item_id in allowed_set)
            self.auto_clear_stall_context.set(
                f"Clone: {profile.get('name') or profile_id}"
            )
            worker = self._clear_stall_workers.get(profile_id)
            if worker and worker.poll() is None:
                self.auto_clear_stall_status.set(
                    str(saved.get("last_checkpoint") or "Dọn quầy đang chạy")
                )
                return
            next_run = float(saved.get("next_run_at", 0) or 0)
            if bool(saved.get("enabled", False)) and next_run > 0:
                next_text = time.strftime("%d/%m %H:%M:%S", time.localtime(next_run))
                self.auto_clear_stall_status.set(
                    f"Sẵn sàng chạy ngay • Lịch tiếp theo {next_text}"
                )
            else:
                self.auto_clear_stall_status.set(
                    "Sẵn sàng Dọn quầy • mua đủ, thu vàng và treo lại đúng VP"
                )
        finally:
            self._clear_stall_refreshing = False

    def _save_clear_stall_config(self) -> None:
        if getattr(self, "_clear_stall_refreshing", False):
            return
        profile_id, profile = self._clear_stall_profile()
        if not profile_id or not profile:
            return
        try:
            friend = max(1, min(500, int(self.auto_clear_stall_friend.get())))
            stall = max(1, min(4, int(self.auto_clear_stall_stall.get())))
            quantity = max(10, min(1000, int(self.auto_clear_stall_quantity.get())))
            quantity = max(10, (quantity // 10) * 10)
            pages = 4
            interval = max(5, min(1440, int(self.auto_clear_stall_interval.get())))
        except (tk.TclError, TypeError, ValueError):
            friend, stall, quantity, pages, interval = 1, 2, 10, 10, 65
        self.auto_clear_stall_friend.set(friend)
        self.auto_clear_stall_stall.set(stall)
        self.auto_clear_stall_quantity.set(quantity)
        self.auto_clear_stall_pages.set(pages)
        self.auto_clear_stall_interval.set(interval)
        allowed_items = [
            item_id
            for item_id, _label in CLEAR_STALL_ITEM_OPTIONS
            if bool(self.auto_clear_stall_items[item_id].get())
        ]
        if not allowed_items:
            first_item = CLEAR_STALL_ITEM_OPTIONS[0][0]
            self.auto_clear_stall_items[first_item].set(True)
            allowed_items = [first_item]
            self.auto_clear_stall_status.set(
                "Phải chọn ít nhất một VP • đã giữ Nước hoa hồng"
            )
        jobs = self.settings.setdefault("clear_stall_jobs", {})
        previous = jobs.get(profile_id, {})
        if not isinstance(previous, dict):
            previous = {}
        enabled = bool(self.auto_clear_stall_enabled.get())
        previous_enabled = bool(previous.get("enabled", False))
        try:
            next_run = float(previous.get("next_run_at", 0) or 0)
        except (TypeError, ValueError):
            next_run = 0
        if enabled and (not previous_enabled or next_run <= 0):
            next_run = time.time() + interval * 60
        elif not enabled:
            next_run = 0
        jobs[profile_id] = {
            "schema_version": 2,
            "job_id": str(previous.get("job_id") or f"clear-stall-{profile_id}"),
            "clone_profile_id": profile_id,
            "target_mode": "friend_ordinal",
            "target_friend_ordinal": friend,
            "target_stall_id": stall,
            "buy_quantity": quantity,
            "max_scan_pages": pages,
            "interval_minutes": interval,
            "next_run_at": next_run,
            "close_client_after_run": True,
            "allowed_item_ids": allowed_items,
            "enabled": enabled,
            "last_checkpoint": str(previous.get("last_checkpoint") or "WAITING"),
            "last_result": previous.get("last_result"),
        }
        save_settings(self.settings)
        self.auto_clear_stall_status.set(
            "Đã lưu • Có thể bấm Bắt đầu để chạy ngay"
        )

    def _redraw_auto_nang_kho_types(self) -> None:
        selected = self.auto_nang_kho_type.get()
        for value, button in self.auto_nang_kho_type_buttons.items():
            active = value == selected
            button.configure(
                background="#2f80ed" if active else "#edf2f8",
                foreground="#ffffff" if active else "#34445f",
                activebackground="#246fd0" if active else "#dfe8f4",
                activeforeground="#ffffff" if active else "#1768c4",
                highlightbackground="#2f80ed" if active else "#d5dfec",
                highlightcolor="#2f80ed",
            )

    def _select_auto_nang_kho_type(self, value: str) -> None:
        if value not in {"Kho 1", "Kho 2", "Kho 1 & 2", "Max Kho"}:
            return
        self.auto_nang_kho_type.set(value)
        self._redraw_auto_nang_kho_types()
        self._save_auto_nang_kho_config()

    def _refresh_auto_nang_kho_panel(self) -> None:
        if not hasattr(self, "auto_nang_kho_enabled_button"):
            return
        self._auto_nang_kho_refreshing = True
        try:
            profile_id = self._active_profile_id
            if not profile_id:
                ids = self.selected_ids()
                profile_id = ids[0] if len(ids) == 1 else None
            profile = next(
                (p for p in self.profiles if p.get("id") == profile_id), None
            )
            state = "normal" if profile else "disabled"
            for widget in (
                self.auto_nang_kho_enabled_button,
                self.auto_nang_kho_hours_spin,
                self.auto_nang_kho_balance_button,
                self.auto_nang_kho_kc_button,
                *self.auto_nang_kho_type_buttons.values(),
            ):
                widget.configure(state=state)
            if not profile:
                self.auto_nang_kho_enabled.set(False)
                self.auto_nang_kho_type.set("Kho 1 & 2")
                self.auto_nang_kho_hours.set(2)
                self.auto_nang_kho_balance.set(True)
                self.auto_nang_kho_kc.set(False)
                self.auto_nang_kho_context.set("Chọn tài khoản để cấu hình")
                self._redraw_auto_nang_kho_types()
                return
            profiles_cfg = self.settings.setdefault("auto_nang_kho_profiles", {})
            saved_cfg = profiles_cfg.get(profile_id, {})
            if not isinstance(saved_cfg, dict):
                saved_cfg = {}
            kho_type = str(saved_cfg.get("type", "Kho 1 & 2"))
            if kho_type not in {"Kho 1", "Kho 2", "Kho 1 & 2", "Max Kho"}:
                kho_type = "Kho 1 & 2"
            try:
                hours = max(1, min(168, int(saved_cfg.get("hours", 2))))
            except (TypeError, ValueError):
                hours = 2
            self.auto_nang_kho_enabled.set(bool(saved_cfg.get("enabled", False)))
            self.auto_nang_kho_type.set(kho_type)
            self.auto_nang_kho_hours.set(hours)
            self.auto_nang_kho_balance.set(bool(saved_cfg.get("balance", True)))
            self.auto_nang_kho_kc.set(bool(saved_cfg.get("use_kc", False)))
            self.auto_nang_kho_context.set(str(profile.get("name") or profile_id))
            self.auto_nang_kho_note.set(
                "Mặc định OFF • KC chỉ dùng khi bạn chủ động bật."
            )
            self._redraw_auto_nang_kho_types()
        finally:
            self._auto_nang_kho_refreshing = False

    def _save_auto_nang_kho_config(self) -> None:
        if getattr(self, "_auto_nang_kho_refreshing", False):
            return
        profile_id = self._active_profile_id
        if not profile_id:
            ids = self.selected_ids()
            profile_id = ids[0] if len(ids) == 1 else None
        if not profile_id:
            return
        try:
            hours = max(1, min(168, int(self.auto_nang_kho_hours.get())))
        except (tk.TclError, TypeError, ValueError):
            hours = 2
        self.auto_nang_kho_hours.set(hours)
        profiles_cfg = self.settings.setdefault("auto_nang_kho_profiles", {})
        profiles_cfg[profile_id] = {
            "enabled": bool(self.auto_nang_kho_enabled.get()),
            "type": self.auto_nang_kho_type.get(),
            "hours": hours,
            "balance": bool(self.auto_nang_kho_balance.get()),
            "use_kc": bool(self.auto_nang_kho_kc.get()),
        }
        save_settings(self.settings)
        self.auto_nang_kho_note.set(
            f"Đã lưu riêng • {self.auto_nang_kho_type.get()} • kiểm tra sau {hours} giờ"
        )

    def _refresh_auto_quay_he_panel(self) -> None:
        if not hasattr(self, "auto_quay_he_enabled_button"):
            return
        self._auto_quay_he_refreshing = True
        try:
            profile_id = self._active_profile_id
            if not profile_id:
                ids = self.selected_ids()
                profile_id = ids[0] if len(ids) == 1 else None
            profile = next(
                (p for p in self.profiles if p.get("id") == profile_id), None
            )
            state = "normal" if profile else "disabled"
            self.auto_quay_he_enabled_button.configure(state=state)
            self.auto_quay_he_count_spin.configure(state=state)
            if not profile:
                self.auto_quay_he_enabled.set(False)
                self.auto_quay_he_count.set(1)
                self.auto_quay_he_context.set("Chọn tài khoản để cấu hình")
                return
            profiles_cfg = self.settings.setdefault("auto_quay_he_profiles", {})
            saved_cfg = profiles_cfg.get(profile_id, {})
            if not isinstance(saved_cfg, dict):
                saved_cfg = {}
            try:
                count = max(1, min(100, int(saved_cfg.get("count", 1))))
            except (TypeError, ValueError):
                count = 1
            self.auto_quay_he_enabled.set(bool(saved_cfg.get("enabled", False)))
            self.auto_quay_he_count.set(count)
            self.auto_quay_he_context.set(str(profile.get("name") or profile_id))
            self.auto_quay_he_note.set(
                "Mặc định OFF • 1 lượt là lượt quay miễn phí • Không quay bằng KC."
            )
        finally:
            self._auto_quay_he_refreshing = False

    def _save_auto_quay_he_config(self) -> None:
        if getattr(self, "_auto_quay_he_refreshing", False):
            return
        profile_id = self._active_profile_id
        if not profile_id:
            ids = self.selected_ids()
            profile_id = ids[0] if len(ids) == 1 else None
        if not profile_id:
            return
        try:
            count = max(1, min(100, int(self.auto_quay_he_count.get())))
        except (tk.TclError, TypeError, ValueError):
            count = 1
        self.auto_quay_he_count.set(count)
        profiles_cfg = self.settings.setdefault("auto_quay_he_profiles", {})
        profiles_cfg[profile_id] = {
            "enabled": bool(self.auto_quay_he_enabled.get()),
            "count": count,
        }
        save_settings(self.settings)
        self.auto_quay_he_note.set(
            f"Đã lưu riêng cho tài khoản này • {count} lượt • Không quay bằng KC."
        )

    def _delete_config_context(self) -> tuple[str | None, dict | None]:
        profile_id = self._active_profile_id
        if not profile_id:
            ids = self.selected_ids()
            profile_id = ids[0] if len(ids) == 1 else None
        function_spec = self._auto_functions_by_label.get(self.auto_function.get())
        return profile_id, function_spec

    def _refresh_auto_delete_panel(self) -> None:
        if not hasattr(self, "auto_delete_items_frame"):
            return
        self._auto_delete_refreshing = True
        try:
            for widget in self.auto_delete_items_frame.winfo_children():
                widget.destroy()
            self.auto_delete_item_vars = {}
            profile_id, function_spec = self._delete_config_context()
            profile = next(
                (p for p in self.profiles if p.get("id") == profile_id), None
            )
            items = list((function_spec or {}).get("delete_items") or [])
            valid = bool(profile and function_spec and items)
            self.auto_delete_enabled_button.configure(
                state="normal" if valid else "disabled"
            )
            if not valid:
                self.auto_delete_enabled.set(False)
                self.auto_delete_context.set(
                    "Chọn tài khoản và chức năng AUTO để cấu hình"
                )
                ttk.Label(
                    self.auto_delete_items_frame,
                    text="Chưa có danh sách vật phẩm phù hợp.",
                    style="AutoValue.TLabel",
                ).pack(anchor="w")
                return
            function_key = str(function_spec.get("key") or "")
            profiles_cfg = self.settings.setdefault("auto_delete_profiles", {})
            profile_cfg = profiles_cfg.get(profile_id, {})
            saved_cfg = profile_cfg.get(function_key, {})
            if not isinstance(saved_cfg, dict):
                saved_cfg = {}
            selected = {
                str(item) for item in saved_cfg.get("items", [])
                if str(item) in items
            }
            self.auto_delete_enabled.set(bool(saved_cfg.get("enabled", False)))
            self.auto_delete_context.set(
                f"{profile.get('name') or profile_id} • {function_spec.get('label')}"
            )
            for item in items:
                variable = tk.BooleanVar(value=item in selected)
                self.auto_delete_item_vars[item] = variable
                self._make_toggle_button(
                    self.auto_delete_items_frame, item, variable,
                    self._save_auto_delete_config,
                ).pack(side="left", padx=(0, 8))
            self.auto_delete_note.set(
                "Mặc định OFF • Không chọn VP = xóa tất cả VP của chức năng."
            )
        finally:
            self._auto_delete_refreshing = False

    def _save_auto_delete_config(self) -> None:
        if getattr(self, "_auto_delete_refreshing", False):
            return
        profile_id, function_spec = self._delete_config_context()
        if not profile_id or not function_spec:
            return
        function_key = str(function_spec.get("key") or "")
        items = [
            item for item, variable in self.auto_delete_item_vars.items()
            if bool(variable.get())
        ]
        profiles_cfg = self.settings.setdefault("auto_delete_profiles", {})
        profile_cfg = profiles_cfg.setdefault(profile_id, {})
        profile_cfg[function_key] = {
            "enabled": bool(self.auto_delete_enabled.get()),
            "items": items,
        }
        save_settings(self.settings)
        self.auto_delete_note.set(
            "Đã lưu riêng cho tài khoản này • Không chọn VP = xóa tất cả."
        )

    def _collect_auto_options(
        self, profile_id: str | None = None, function_spec: dict | None = None
    ) -> dict:
        """Build legacy options and translate selected delete targets to skip_items."""
        options = {
            "Xoa_vp_kc": False,
            "open_chest": False,
            "auto_quay_he": False,
            "quay_he_count": 1,
            "auto_nang_kho": False,
            "auto_nang_kho_type": "Kho 1 & 2",
            "auto_nang_kho_time_hours": 2,
            "auto_nang_kho_balance": True,
            "kc_nang_kho": False,
            "thue_tom": False,
            "giao_cu": False,
            "san_xuat_ngoc": False,
            "sx_event_cam": False,
            "sell_all": False,
            "skip_items": [],
        }
        quick_map = {
            "open_chests": "open_chest",
            "produce_feed": "sx_event_cam",
            "sell_all_scratch_items": "sell_all",
        }
        for ui_key, option_key in quick_map.items():
            variable = getattr(self, "auto_quick_options", {}).get(ui_key)
            options[option_key] = bool(variable.get()) if variable else False
        for option_key, variable in getattr(
            self, "auto_optional_features", {}
        ).items():
            if option_key not in {"Xoa_vp_kc", "auto_quay_he", "auto_nang_kho"}:
                options[option_key] = bool(variable.get())

        if profile_id:
            profiles_cfg = self.settings.get("auto_quay_he_profiles", {})
            saved_cfg = (
                profiles_cfg.get(profile_id, {})
                if isinstance(profiles_cfg, dict) else {}
            )
            if isinstance(saved_cfg, dict):
                try:
                    count = max(1, min(100, int(saved_cfg.get("count", 1))))
                except (TypeError, ValueError):
                    count = 1
                options["auto_quay_he"] = bool(saved_cfg.get("enabled", False))
                options["quay_he_count"] = count

        if profile_id:
            profiles_cfg = self.settings.get("auto_nang_kho_profiles", {})
            saved_cfg = (
                profiles_cfg.get(profile_id, {})
                if isinstance(profiles_cfg, dict) else {}
            )
            if isinstance(saved_cfg, dict):
                kho_type = str(saved_cfg.get("type", "Kho 1 & 2"))
                if kho_type not in {"Kho 1", "Kho 2", "Kho 1 & 2", "Max Kho"}:
                    kho_type = "Kho 1 & 2"
                try:
                    hours = max(1, min(168, int(saved_cfg.get("hours", 2))))
                except (TypeError, ValueError):
                    hours = 2
                options["auto_nang_kho"] = bool(saved_cfg.get("enabled", False))
                options["auto_nang_kho_type"] = kho_type
                options["auto_nang_kho_time_hours"] = hours
                options["auto_nang_kho_balance"] = bool(
                    saved_cfg.get("balance", True)
                )
                options["kc_nang_kho"] = bool(saved_cfg.get("use_kc", False))

        if profile_id and function_spec:
            function_key = str(function_spec.get("key") or "")
            allowed_items = [
                str(item) for item in function_spec.get("delete_items", [])
            ]
            profiles_cfg = self.settings.get("auto_delete_profiles", {})
            profile_cfg = (
                profiles_cfg.get(profile_id, {})
                if isinstance(profiles_cfg, dict) else {}
            )
            saved_cfg = (
                profile_cfg.get(function_key, {})
                if isinstance(profile_cfg, dict) else {}
            )
            if isinstance(saved_cfg, dict):
                enabled = bool(saved_cfg.get("enabled", False))
                selected = {
                    str(item) for item in saved_cfg.get("items", [])
                    if str(item) in allowed_items
                }
                options["Xoa_vp_kc"] = enabled
                if enabled and selected:
                    options["skip_items"] = [
                        item for item in allowed_items if item not in selected
                    ]
        return options

    def _show_auto_tab(self, selected: str) -> None:
        """Switch flat AUTO feature buttons without native Windows tab chrome."""
        frames = getattr(self, "auto_feature_tabs", {})
        buttons = getattr(self, "auto_tab_buttons", {})
        if selected not in frames:
            selected = "main"
        for key, frame in frames.items():
            if key == selected:
                frame.place(relx=0, rely=0, relwidth=1, relheight=1)
                frame.lift()
            else:
                frame.place_forget()
        for key, button in buttons.items():
            active = key == selected
            button.configure(
                background="#2f80ed" if active else "#e8eef7",
                foreground="#ffffff" if active else "#263653",
                activebackground="#246fca" if active else "#dce8f8",
                activeforeground="#ffffff" if active else "#1768c4",
            )

    def _refresh_auto_target(self) -> None:
        ids = self.selected_ids()
        if not hasattr(self, "auto_target"):
            return
        if not ids:
            self.auto_target.set("Chưa chọn tài khoản")
            return
        names = [
            str(profile.get("name") or "Chưa đặt tên")
            for profile in self.profiles if profile.get("id") in set(ids)
        ]
        if len(names) <= 2:
            self.auto_target.set(", ".join(names))
        else:
            self.auto_target.set(f"{names[0]}, {names[1]} +{len(names) - 2}")

    def _clear_stall_job(self, profile_id: str) -> dict:
        jobs = self.settings.setdefault("clear_stall_jobs", {})
        job = jobs.get(profile_id, {})
        return job if isinstance(job, dict) else {}

    @staticmethod
    def _format_clear_stall_countdown(seconds: float) -> str:
        total = max(0, int(round(seconds)))
        days, total = divmod(total, 86400)
        hours, total = divmod(total, 3600)
        minutes, secs = divmod(total, 60)
        prefix = f"{days} ngày " if days else ""
        return f"{prefix}{hours:02d}:{minutes:02d}:{secs:02d}"

    def _clear_stall_account_name(self, profile_id: str) -> str:
        profile = next(
            (item for item in self.profiles if str(item.get("id") or "") == profile_id),
            None,
        )
        return str(
            (profile or {}).get("name") or profile_id or "Tài khoản không xác định"
        )

    def _append_clear_stall_history(self, record: dict) -> None:
        """Append a safe, profile-independent Dọn quầy history record."""
        allowed = (
            "timestamp", "profile_id", "account", "result", "activity",
            "requested_quantity", "purchased_quantity", "sold_quantity",
            "collected_gold_slots",
        )
        safe = {key: record.get(key) for key in allowed if key in record}
        try:
            CLEAR_STALL_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with CLEAR_STALL_HISTORY_FILE.open(
                "a", encoding="utf-8", errors="replace"
            ) as stream:
                stream.write(json.dumps(safe, ensure_ascii=False, default=str) + "\n")
        except OSError:
            pass

    def _record_clear_stall_activity(self, payload: dict) -> None:
        profile_id = str(payload.get("profile_id") or "")
        event = str(payload.get("event") or "")
        if not profile_id or not event:
            return
        account = self._clear_stall_account_name(profile_id)
        stamp = float(payload.get("at") or time.time())
        message = str(payload.get("message") or payload.get("stage") or "").strip()
        purchased = int(payload.get("purchased_quantity") or 0)
        sold = int(payload.get("sold_quantity") or payload.get("quantity") or 0)
        gold = int(payload.get("collected_gold_slots") or 0)
        requested = int(payload.get("requested_quantity") or 0)
        friend = payload.get("friend_ordinal")
        item_name = str(payload.get("item_name") or payload.get("item_id") or "VP")

        if event in {"worker_started", "probe_boot"}:
            activity = message or "đã đăng nhập, bắt đầu Dọn quầy"
        elif event == "probe_purchase_ok":
            where = f" tại nhà bạn {friend}" if friend else ""
            activity = f"đã thu {item_name}{where}; tổng thu {purchased} VP"
        elif event == "probe_resale_ok":
            activity = f"đã treo {sold} VP"
        elif event == "probe_ok":
            activity = (
                f"hoàn thành: mua {purchased}/{requested} VP, "
                f"thu vàng {gold} ô, treo {sold} VP"
            )
        elif event in {"worker_error", "probe_error"}:
            activity = "lỗi: " + str(payload.get("error") or message or "không xác định")
        elif event == "probe_temp_pass":
            activity = message or "watchdog phát hiện đơ; đã đóng ClientJS và trả hàng chờ"
        elif event in {"worker_stopping", "probe_stopped"}:
            activity = message or "đã dừng an toàn"
        elif event in {"progress", "probe_progress", "log"}:
            activity = message
        elif event == "worker_finished":
            activity = "hoàn thành lượt Dọn quầy"
        else:
            return
        if not activity:
            return

        rows = getattr(self, "_clear_stall_live_log", None)
        if rows is None:
            rows = []
            self._clear_stall_live_log = rows
        rows.append({
            "timestamp": stamp,
            "profile_id": profile_id,
            "account": account,
            "activity": activity,
        })
        del rows[:-500]

        result = ""
        if event == "worker_started" or (
            event == "probe_boot"
            and str(payload.get("stage") or "") == "clean-runtime-start"
        ):
            result = "BẮT ĐẦU"
        elif event in {"worker_finished", "probe_ok"}:
            result = "HOÀN THÀNH"
        elif event == "probe_temp_pass":
            result = "TẠM PASS"
        elif event in {"worker_error", "probe_error"}:
            result = "LỖI"
        elif event in {"worker_stopping", "probe_stopped"}:
            result = "ĐÃ DỪNG"
        if result:
            self._append_clear_stall_history({
                "timestamp": stamp,
                "profile_id": profile_id,
                "account": account,
                "result": result,
                "activity": activity,
                "requested_quantity": requested,
                "purchased_quantity": purchased,
                "sold_quantity": sold,
                "collected_gold_slots": gold,
            })

    def _read_clear_stall_history(self) -> list[dict]:
        if not CLEAR_STALL_HISTORY_FILE.is_file():
            return []
        rows = []
        try:
            with CLEAR_STALL_HISTORY_FILE.open(
                "r", encoding="utf-8", errors="replace"
            ) as stream:
                for line in stream:
                    try:
                        value = json.loads(line)
                    except (TypeError, ValueError):
                        continue
                    if isinstance(value, dict):
                        rows.append(value)
        except OSError:
            return []
        return rows[-1000:]

    def _show_clear_stall_log(self) -> None:
        current = getattr(self, "_clear_stall_log_window", None)
        if current is not None and current.winfo_exists():
            current.deiconify()
            current.lift()
            current.focus_force()
            return

        window = tk.Toplevel(self)
        self._clear_stall_log_window = window
        window.title("Log Dọn quầy")
        window.geometry("820x460")
        window.minsize(680, 360)
        window.transient(self)
        window.configure(background="#f3f6fa")

        header = ttk.Frame(
            window, padding=(12, 10, 12, 6), style="Detail.TFrame"
        )
        header.pack(fill="x")
        ttk.Label(
            header, text="LOG DỌN QUẦY", style="Section.TLabel"
        ).pack(side="left")
        ttk.Label(
            header, text="Tự cập nhật mỗi giây", style="AutoValue.TLabel"
        ).pack(side="right")

        notebook = ttk.Notebook(window)
        notebook.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        total_tab = ttk.Frame(notebook, padding=8, style="Detail.TFrame")
        live_tab = ttk.Frame(notebook, padding=8, style="Detail.TFrame")
        notebook.add(total_tab, text="Nhật ký tổng")
        notebook.add(live_tab, text="Acc đang dọn")

        total_tree = ttk.Treeview(
            total_tab,
            columns=("time", "account", "result", "bought", "sold", "gold"),
            show="headings", style="Queue.Treeview",
        )
        for key, label, width, anchor in (
            ("time", "THỜI GIAN", 145, "center"),
            ("account", "TÀI KHOẢN", 190, "w"),
            ("result", "KẾT QUẢ", 105, "center"),
            ("bought", "VP MUA", 90, "center"),
            ("sold", "VP TREO", 90, "center"),
            ("gold", "Ô VÀNG", 80, "center"),
        ):
            total_tree.heading(key, text=label)
            total_tree.column(key, width=width, anchor=anchor)
        total_scroll = ttk.Scrollbar(
            total_tab, orient="vertical", command=total_tree.yview
        )
        total_tree.configure(yscrollcommand=total_scroll.set)
        total_tree.pack(side="left", fill="both", expand=True)
        total_scroll.pack(side="right", fill="y")

        live_tree = ttk.Treeview(
            live_tab, columns=("time", "account", "activity"),
            show="headings", style="Queue.Treeview",
        )
        live_tree.heading("time", text="THỜI GIAN")
        live_tree.heading("account", text="TÀI KHOẢN")
        live_tree.heading("activity", text="THÔNG TIN ĐANG THỰC HIỆN")
        live_tree.column("time", width=90, anchor="center")
        live_tree.column("account", width=170, anchor="w")
        live_tree.column("activity", width=500, anchor="w")
        live_scroll = ttk.Scrollbar(
            live_tab, orient="vertical", command=live_tree.yview
        )
        live_tree.configure(yscrollcommand=live_scroll.set)
        live_tree.pack(side="left", fill="both", expand=True)
        live_scroll.pack(side="right", fill="y")

        self._clear_stall_total_log_tree = total_tree
        self._clear_stall_live_log_tree = live_tree

        def close_log() -> None:
            self._clear_stall_log_window = None
            self._clear_stall_total_log_tree = None
            self._clear_stall_live_log_tree = None
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", close_log)
        self._refresh_clear_stall_log()

    def _refresh_clear_stall_log(self) -> None:
        window = getattr(self, "_clear_stall_log_window", None)
        total_tree = getattr(self, "_clear_stall_total_log_tree", None)
        live_tree = getattr(self, "_clear_stall_live_log_tree", None)
        if window is None or not window.winfo_exists():
            return
        if total_tree is not None:
            total_tree.delete(*total_tree.get_children())
            for row in reversed(self._read_clear_stall_history()):
                stamp = float(row.get("timestamp") or 0)
                total_tree.insert("", "end", values=(
                    time.strftime("%d/%m/%Y %H:%M", time.localtime(stamp)),
                    row.get("account") or row.get("profile_id") or "",
                    row.get("result") or "",
                    int(row.get("purchased_quantity") or 0),
                    int(row.get("sold_quantity") or 0),
                    int(row.get("collected_gold_slots") or 0),
                ))
        if live_tree is not None:
            live_tree.delete(*live_tree.get_children())
            live_rows = list(getattr(self, "_clear_stall_live_log", []))[-300:]
            for row in live_rows:
                stamp = float(row.get("timestamp") or 0)
                live_tree.insert("", "end", values=(
                    time.strftime("%H:%M:%S", time.localtime(stamp)),
                    row.get("account") or row.get("profile_id") or "",
                    row.get("activity") or "",
                ))
            children = live_tree.get_children()
            if children:
                live_tree.see(children[-1])
        window.after(1000, self._refresh_clear_stall_log)

    def _show_clear_stall_queue(self) -> None:
        current = getattr(self, "_clear_stall_queue_window", None)
        if current is not None and current.winfo_exists():
            current.deiconify()
            current.lift()
            current.focus_force()
            return

        window = tk.Toplevel(self)
        self._clear_stall_queue_window = window
        window.title("Danh sách hàng chờ Dọn quầy")
        window.geometry("620x360")
        window.minsize(560, 300)
        window.transient(self)
        window.configure(background="#f3f6fa")

        header = ttk.Frame(
            window, padding=(12, 10, 12, 6), style="Detail.TFrame"
        )
        header.pack(fill="x")
        ttk.Label(
            header, text="HÀNG CHỜ DỌN QUẦY", style="Section.TLabel"
        ).pack(side="left")
        self._clear_stall_queue_summary = tk.StringVar(value="Đang tải...")
        ttk.Label(
            header, textvariable=self._clear_stall_queue_summary,
            style="AutoValue.TLabel",
        ).pack(side="right")

        body = ttk.Frame(
            window, padding=(12, 4, 12, 8), style="Detail.TFrame"
        )
        body.pack(fill="both", expand=True)
        tree = ttk.Treeview(
            body,
            columns=("account", "state", "countdown"),
            show="headings",
            selectmode="browse",
            style="Queue.Treeview",
        )
        tree.heading("account", text="TÊN TÀI KHOẢN")
        tree.heading("state", text="TRẠNG THÁI")
        tree.heading("countdown", text="THỜI GIAN CÒN LẠI")
        tree.column("account", width=190, anchor="w")
        tree.column("state", width=230, anchor="w")
        tree.column("countdown", width=150, anchor="center")
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self._clear_stall_queue_tree = tree

        ttk.Label(
            window,
            text="Danh sách tự cập nhật mỗi giây và xếp từ thời gian ít nhất đến nhiều nhất.",
            style="AutoValue.TLabel",
            anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 10))

        def close_queue() -> None:
            self._clear_stall_queue_window = None
            self._clear_stall_queue_tree = None
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", close_queue)
        self._refresh_clear_stall_queue()

    def _refresh_clear_stall_queue(self) -> None:
        window = getattr(self, "_clear_stall_queue_window", None)
        tree = getattr(self, "_clear_stall_queue_tree", None)
        if window is None or tree is None or not window.winfo_exists():
            return

        now = time.time()
        names = {
            str(profile.get("id") or ""): str(
                profile.get("name") or profile.get("id") or "Không tên"
            )
            for profile in self.profiles
        }
        jobs = self.settings.get("clear_stall_jobs", {})
        rows = []
        if isinstance(jobs, dict):
            for profile_id, job in jobs.items():
                if not isinstance(job, dict):
                    continue
                profile_key = str(profile_id)
                worker = self._clear_stall_workers.get(profile_key)
                running = worker is not None and worker.poll() is None
                starting = profile_key in self._clear_stall_starting
                if not bool(job.get("enabled", False)) and not running and not starting:
                    continue
                try:
                    due = float(job.get("next_run_at", 0) or 0)
                except (TypeError, ValueError):
                    due = 0.0
                remaining = max(0.0, due - now) if due > 0 else 0.0
                checkpoint = str(job.get("last_checkpoint") or "").strip()
                if running:
                    state = checkpoint or "Đang chạy"
                    countdown = "ĐANG CHẠY"
                elif starting:
                    state = checkpoint or "Đang khởi động"
                    countdown = "ĐANG CHẠY"
                elif due <= 0 or due <= now:
                    state = checkpoint if "xếp hàng" in checkpoint.lower() else "Đang xếp hàng"
                    countdown = "00:00:00"
                else:
                    state = "Chờ đến lượt"
                    countdown = self._format_clear_stall_countdown(remaining)
                rows.append((
                    remaining,
                    names.get(profile_key, profile_key),
                    state,
                    countdown,
                ))

        rows.sort(key=lambda row: (row[0], row[1].casefold()))
        for item in tree.get_children():
            tree.delete(item)
        for _remaining, account_name, state, countdown in rows:
            tree.insert("", "end", values=(account_name, state, countdown))
        self._clear_stall_queue_summary.set(f"{len(rows)} tài khoản")
        window.after(1000, self._refresh_clear_stall_queue)

    def _set_clear_stall_checkpoint(
        self, profile_id: str, checkpoint: str, result=None
    ) -> None:
        jobs = self.settings.setdefault("clear_stall_jobs", {})
        job = self._clear_stall_job(profile_id)
        job["last_checkpoint"] = str(checkpoint)
        if result is not None:
            job["last_result"] = result
        jobs[profile_id] = job
        save_settings(self.settings)
        if profile_id == self._active_profile_id:
            self.auto_clear_stall_status.set(str(checkpoint))

    def _start_clear_stall_probe(self) -> None:
        """Production fallback; DEV overrides this with the resident read-only probe."""
        self._start_clear_stall()

    def _start_clear_stall_purchase_probe(self) -> None:
        """Transaction probes are available only in the isolated DEV shell."""
        messagebox.showinfo(
            APP_NAME,
            "GATE 2 chỉ được phép chạy trong Multi DEV.",
        )

    def _start_clear_stall_target_probe(self) -> None:
        """Target-purchase probes are available only in the isolated DEV shell."""
        messagebox.showinfo(
            APP_NAME,
            "GATE 3 chỉ được phép chạy trong Multi DEV.",
        )

    def _start_clear_stall_resale_probe(self) -> None:
        """Exact-resale probes are available only in the isolated DEV shell."""
        messagebox.showinfo(
            APP_NAME,
            "GATE 4 chỉ được phép chạy trong Multi DEV.",
        )

    def _start_clear_stall_full_resale_probe(self) -> None:
        """Full exact-resale probes are available only in the DEV shell."""
        messagebox.showinfo(
            APP_NAME,
            "GATE 5 chỉ được phép chạy trong Multi DEV.",
        )

    def _start_clear_stall(
        self, profile_id: str | None = None, scheduled: bool = False
    ) -> None:
        if profile_id is None:
            self._save_clear_stall_config()
            profile_id, profile = self._clear_stall_profile()
        else:
            profile = next(
                (p for p in self.profiles if p.get("id") == profile_id), None
            )
        if not profile_id or not profile:
            if not scheduled:
                messagebox.showinfo(APP_NAME, "Hãy chọn một tài khoản clone.")
            return
        current = self._clear_stall_workers.get(profile_id)
        if current and current.poll() is None:
            if not scheduled:
                messagebox.showinfo(APP_NAME, "Clone này đang chạy Dọn quầy.")
            return
        auto_worker = self._auto_workers.get(profile_id)
        if auto_worker and auto_worker.poll() is None:
            if not scheduled:
                messagebox.showinfo(
                    APP_NAME,
                    "Hãy dừng AUTO chính của clone trước khi chạy Dọn quầy.",
                )
            return
        if profile_id in self._clear_stall_starting:
            return

        # Dọn quầy is a machine-wide serialized job.  A later account stays
        # due and is retried by the scheduler after the active account exits;
        # never open two clients/workers into the same friend-stall workflow.
        busy_profiles = {
            str(other_id)
            for other_id, other_worker in self._clear_stall_workers.items()
            if str(other_id) != str(profile_id)
            and other_worker is not None
            and other_worker.poll() is None
        }
        busy_profiles.update(
            str(other_id)
            for other_id in self._clear_stall_starting
            if str(other_id) != str(profile_id)
        )
        if busy_profiles:
            active_name = next(
                (
                    str(item.get("name") or other_id)
                    for other_id in sorted(busy_profiles)
                    for item in self.profiles
                    if str(item.get("id") or "") == other_id
                ),
                "tài khoản trước",
            )
            self._set_clear_stall_checkpoint(
                str(profile_id),
                f"Đang xếp hàng • chờ {active_name} dọn quầy xong",
            )
            return

        job = self._clear_stall_job(profile_id)
        if not job:
            if not scheduled:
                messagebox.showinfo(APP_NAME, "Hãy lưu cấu hình Dọn quầy trước.")
            return
        # Bấm Bắt đầu luôn chạy ngay. Chu kỳ chỉ được tính sau khi hoàn tất.
        job["next_run_at"] = 0
        job["last_checkpoint"] = "Đang mở clone"
        self.settings.setdefault("clear_stall_jobs", {})[profile_id] = job
        save_settings(self.settings)
        self._clear_stall_starting.add(profile_id)
        try:
            proc = self.processes.get(profile_id)
            if not proc or proc.poll() is not None:
                self._launch(profile)
                proc = self.processes.get(profile_id)
            if not proc or proc.poll() is not None:
                raise RuntimeError("Không mở được ClientJS của clone")
        except Exception as exc:
            self._clear_stall_starting.discard(profile_id)
            self._set_clear_stall_checkpoint(profile_id, f"Lỗi mở clone: {exc}")
            if not scheduled:
                messagebox.showerror(APP_NAME, str(exc))
            return
        self.auto_clear_stall_status.set(
            "Đang chờ ClientJS sẵn sàng • Sau đó chạy ngay"
        )
        self.after(
            2500,
            lambda pid=profile_id: self._launch_clear_stall_worker(pid),
        )

    def _launch_clear_stall_worker(self, profile_id: str) -> None:
        self._clear_stall_starting.discard(profile_id)
        profile = next(
            (p for p in self.profiles if p.get("id") == profile_id), None
        )
        proc = self.processes.get(profile_id)
        if not profile or not proc or proc.poll() is not None:
            self._set_clear_stall_checkpoint(
                profile_id, "Lỗi: clone đã đóng trước khi worker khởi động"
            )
            return
        job = self._clear_stall_job(profile_id)
        package_root = TOOL_DIR.parent
        auto_root = package_root / "AUTO_PRO"
        worker_file = (
            package_root / "components" / "clientjs-auto" /
            "worker" / "clear_stall_worker.py"
        )
        if not worker_file.is_file():
            self._set_clear_stall_checkpoint(
                profile_id, f"Thiếu worker: {worker_file}"
            )
            return
        friend = int(job.get("target_friend_ordinal", 1))
        stall = int(job.get("target_stall_id", 2))
        quantity = int(job.get("buy_quantity", 8))
        pages = int(job.get("max_scan_pages", 10))
        run_id = time.strftime("%Y%m%d-%H%M%S")
        work_dir = APP_DIR / "clear-stall" / profile_id / run_id
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            worker = subprocess.Popen(
                [
                    sys.executable, str(worker_file),
                    "--auto-root", str(auto_root),
                    "--pid", str(proc.pid),
                    "--profile-id", str(profile_id),
                    "--profile-name", str(profile.get("name") or profile_id),
                    "--friend-ordinal", str(friend),
                    "--stall-id", str(stall),
                    "--quantity", str(quantity),
                    "--max-pages", str(pages),
                    "--work-dir", str(work_dir),
                ],
                cwd=str(auto_root), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                errors="replace", bufsize=1, creationflags=flags,
            )
        except Exception as exc:
            self._set_clear_stall_checkpoint(
                profile_id, f"Lỗi mở Dọn quầy worker Python: {exc}"
            )
            return
        self._clear_stall_workers[profile_id] = worker
        self._write_auto_log(profile_id, {
            "event": "worker_spawned",
            "workflow": "clear_stall",
            "pid": proc.pid,
            "worker_pid": worker.pid,
            "worker_file": str(worker_file),
            "work_dir": str(work_dir),
            "friend_ordinal": friend,
            "stall_id": stall,
            "quantity": quantity,
            "max_pages": pages,
        })
        self._set_clear_stall_checkpoint(
            profile_id,
            (
                f"Python worker • Duyệt nhà 1..{friend} • Kho {stall} • "
                f"Mua {quantity} • Quét tối đa {pages} trang"
            ),
        )
        threading.Thread(
            target=self._read_clear_stall_worker,
            args=(profile_id, worker),
            daemon=True,
        ).start()

    def _read_clear_stall_worker(self, profile_id: str, worker) -> None:
        if not worker.stdout:
            return
        for line in worker.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                payload = {"event": "log", "message": line}
            payload["profile_id"] = profile_id
            self._write_auto_log(profile_id, {
                **payload, "workflow": "clear_stall",
            })
            try:
                self._clear_stall_worker_queue.put(payload, timeout=1.0)
            except queue.Full:
                pass
        try:
            self._clear_stall_worker_queue.put_nowait({
                "event": "worker_exit",
                "profile_id": profile_id,
                "returncode": worker.wait(timeout=1.0),
            })
        except Exception:
            pass

    def _poll_clear_stall_workers(self) -> None:
        if self._bridge_stop.is_set():
            return
        try:
            while True:
                payload = self._clear_stall_worker_queue.get_nowait()
                self._handle_clear_stall_worker_event(payload)
        except queue.Empty:
            pass
        self.after(150, self._poll_clear_stall_workers)

    def _handle_clear_stall_worker_event(self, payload: dict) -> None:
        self._record_clear_stall_activity(payload)
        profile_id = str(payload.get("profile_id") or "")
        event = str(payload.get("event") or "")
        message = str(payload.get("message") or "")
        if event in {"worker_spawned", "worker_boot"}:
            stage = str(payload.get("stage") or "process_spawned")
            stage_labels = {
                "process_spawned": "Đã mở tiến trình Dọn quầy",
                "process_started": "Worker Dọn quầy đã khởi động",
                "importing_auto_worker": "Đang nạp bộ điều khiển AUTO PRO",
                "loading_auto_pro_runtime": "Đang nạp runtime AUTO PRO",
                "constructing_controller": "Đang kết nối ClientJS",
                "controller_ready": "Đã kết nối ClientJS",
            }
            self._set_clear_stall_checkpoint(
                profile_id, stage_labels.get(stage, f"Khởi tạo: {stage}")
            )
        elif event == "worker_started":
            self._set_clear_stall_checkpoint(
                profile_id, "Đang vào nhà bạn và quét toàn bộ quầy"
            )
        elif event == "progress":
            self._set_clear_stall_checkpoint(
                profile_id, message or "Dọn quầy đang chạy"
            )
        elif event == "log" and message:
            if profile_id == self._active_profile_id:
                self.auto_clear_stall_status.set(message)
            self.note.set(message)
        elif event == "worker_stopping":
            self._set_clear_stall_checkpoint(profile_id, "Đang dừng an toàn")
        elif event == "worker_error":
            error = str(payload.get("error") or "Lỗi Dọn quầy không xác định")
            diagnostics = payload.get("diagnostics")
            detail = ""
            if isinstance(diagnostics, dict):
                source = str(diagnostics.get("source_file") or "")
                function = str(diagnostics.get("function") or "")
                line = diagnostics.get("line")
                if source or function or line:
                    detail = f"\nTại: {source} • {function} • dòng {line}"
            self._set_clear_stall_checkpoint(
                profile_id, "Dọn quầy lỗi",
                {"ok": False, "error": error, "diagnostics": diagnostics},
            )
            if profile_id == self._active_profile_id:
                messagebox.showerror(
                    APP_NAME, f"Dọn quầy lỗi:\n{error}{detail}"
                )
        elif event == "worker_finished":
            job = self._clear_stall_job(profile_id)
            if bool(payload.get("probe_only", False)):
                planned = int(payload.get("planned_quantity", 0) or 0)
                requested = int(job.get("buy_quantity", 0) or 0)
                reached = bool(payload.get("target_reached", False))
                job["last_checkpoint"] = (
                    f"GATE 1 PASS • kế hoạch {planned}/{requested} VP • "
                    f"target {'ĐỦ' if reached else 'THIẾU'}"
                )
                job["last_result"] = {
                    "ok": True,
                    "probe_only": True,
                    "finished_at": time.time(),
                    "planned_quantity": planned,
                    "target_reached": reached,
                }
                self.settings.setdefault("clear_stall_jobs", {})[profile_id] = job
                save_settings(self.settings)
                if profile_id == self._active_profile_id:
                    self._refresh_clear_stall_panel()
                return
            interval = max(5, int(job.get("interval_minutes", 65) or 65))
            job["last_checkpoint"] = "Hoàn thành mua và bán lại"
            job["last_result"] = {"ok": True, "finished_at": time.time()}
            job["next_run_at"] = (
                time.time() + interval * 60 if job.get("enabled", False) else 0
            )
            self.settings.setdefault("clear_stall_jobs", {})[profile_id] = job
            save_settings(self.settings)
            if bool(job.get("close_client_after_run", True)):
                proc = self.processes.get(profile_id)
                if proc and proc.poll() is None:
                    proc.terminate()
            if profile_id == self._active_profile_id:
                self._refresh_clear_stall_panel()
        elif event == "worker_exit":
            worker = self._clear_stall_workers.get(profile_id)
            if worker and worker.poll() is not None:
                self._clear_stall_workers.pop(profile_id, None)

    def _stop_clear_stall(self) -> None:
        profile_id, _profile = self._clear_stall_profile()
        worker = self._clear_stall_workers.get(str(profile_id or ""))
        if not worker or worker.poll() is not None or not worker.stdin:
            self.auto_clear_stall_status.set("Dọn quầy hiện không chạy")
            return
        try:
            worker.stdin.write(json.dumps({"command": "stop"}) + "\n")
            worker.stdin.flush()
            self.auto_clear_stall_status.set("Đã gửi yêu cầu dừng an toàn")
        except (OSError, ValueError) as exc:
            self.auto_clear_stall_status.set(f"Không gửi được lệnh dừng: {exc}")

    def _poll_clear_stall_schedule(self) -> None:
        if self._bridge_stop.is_set():
            return
        now = time.time()
        jobs = self.settings.get("clear_stall_jobs", {})
        if isinstance(jobs, dict):
            for profile_id, job in tuple(jobs.items()):
                if not isinstance(job, dict) or not job.get("enabled", False):
                    continue
                try:
                    due = float(job.get("next_run_at", 0) or 0)
                except (TypeError, ValueError):
                    due = 0
                if due > 0 and due <= now:
                    self._start_clear_stall(str(profile_id), scheduled=True)
        self.after(1000, self._poll_clear_stall_schedule)

    def _open_clean_main_log(self, kind: str) -> None:
        selected = self.selected_ids()
        if len(selected) != 1:
            messagebox.showinfo(
                APP_NAME, "Hãy chọn đúng một tài khoản để xem log."
            )
            return
        profile_id = str(selected[0])
        paths = getattr(self, "_clean_main_log_paths", {}).get(profile_id)
        index = 0 if str(kind) == "action" else 1
        path = Path(paths[index]) if paths else None
        if path is None or not path.is_file():
            profile_root = APP_DIR / "auto-multi-dev" / profile_id
            name = "action.log" if index == 0 else "detail.log"
            candidates = sorted(
                profile_root.glob(f"*/{name}"),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            ) if profile_root.is_dir() else []
            path = candidates[0] if candidates else None
        if path is None or not path.is_file():
            messagebox.showinfo(APP_NAME, "Tài khoản này chưa có log AUTO MULTI DEV.")
            return
        from main_log_viewer import open_log_window
        label = "LOG HÀNH ĐỘNG" if index == 0 else "LOG CHI TIẾT NHẬN DIỆN"
        profile = next(
            (item for item in self.profiles if str(item.get("id") or "") == profile_id),
            {},
        )
        open_log_window(
            self, path, f"{label} • {profile.get('name') or profile_id}"
        )

    def _start_clean_vp_recognition_probe(self) -> None:
        messagebox.showinfo(
            APP_NAME,
            "Kiểm tra nhận diện VP READ-ONLY chỉ chạy trong Multi DEV.",
        )

    def _start_clean_auto_session(self) -> None:
        """Launch the Python-only game-entry layer for every checked client."""
        selected = self.selected_ids()
        if not selected:
            messagebox.showinfo(APP_NAME, "Hãy tích chọn ít nhất một tài khoản đang chạy.")
            return
        launched = 0
        busy = []
        launch_failed = []

        # Refresh ownership immediately instead of waiting for the 2-second
        # bridge monitor. This also rebinds a replacement PID after a restart.
        try:
            self._adopt_running_clients(running_clients())
        except Exception as exc:
            self.note.set(f"AUTO sạch: chưa thể quét ClientJS đang chạy: {exc}")

        package_root = TOOL_DIR.parent
        auto_root = package_root / "AUTO_PRO"
        worker_file = (
            package_root / "components" / "clientjs-auto" /
            "worker" / "clean_auto_worker.py"
        )
        if not worker_file.is_file():
            messagebox.showerror(APP_NAME, f"Thiếu worker AUTO sạch:\n{worker_file}")
            return
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        for profile_id in selected:
            profile = next(
                (item for item in self.profiles if item.get("id") == profile_id),
                None,
            )
            process = self.processes.get(profile_id)
            legacy = self._auto_workers.get(profile_id)
            stall = self._clear_stall_workers.get(profile_id)
            current = self._clean_auto_workers.get(profile_id)
            profile_name = str((profile or {}).get("name") or profile_id)
            if profile is None:
                launch_failed.append(f"{profile_name} (không còn profile)")
                continue
            if (
                (legacy and legacy.poll() is None)
                or (stall and stall.poll() is None)
                or (current and current.poll() is None)
            ):
                busy.append(profile_name)
                continue

            # "Vào game" owns the complete first layer: open the selected
            # ClientJS when offline, then let the worker wait for its exact PID,
            # Bridge V3 and the game UI. Profiles/secrets are left untouched.
            if process is None or process.poll() is not None:
                try:
                    self._launch(profile)
                    process = self.processes.get(profile_id)
                except Exception as exc:
                    launch_failed.append(f"{profile_name} ({exc})")
                    continue
            if process is None or process.poll() is not None:
                launch_failed.append(f"{profile_name} (ClientJS không khởi động)")
                continue

            work_dir = APP_DIR / "auto-multi-dev" / str(profile_id)
            work_dir.mkdir(parents=True, exist_ok=True)
            worker = subprocess.Popen(
                [
                    sys.executable, str(worker_file),
                    "--auto-root", str(auto_root),
                    "--pid", str(process.pid),
                    "--profile-id", str(profile_id),
                    "--profile-name", str(profile.get("name") or profile_id),
                    "--profile-file", str(PROFILE_FILE),
                    "--work-dir", str(work_dir),
                ],
                cwd=str(auto_root), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                errors="replace", bufsize=1, creationflags=flags,
            )
            self._clean_auto_workers[profile_id] = worker
            threading.Thread(
                target=self._read_clean_auto_worker,
                args=(profile_id, worker),
                daemon=True,
            ).start()
            launched += 1
        if launched:
            self.auto_multi_dev_status.set(
                f"Đang vào game và đóng popup • {launched} tài khoản"
            )
        if busy:
            self.note.set("AUTO sạch bỏ qua tài khoản đang có worker: " + ", ".join(busy))
        if launch_failed:
            detail = "; ".join(launch_failed)
            self.note.set("AUTO sạch không mở được ClientJS: " + detail)
            messagebox.showerror(APP_NAME, "Không mở được ClientJS cho AUTO sạch:\n" + detail)

    def _read_clean_auto_worker(self, profile_id: str, worker) -> None:
        if worker.stdout:
            for line in worker.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    payload = {"event": "log", "message": line}
                payload["profile_id"] = profile_id
                try:
                    self._clean_auto_worker_queue.put(payload, timeout=1.0)
                except queue.Full:
                    pass
        try:
            self._clean_auto_worker_queue.put_nowait({
                "event": "worker_exit", "profile_id": profile_id,
                "returncode": worker.wait(timeout=1.0),
            })
        except Exception:
            pass

    def _poll_clean_auto_workers(self) -> None:
        if self._bridge_stop.is_set():
            return
        try:
            while True:
                payload = self._clean_auto_worker_queue.get_nowait()
                profile_id = str(payload.get("profile_id") or "")
                event = str(payload.get("event") or "")
                message = str(payload.get("message") or "")
                if event in {"progress", "log"} and message:
                    self.auto_multi_dev_status.set(message)
                    self.note.set(message)
                elif event == "worker_finished":
                    self.auto_multi_dev_status.set(
                        "PASS • Đã vào game, đóng popup và xác nhận màn hình chính"
                    )
                elif event == "worker_error":
                    error = str(payload.get("error") or "Lỗi AUTO sạch")
                    self.auto_multi_dev_status.set(f"LỖI • {error}")
                    messagebox.showerror(APP_NAME, f"AUTO MULTI DEV lỗi:\n{error}")
                elif event == "worker_stopped":
                    self.auto_multi_dev_status.set("Đã dừng AUTO sạch")
                elif event == "worker_exit":
                    worker = self._clean_auto_workers.get(profile_id)
                    if worker and worker.poll() is not None:
                        self._clean_auto_workers.pop(profile_id, None)
        except queue.Empty:
            pass
        self.after(120, self._poll_clean_auto_workers)

    def _stop_clean_auto_session(self) -> None:
        selected = set(self.selected_ids())
        targets = [
            (profile_id, worker)
            for profile_id, worker in self._clean_auto_workers.items()
            if not selected or profile_id in selected
        ]
        stopped = 0
        for _profile_id, worker in targets:
            try:
                if worker.poll() is None and worker.stdin:
                    worker.stdin.write(json.dumps({"command": "stop"}) + "\n")
                    worker.stdin.flush()
                    stopped += 1
            except (OSError, ValueError):
                pass
        self.auto_multi_dev_status.set(
            f"Đã gửi dừng an toàn • {stopped} worker"
            if stopped else "AUTO sạch hiện không chạy"
        )

    def _auto_ui_start(self) -> None:
        ids = self.selected_ids()
        if not ids:
            messagebox.showinfo(
                APP_NAME, "Hãy tích chọn ít nhất một tài khoản đang chạy."
            )
            return
        function_spec = self._auto_functions_by_label.get(self.auto_function.get())
        if not function_spec:
            messagebox.showinfo(APP_NAME, "Hãy chọn chức năng AUTO đã được cho phép.")
            return

        ready_ids = []
        unavailable = []
        already_running = []
        for profile_id in ids:
            profile = next(
                (p for p in self.profiles if p.get("id") == profile_id), None
            )
            proc = self.processes.get(profile_id)
            if not profile or not proc or proc.poll() is not None:
                unavailable.append(
                    str((profile or {}).get("name") or profile_id)
                )
                continue
            current = self._auto_workers.get(profile_id)
            if current and current.poll() is None:
                already_running.append(str(profile.get("name") or profile_id))
                continue
            ready_ids.append(profile_id)

        if unavailable:
            messagebox.showinfo(
                APP_NAME,
                "Các tài khoản sau chưa được mở bằng Multi DEV:\n- "
                + "\n- ".join(unavailable),
            )
            return
        if not ready_ids:
            messagebox.showinfo(
                APP_NAME,
                "Tất cả tài khoản đã chọn đều đang chạy AUTO."
                if already_running else "Không có tài khoản hợp lệ để chạy AUTO.",
            )
            return

        function_id = int(function_spec["auto_pro_function_id"])
        self.auto_status.set("Kiểm tra thư viện")
        self.auto_progress.set(5)
        self.auto_progress_text.set("5%")
        self.auto_scope_note.set(
            f"Function {function_id} • chuẩn bị {len(ready_ids)} tài khoản"
        )
        threading.Thread(
            target=self._probe_auto_runtime,
            args=(dict(function_spec), tuple(ready_ids)),
            daemon=True,
        ).start()

    def _probe_auto_runtime(self, function_spec: dict, profile_ids: tuple[str, ...]) -> None:
        """Validate AUTO PRO before allowing the execution worker to touch game."""
        package_root = TOOL_DIR.parent
        auto_root = package_root / "AUTO_PRO"
        worker = (
            package_root / "components" / "clientjs-auto" /
            "worker" / "runtime_probe.py"
        )
        try:
            if not worker.is_file():
                raise FileNotFoundError(f"Thiếu worker: {worker}")
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            result = subprocess.run(
                [
                    sys.executable, str(worker),
                    "--auto-root", str(auto_root),
                    "--function-id", str(function_spec["auto_pro_function_id"]),
                ],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", creationflags=flags, timeout=90,
            )
            payload = None
            for line in reversed(result.stdout.splitlines()):
                try:
                    candidate = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(candidate, dict) and candidate.get("event"):
                    payload = candidate
                    break
            if result.returncode or not payload or payload.get("event") != "probe_ok":
                detail = (
                    (payload or {}).get("error") or result.stderr.strip() or
                    result.stdout.strip() or f"exit code {result.returncode}"
                )
                raise RuntimeError(detail)
            self.after(
                0, lambda spec=dict(function_spec), ids=tuple(profile_ids):
                self._auto_probe_ok(spec, ids)
            )
        except Exception as exc:
            self.after(0, lambda error=str(exc): self._auto_probe_failed(error))

    def _auto_probe_ok(
        self, function_spec: dict, profile_ids: tuple[str, ...]
    ) -> None:
        launched = 0
        failed = []
        for profile_id in profile_ids:
            profile = next(
                (p for p in self.profiles if p.get("id") == profile_id), None
            )
            proc = self.processes.get(profile_id)
            if not profile or not proc or proc.poll() is not None:
                failed.append(str((profile or {}).get("name") or profile_id))
                continue
            try:
                self._launch_auto_worker(profile, proc, function_spec)
                launched += 1
            except Exception as exc:
                failed.append(
                    f"{profile.get('name') or profile_id}: {exc}"
                )

        if not launched:
            self._auto_probe_failed(
                "Không khởi động được tài khoản nào. " + "; ".join(failed)
            )
            return
        self.auto_status.set("Đang khởi động")
        self.auto_progress.set(15)
        self.auto_progress_text.set("15%")
        function_id = int(function_spec["auto_pro_function_id"])
        self.auto_scope_note.set(
            f"Function {function_id} • {launched} tài khoản đang kết nối"
        )
        if failed:
            self.note.set(
                f"Đã mở {launched} AUTO; bỏ qua: " + "; ".join(failed)
            )
        else:
            self.note.set(
                f"Đã mở Function {function_id} cho {launched} tài khoản."
            )

    def _launch_auto_worker(self, profile: dict, proc, function_spec: dict) -> None:
        package_root = TOOL_DIR.parent
        auto_root = package_root / "AUTO_PRO"
        worker_file = (
            package_root / "components" / "clientjs-auto" /
            "worker" / "auto_worker.py"
        )
        if not worker_file.is_file():
            raise FileNotFoundError(f"Thiếu worker: {worker_file}")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        worker = subprocess.Popen(
            [
                sys.executable, str(worker_file),
                "--auto-root", str(auto_root),
                "--pid", str(proc.pid),
                "--profile-id", str(profile["id"]),
                "--profile-name", str(profile.get("name") or profile["id"]),
                "--profile-file", str(PROFILE_FILE),
                "--function-id", str(function_spec["auto_pro_function_id"]),
                "--options-json", json.dumps(
                    self._collect_auto_options(profile["id"], function_spec),
                    ensure_ascii=True, separators=(",", ":"),
                ),
                "--tuning-json", json.dumps(
                    self._collect_auto_tuning(),
                    ensure_ascii=True, separators=(",", ":"),
                ),
            ],
            cwd=str(auto_root), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", bufsize=1, creationflags=flags,
        )
        self._auto_workers[profile["id"]] = worker
        threading.Thread(
            target=self._read_auto_worker,
            args=(profile["id"], worker),
            daemon=True,
        ).start()
        self.auto_status.set("Đang kết nối ClientJS")
        self.auto_progress.set(15)
        self.auto_progress_text.set("15%")
        self.note.set(
            f"Đã mở AUTO worker Function {function_spec['auto_pro_function_id']} "
            f"cho {profile.get('name')}."
        )

    def _read_auto_worker(self, profile_id: str, worker) -> None:
        if not worker.stdout:
            return
        for line in worker.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                payload = {"event": "log", "message": line}
            payload["profile_id"] = profile_id
            self._write_auto_log(profile_id, payload)
            try:
                self._auto_worker_queue.put(payload, timeout=1.0)
            except queue.Full:
                pass
        try:
            self._auto_worker_queue.put_nowait({
                "event": "worker_exit", "profile_id": profile_id,
                "returncode": worker.wait(timeout=1.0),
            })
        except Exception:
            pass

    def _write_auto_log(self, profile_id: str, payload: dict) -> None:
        try:
            log_dir = APP_DIR / "auto-logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            day = time.strftime("%Y%m%d")
            destination = log_dir / f"{profile_id}-{day}.jsonl"
            record = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), **payload}
            with destination.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _poll_auto_workers(self) -> None:
        if self._bridge_stop.is_set():
            return
        try:
            while True:
                payload = self._auto_worker_queue.get_nowait()
                self._handle_auto_worker_event(payload)
        except queue.Empty:
            pass
        self.after(100, self._poll_auto_workers)

    def _handle_auto_worker_event(self, payload: dict) -> None:
        profile_id = str(payload.get("profile_id") or "")
        event = str(payload.get("event") or "")
        message = str(payload.get("message") or "")
        if event == "worker_started":
            self.auto_status.set("Đang chạy")
            self.auto_progress.set(20)
            self.auto_progress_text.set("20%")
            self.auto_scope_note.set(
                f"Function {payload.get('function_id')} • PID {payload.get('pid')} • đang chạy"
            )
        elif event == "client_pid_changed":
            new_pid = int(payload.get("new_pid") or 0)
            old_pid = int(payload.get("old_pid") or 0)
            if profile_id and new_pid > 0:
                self.processes[profile_id] = RunningProcessRef(new_pid)
                self.note.set(
                    f"ClientJS đã reset: PID {old_pid} → {new_pid}; AUTO tiếp tục"
                )
                self.auto_scope_note.set(
                    f"Function {payload.get('function_id') or ''} • PID {new_pid} • đã nhận lại"
                )
                self.refresh()
        elif event == "progress":
            self.auto_status.set(message or "Đang chạy")
            self.note.set(message or "AUTO đang chạy")
        elif event == "log":
            if message:
                self.note.set(message)
        elif event == "tuning_applied":
            self.note.set("AUTO đang chạy đã nhận cấu hình tốc độ mới.")
            self.auto_scope_note.set("Đã áp dụng nóng • Có hiệu lực từ thao tác kế tiếp")
        elif event == "tuning_error":
            error = str(payload.get("error") or "Không rõ lỗi")
            self.note.set(f"Lỗi áp dụng tốc độ: {error}")
        elif event == "gesture_timing":
            caller = str(payload.get("caller") or "gesture")
            requested = float(payload.get("requested_seconds") or 0.0)
            actual = float(payload.get("actual_seconds") or 0.0)
            points = int(payload.get("point_count") or 0)
            self.auto_scope_note.set(
                f"{caller}: cấu hình {requested:.3f}s → thực tế {actual:.3f}s • {points} điểm"
            )
        elif event == "stats":
            data = self._game_data.setdefault(profile_id, {})
            data["sales"] = payload.get("total", data.get("sales", "—"))
            self._show_account_details(self._active_profile_id)
        elif event == "worker_stopping":
            self.auto_status.set("Đang dừng")
        elif event == "worker_finished":
            self.auto_status.set("Hoàn thành")
            self.auto_progress.set(100)
            self.auto_progress_text.set("100%")
        elif event == "worker_error":
            error = str(payload.get("error") or "Lỗi worker không xác định")
            self.auto_status.set("Lỗi AUTO")
            self.auto_scope_note.set(error[:120])
            messagebox.showerror(
                APP_NAME,
                f"AUTO Function {payload.get('function_id', '?')} lỗi:\n{error}",
            )
        elif event == "worker_exit":
            worker = self._auto_workers.get(profile_id)
            if worker and worker.poll() is not None:
                self._auto_workers.pop(profile_id, None)
            if int(payload.get("returncode") or 0) and self.auto_status.get() != "Lỗi AUTO":
                self.auto_status.set("Worker đã dừng")

    def _auto_probe_failed(self, error: str) -> None:
        self.auto_status.set("Lỗi thư viện")
        self.auto_progress.set(0)
        self.auto_progress_text.set("0%")
        self.auto_scope_note.set("Runtime probe thất bại")
        messagebox.showerror(APP_NAME, f"Không nạp được thư viện AUTO PRO:\n{error}")

    def _send_auto_command(self, command: str) -> bool:
        sent = False
        for profile_id in self.selected_ids():
            worker = self._auto_workers.get(profile_id)
            if not worker or worker.poll() is not None or not worker.stdin:
                continue
            try:
                worker.stdin.write(json.dumps({"command": command}) + "\n")
                worker.stdin.flush()
                sent = True
            except OSError:
                continue
        return sent

    def _auto_ui_pause(self) -> None:
        if self._send_auto_command("pause"):
            self.auto_status.set("Đang tạm dừng")
            self.auto_scope_note.set("Worker sẽ dừng an toàn tại checkpoint gần nhất")
        else:
            self.note.set("Không có AUTO đang chạy trên tài khoản đã chọn.")

    def _auto_ui_stop(self) -> None:
        if self._send_auto_command("stop"):
            self.auto_status.set("Đang dừng")
            self.auto_scope_note.set("Đã gửi yêu cầu dừng an toàn")
        else:
            self.auto_status.set("Đã dừng")
            self.auto_progress.set(0)
            self.auto_progress_text.set("0%")

    def _auto_ui_configure(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Cấu hình tốc độ AUTO ClientJS")
        dialog.transient(self)
        dialog.resizable(False, False)
        dialog.configure(background="#f3f6fa")
        dialog.grab_set()

        header = ttk.Frame(dialog, padding=(16, 14, 16, 8))
        header.pack(fill="x")
        ttk.Label(
            header, text="CẤU HÌNH TỐC ĐỘ AUTO CLIENTJS",
            style="AutoKey.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            header,
            text=(
                "Ba dòng MULTI DEV được tách độc lập theo yêu cầu. "
                "Các dòng AUTO PRO cũ được giữ để tương thích."
            ),
            style="AutoValue.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        body = ttk.Frame(dialog, padding=(16, 4, 16, 8))
        body.pack(fill="both", expand=True)
        current = self._collect_auto_tuning()
        variables = {}
        items = list(AUTO_TUNING_SPECS.items())
        split_at = (len(items) + 1) // 2
        for index, (key, (label, minimum, maximum, integer)) in enumerate(items):
            column_group = 0 if index < split_at else 1
            row = index if column_group == 0 else index - split_at
            base_column = column_group * 2
            ttk.Label(body, text=label, style="AutoValue.TLabel").grid(
                row=row, column=base_column, sticky="w",
                padx=(0 if column_group == 0 else 24, 8), pady=5,
            )
            value = current.get(key, DEFAULT_AUTO_TUNING[key])
            variable = tk.StringVar(value=str(value))
            variables[key] = variable
            increment = 1 if integer else (0.01 if minimum < 0.05 else 0.05)
            tk.Spinbox(
                body, from_=minimum, to=maximum, increment=increment,
                textvariable=variable, width=9, justify="right",
                font=("Segoe UI", 10),
            ).grid(row=row, column=base_column + 1, sticky="e", pady=5)

        ttk.Separator(dialog, orient="horizontal").pack(fill="x", padx=16)
        actions = ttk.Frame(dialog, padding=(16, 10, 16, 14))
        actions.pack(fill="x")

        def reset_defaults():
            for key, default in DEFAULT_AUTO_TUNING.items():
                variables[key].set(str(default))

        def save_values():
            validated = {}
            for key, variable in variables.items():
                label, minimum, maximum, integer = AUTO_TUNING_SPECS[key]
                try:
                    value = int(variable.get()) if integer else float(variable.get())
                except ValueError:
                    messagebox.showerror(
                        APP_NAME, f"{label}: giá trị không hợp lệ.", parent=dialog
                    )
                    return
                if not minimum <= value <= maximum:
                    messagebox.showerror(
                        APP_NAME,
                        f"{label}: chỉ nhận từ {minimum} đến {maximum}.",
                        parent=dialog,
                    )
                    return
                validated[key] = value
            self.settings["auto_tuning"] = validated
            save_settings(self.settings)
            updated_workers = 0
            payload = json.dumps(
                {"command": "update_tuning", "tuning": validated},
                ensure_ascii=True, separators=(",", ":"),
            ) + "\n"
            for worker in [
            *list(self._auto_workers.values()),
            *list(self._clean_auto_workers.values()),
        ]:
                try:
                    if worker.poll() is None and worker.stdin:
                        worker.stdin.write(payload)
                        worker.stdin.flush()
                        updated_workers += 1
                except (OSError, ValueError):
                    pass
            if updated_workers:
                self.note.set(
                    f"Đã lưu và áp dụng tốc độ mới cho {updated_workers} AUTO đang chạy."
                )
            else:
                self.note.set(
                    "Đã lưu cấu hình; sẽ áp dụng khi bắt đầu AUTO."
                )
            dialog.destroy()

        ttk.Button(
            actions, text="Khôi phục mặc định", command=reset_defaults,
            style="Action.TButton",
        ).pack(side="left")
        ttk.Button(
            actions, text="Hủy", command=dialog.destroy,
            style="Action.TButton",
        ).pack(side="right")
        ttk.Button(
            actions, text="Lưu cấu hình", command=save_values,
            style="AutoStart.TButton",
        ).pack(side="right", padx=(0, 8))

        dialog.update_idletasks()
        x = self.winfo_rootx() + max(0, (self.winfo_width() - dialog.winfo_width()) // 2)
        y = self.winfo_rooty() + max(0, (self.winfo_height() - dialog.winfo_height()) // 2)
        dialog.geometry(f"+{x}+{y}")
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.wait_window()

    def _create_account_tree(self, parent, title: str):
        box = ttk.LabelFrame(
            parent, text=title.upper(), padding=7, style="Panel.TLabelframe"
        )
        parent.add(box, weight=1)
        tree = ttk.Treeview(
            box, columns=("name", "pid"), show=("tree", "headings"),
            selectmode="browse", style="Account.Treeview", height=4,
        )
        tree.heading("#0", text="")
        tree.column("#0", width=46, minwidth=46, stretch=False, anchor="center")
        tree.heading("name", text="Tên client")
        tree.column("name", width=230, anchor="w")
        tree.heading("pid", text="PID")
        tree.column("pid", width=90, minwidth=70, stretch=False, anchor="center")
        tree.tag_configure("online", foreground="#147d52")
        tree.tag_configure("offline", foreground="#78859a")
        tree.pack(fill="both", expand=True)
        tree.bind("<Button-1>", lambda event, source=tree: self._on_account_click(source, event), add="+")
        tree.bind("<Double-1>", lambda _event: self.launch_selected())
        return tree

    def selected_ids(self) -> list[str]:
        if self._checked_profiles:
            return [p["id"] for p in self.profiles if p["id"] in self._checked_profiles]
        return [self._active_profile_id] if self._active_profile_id else []

    def _on_account_click(self, tree, event) -> None:
        profile_id = tree.identify_row(event.y)
        if not profile_id:
            return
        self._active_profile_id = profile_id
        other = self.offline_tree if tree is self.online_tree else self.online_tree
        other_selected = other.selection()
        if other_selected:
            other.selection_remove(*other_selected)
        tree.selection_set(profile_id)
        if tree.identify_column(event.x) == "#0":
            if profile_id in self._checked_profiles:
                self._checked_profiles.discard(profile_id)
            else:
                self._checked_profiles.add(profile_id)
            tree.item(
                profile_id,
                text="✓" if profile_id in self._checked_profiles else "＋",
            )
        self._show_account_details(profile_id)
        self._refresh_auto_target()
        self._refresh_auto_delete_panel()
        self._refresh_auto_quay_he_panel()
        self._refresh_auto_nang_kho_panel()
        self._refresh_clear_stall_panel()

    def _show_account_details(self, profile_id: str | None) -> None:
        profile = next((p for p in self.profiles if p.get("id") == profile_id), None)
        if not profile:
            self.detail_title.set("Chưa chọn tài khoản")
            for value in self.detail_vars.values():
                value.set("—")
            return
        self.detail_title.set(str(profile.get("name") or "Chưa đặt tên"))
        data = self._game_data.get(profile_id, {})
        defaults = {"name": profile.get("name", "—")}
        for key, value in self.detail_vars.items():
            value.set(str(data.get(key, defaults.get(key, "—"))))

    def update_game_data(self, profile_id: str, data: dict) -> None:
        """Public ingestion point for the upcoming in-game data reader."""
        current = self._game_data.setdefault(profile_id, {})
        current.update(data or {})
        if self._active_profile_id == profile_id:
            self._show_account_details(profile_id)

    def _publish_running_map(self) -> None:
        """Publish the authoritative profile name for each live PID.

        AUTO reads this file instead of guessing names from process/profile order.
        No launcher arguments or account secrets are written here.
        """
        entries = []
        for profile in self.profiles:
            proc = self.processes.get(profile.get("id"))
            if not proc or proc.poll() is not None:
                continue
            entries.append({
                "pid": int(proc.pid),
                "profile_id": str(profile.get("id") or ""),
                "name": str(profile.get("name") or f"PID {proc.pid}"),
            })
        try:
            APP_DIR.mkdir(parents=True, exist_ok=True)
            temp = RUNNING_MAP_FILE.with_suffix(".tmp")
            temp.write_text(
                json.dumps({"version": 1, "clients": entries}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temp, RUNNING_MAP_FILE)
        except OSError:
            pass

    def refresh(self) -> None:
        self._publish_running_map()
        valid_ids = {p.get("id") for p in self.profiles}
        self._checked_profiles.intersection_update(valid_ids)
        for tree in (self.online_tree, self.offline_tree):
            tree.delete(*tree.get_children())
        for profile in self.profiles:
            profile_id = profile["id"]
            proc = self.processes.get(profile_id)
            alive = bool(proc and proc.poll() is None)
            target = self.online_tree if alive else self.offline_tree
            target.insert(
                "", "end", iid=profile_id,
                text=(
                    "✓" if profile_id in self._checked_profiles else "＋"
                ),
                values=(profile.get("name", "Chưa đặt tên"), proc.pid if alive else "—"),
                tags=("online" if alive else "offline",),
            )
            if profile_id == self._active_profile_id:
                target.selection_set(profile_id)
        if self._active_profile_id not in valid_ids:
            self._active_profile_id = None
        self._show_account_details(self._active_profile_id)
        self._refresh_auto_target()
        self._refresh_clear_stall_panel()

    def _prepare_dwm(self):
        dwm = ctypes.windll.dwmapi
        dwm.DwmRegisterThumbnail.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.POINTER(ctypes.c_void_p)]
        dwm.DwmRegisterThumbnail.restype = ctypes.c_long
        dwm.DwmUpdateThumbnailProperties.argtypes = [ctypes.c_void_p, ctypes.POINTER(DWM_THUMBNAIL_PROPERTIES)]
        dwm.DwmUpdateThumbnailProperties.restype = ctypes.c_long
        dwm.DwmUnregisterThumbnail.argtypes = [ctypes.c_void_p]
        dwm.DwmUnregisterThumbnail.restype = ctypes.c_long
        return dwm

    def _register_live_thumbnail(self, profile_id: str, source_hwnd: int) -> None:
        self.update_idletasks()
        user32 = ctypes.windll.user32
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        destination = user32.GetAncestor(self.winfo_id(), 2) or self.winfo_id()
        thumbnail = ctypes.c_void_p()
        hr = self._prepare_dwm().DwmRegisterThumbnail(destination, source_hwnd, ctypes.byref(thumbnail))
        if hr < 0:
            raise OSError(f"DwmRegisterThumbnail lỗi 0x{hr & 0xffffffff:08X}")
        self._live_thumbnails[profile_id] = thumbnail

    def _unregister_live_thumbnail(self, profile_id: str) -> None:
        thumbnail = self._live_thumbnails.pop(profile_id, None)
        if thumbnail and thumbnail.value:
            self._prepare_dwm().DwmUnregisterThumbnail(thumbnail)

    def _update_live_dwm(self) -> None:
        if self._bridge_stop.is_set():
            return
        dwm = self._prepare_dwm()
        tree_x = self.tree.winfo_rootx() - self.winfo_rootx()
        tree_y = self.tree.winfo_rooty() - self.winfo_rooty()
        for profile_id, thumbnail in list(self._live_thumbnails.items()):
            props = DWM_THUMBNAIL_PROPERTIES()
            bbox = self.tree.bbox(profile_id, "#0") if self.tree.exists(profile_id) else ""
            if bbox:
                bx, by, bw, bh = map(int, bbox)
                side = max(1, min(bw - 8, bh - 8))
                left = tree_x + bx + (bw - side) // 2
                top = tree_y + by + (bh - side) // 2
                props.dwFlags = DWM_TNP_RECTDESTINATION | DWM_TNP_VISIBLE | DWM_TNP_SOURCECLIENTAREAONLY
                props.rcDestination = wintypes.RECT(left, top, left + side, top + side)
                props.fVisible = True
                props.fSourceClientAreaOnly = True
            else:
                props.dwFlags = DWM_TNP_VISIBLE
                props.fVisible = False
            hr = dwm.DwmUpdateThumbnailProperties(thumbnail, ctypes.byref(props))
            if hr < 0:
                self._live_enabled.discard(profile_id)
                self._unregister_live_thumbnail(profile_id)
        self.after(100, self._update_live_dwm)

    @staticmethod
    def _thumbnail_ppm(raw: bytes, width: int, height: int, side: int = 112) -> bytes:
        """Nearest-neighbour BGRA thumbnail encoded for Tk PhotoImage."""
        rgb = bytearray(side * side * 3)
        target = 0
        for y in range(side):
            source_y = min(height - 1, y * height // side)
            row = source_y * width * 4
            for x in range(side):
                source_x = min(width - 1, x * width // side)
                index = row + source_x * 4
                rgb[target] = raw[index + 2]
                rgb[target + 1] = raw[index + 1]
                rgb[target + 2] = raw[index]
                target += 3
        return f"P6\n{side} {side}\n255\n".encode("ascii") + bytes(rgb)

    def _live_worker(self) -> None:
        while not self._bridge_stop.is_set():
            enabled = set(self._live_enabled)
            snapshot = [item for item in list(self.processes.items()) if item[0] in enabled]
            for profile_id, proc in snapshot:
                if self._bridge_stop.is_set():
                    return
                if proc.poll() is not None:
                    continue
                try:
                    hwnd = self._window_for_pid(proc.pid)
                    if not hwnd:
                        continue
                    raw, width, height = capture_bgra(hwnd)
                    item = (profile_id, self._thumbnail_ppm(raw, width, height))
                    try:
                        self._live_queue.put_nowait(item)
                    except queue.Full:
                        pass
                except Exception:
                    continue
            self._bridge_stop.wait(1.0)

    def _poll_live_results(self) -> None:
        if self._bridge_stop.is_set():
            return
        try:
            while True:
                profile_id, ppm = self._live_queue.get_nowait()
                if self.tree.exists(profile_id):
                    image = tk.PhotoImage(data=ppm, format="PPM")
                    self._live_images[profile_id] = image
                    self.tree.item(profile_id, text="Đang xem", image=image)
        except queue.Empty:
            pass
        self.after(200, self._poll_live_results)

    def capture(self) -> None:
        try:
            clients = running_clients()
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Không đọc được client đang chạy:\n{exc}")
            return
        candidates = []
        for row in clients:
            try:
                args = split_windows_command_line(row["CommandLine"])
            except Exception:
                continue
            if len(args) >= 4 and Path(args[1]).name.lower() in {"game", "24"}:
                candidates.append((row, args))
            elif len(args) >= 4:
                candidates.append((row, args))
        if not candidates:
            messagebox.showinfo(APP_NAME, "Chưa thấy KVTM đang chạy. Hãy mở tài khoản bằng ZingPlay rồi bấm lại.")
            return
        if len(candidates) > 1:
            pids = ", ".join(str(row.get("ProcessId")) for row, _ in candidates)
            messagebox.showinfo(APP_NAME, f"Có nhiều client đang chạy (PID {pids}).\nHãy chỉ để client cần lưu chạy rồi thử lại.")
            return
        row, args = candidates[0]
        name = simpledialog.askstring(APP_NAME, "Đặt tên hồ sơ/tài khoản:", parent=self)
        if not name:
            return
        secret = protect(json.dumps(args[2:], ensure_ascii=False).encode("utf-8"))
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        existing = next((p for p in self.profiles if p.get("name", "").casefold() == name.casefold()), None)
        record = {
            "id": existing["id"] if existing else uuid.uuid4().hex,
            "name": name.strip(),
            "client": row.get("ExecutablePath") or args[0],
            "game_dir": args[1],
            "secret": secret,
            "updated_at": now,
        }
        if existing:
            self.profiles[self.profiles.index(existing)] = record
        else:
            self.profiles.append(record)
        try:
            save_profiles(self.profiles)
        except RuntimeError as exc:
            self.profiles = load_profiles()
            messagebox.showerror(APP_NAME, str(exc))
            self.refresh()
            return
        self.note.set(f"Đã lưu hồ sơ {record['name']} an toàn trên máy này")
        self.refresh()

    def _launch(self, profile: dict) -> None:
        old = self.processes.get(profile["id"])
        if old and old.poll() is None:
            return
        client = Path(profile.get("client") or DEFAULT_CLIENT)
        game_dir = Path(profile.get("game_dir") or DEFAULT_GAME)
        if not client.is_file():
            raise FileNotFoundError(f"Không thấy GameClientJS.exe:\n{client}")
        if not game_dir.is_dir():
            raise FileNotFoundError(f"Không thấy dữ liệu KVTM:\n{game_dir}")
        secret_args = json.loads(unprotect(profile["secret"]).decode("utf-8"))
        proc = subprocess.Popen([str(client), str(game_dir), *secret_args], cwd=str(game_dir))
        self.processes[profile["id"]] = proc
        self.after(1200, lambda p=proc: self._apply_display_to_process(p))

    def _profiles_for(self, ids: list[str]) -> list[dict]:
        wanted = set(ids)
        return [p for p in self.profiles if p["id"] in wanted]

    def launch_selected(self) -> None:
        ids = self.selected_ids()
        if not ids:
            messagebox.showinfo(APP_NAME, "Hãy chọn ít nhất một hồ sơ.")
            return
        self._launch_many(self._profiles_for(ids))

    def launch_all(self) -> None:
        self._launch_many(self.profiles)

    def _launch_many(self, profiles: list[dict]) -> None:
        if profiles and not self._bridge_files() and not self.configure_bridge():
            messagebox.showwarning(APP_NAME, "Chưa có Bridge DLL nên Multi chưa thể khóa khung game vuông.")
            return
        errors = []
        for profile in profiles:
            try:
                self._launch(profile)
                time.sleep(0.35)
            except Exception as exc:
                errors.append(f"{profile.get('name')}: {exc}")
        self.refresh()
        if errors:
            messagebox.showerror(APP_NAME, "Không mở được:\n\n" + "\n".join(errors))
        else:
            self.note.set(f"Đã gửi lệnh mở {len(profiles)} hồ sơ")

    def stop_selected(self) -> None:
        for profile_id in self.selected_ids():
            self._live_enabled.discard(profile_id)
            self._unregister_live_thumbnail(profile_id)
            preview = self.previews.get(profile_id)
            if preview:
                preview.close(restore=False)
            proc = self.processes.get(profile_id)
            if proc and proc.poll() is None:
                proc.terminate()
        self.after(500, self.refresh)

    def delete_selected(self) -> None:
        ids = set(self.selected_ids())
        if not ids or not messagebox.askyesno(APP_NAME, "Xóa các hồ sơ đã chọn? Client game không bị xóa."):
            return
        self.profiles = [p for p in self.profiles if p["id"] not in ids]
        save_profiles(self.profiles, allow_shrink=True)
        self._checked_profiles.difference_update(ids)
        self.refresh()

    def _window_for_pid(self, pid: int) -> int | None:
        found = []
        enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def callback(hwnd, _lparam):
            window_pid = wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
            if window_pid.value == pid and ctypes.windll.user32.IsWindowVisible(hwnd):
                found.append(hwnd)
                return False
            return True
        ctypes.windll.user32.EnumWindows(enum_proc(callback), 0)
        return found[0] if found else None

    def tile(self) -> None:
        live = [p for p in self.processes.values() if p.poll() is None]
        if not live:
            return
        screen_w = ctypes.windll.user32.GetSystemMetrics(0)
        screen_h = ctypes.windll.user32.GetSystemMetrics(1) - 48
        cols = max(1, int(len(live) ** 0.5 + 0.999))
        rows = (len(live) + cols - 1) // cols
        width, height = screen_w // cols, screen_h // rows
        for index, proc in enumerate(live):
            hwnd = self._window_for_pid(proc.pid)
            if hwnd:
                x, y = (index % cols) * width, (index // cols) * height
                ctypes.windll.user32.ShowWindow(hwnd, 9)
                ctypes.windll.user32.SetWindowPos(hwnd, 0, x, y, width, height, 0x0040)

    def _resize_client(self, hwnd: int, width: int, height: int) -> None:
        """Resize the drawable client area, excluding title bar and borders."""
        rect = wintypes.RECT(0, 0, int(width), int(height))
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -16)
        ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        adjusted = False
        adjust_for_dpi = getattr(ctypes.windll.user32, "AdjustWindowRectExForDpi", None)
        if adjust_for_dpi:
            dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
            adjusted = bool(adjust_for_dpi(ctypes.byref(rect), style, False, ex_style, dpi))
        if not adjusted:
            ctypes.windll.user32.AdjustWindowRectEx(ctypes.byref(rect), style, False, ex_style)
        outer_w, outer_h = rect.right - rect.left, rect.bottom - rect.top
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, outer_w, outer_h, 0x0002 | 0x0004 | 0x0040)

    def _monitors(self) -> list[dict]:
        monitors = []
        callback_type = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
            ctypes.POINTER(wintypes.RECT), wintypes.LPARAM,
        )

        def callback(handle, _hdc, _rect, _data):
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(info)
            if ctypes.windll.user32.GetMonitorInfoW(handle, ctypes.byref(info)):
                monitors.append({
                    "handle": handle,
                    "primary": bool(info.dwFlags & 1),
                    "left": info.rcWork.left,
                    "top": info.rcWork.top,
                    "right": info.rcWork.right,
                    "bottom": info.rcWork.bottom,
                })
            return True

        ctypes.windll.user32.EnumDisplayMonitors(0, None, callback_type(callback), 0)
        return monitors

    def _move_selected_to_monitor(self, monitor: dict) -> None:
        ids = self.selected_ids()
        if not ids:
            messagebox.showinfo(APP_NAME, "Hãy chọn ít nhất một hồ sơ đang chạy.")
            return
        windows = []
        for profile_id in ids:
            proc = self.processes.get(profile_id)
            if proc and proc.poll() is None:
                hwnd = self._window_for_pid(proc.pid)
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    # Move first so WM_DPICHANGED completes on the destination
                    # monitor. The exact 1000x1000 resize happens afterwards.
                    ctypes.windll.user32.SetWindowPos(
                        hwnd, 0, monitor["left"], monitor["top"], 0, 0,
                        0x0001 | 0x0004 | 0x0010 | 0x0040,
                    )
                    windows.append(hwnd)
        if not windows:
            messagebox.showinfo(APP_NAME, "Không tìm thấy client được mở bằng Multi.")
            return
        self.note.set("Đang chờ Windows đổi DPI rồi đặt chính xác 1000x1000...")
        self.after(400, lambda ws=windows, m=dict(monitor): self._finalize_monitor_move(ws, m))

    def _finalize_monitor_move(self, windows: list[int], monitor: dict) -> None:
        measured = []
        for hwnd in windows:
            if not ctypes.windll.user32.IsWindow(hwnd):
                continue
            self._resize_client(hwnd, 1000, 1000)
            rect = wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            measured.append((hwnd, rect.right - rect.left, rect.bottom - rect.top))
        if not measured:
            return
        work_w = monitor["right"] - monitor["left"]
        work_h = monitor["bottom"] - monitor["top"]
        cell_w = max(item[1] for item in measured)
        cell_h = max(item[2] for item in measured)
        columns = max(1, work_w // cell_w)
        rows = max(1, work_h // cell_h)
        if columns * rows < len(measured):
            messagebox.showwarning(
                APP_NAME,
                f"Màn hình chỉ đủ chỗ cho {columns * rows} client 1000x1000; "
                f"{len(measured)} client sẽ xếp chồng một phần.",
            )
        for index, (hwnd, outer_w, outer_h) in enumerate(measured):
            column = index % columns
            row = (index // columns) % rows
            x = monitor["left"] + column * cell_w
            y = monitor["top"] + row * cell_h
            ctypes.windll.user32.SetWindowPos(
                hwnd, 0, x, y, outer_w, outer_h, 0x0004 | 0x0010 | 0x0040,
            )
        kind = "màn hình chính" if monitor["primary"] else "màn hình phụ/ảo"
        self.note.set(f"Đã chuyển {len(measured)} client, vùng game đúng 1000x1000 trên {kind}")

    def toggle_selected_visibility(self) -> None:
        """Move selected clients between the primary and virtual monitor."""
        ids = self.selected_ids()
        if not ids:
            messagebox.showinfo(APP_NAME, "Hãy chọn ít nhất một hồ sơ đang chạy.")
            return
        primary = next((item for item in self._monitors() if item["primary"]), None)
        if not primary:
            messagebox.showerror(APP_NAME, "Không xác định được màn hình chính.")
            return
        on_primary = False
        found = False
        for profile_id in ids:
            proc = self.processes.get(profile_id)
            if not proc or proc.poll() is not None:
                continue
            hwnd = self._window_for_pid(proc.pid)
            if not hwnd:
                continue
            rect = wintypes.RECT()
            if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                continue
            found = True
            center_x = (rect.left + rect.right) // 2
            center_y = (rect.top + rect.bottom) // 2
            if (
                primary["left"] <= center_x < primary["right"]
                and primary["top"] <= center_y < primary["bottom"]
            ):
                on_primary = True
                break
        if not found:
            messagebox.showinfo(APP_NAME, "Không tìm thấy client được mở bằng Multi.")
            return
        if on_primary:
            self.move_selected_to_virtual()
        else:
            self.move_selected_to_primary()

    def move_selected_to_virtual(self) -> None:
        monitors = [item for item in self._monitors() if not item["primary"]]
        if not monitors:
            messagebox.showerror(
                APP_NAME,
                "Windows chưa có màn hình phụ/ảo ở chế độ Extend. Hãy bật màn hình ảo rồi thử lại.",
            )
            return
        monitor = max(
            monitors,
            key=lambda item: (item["right"] - item["left"]) * (item["bottom"] - item["top"]),
        )
        self._move_selected_to_monitor(monitor)

    def move_selected_to_primary(self) -> None:
        monitor = next((item for item in self._monitors() if item["primary"]), None)
        if not monitor:
            messagebox.showerror(APP_NAME, "Không xác định được màn hình chính.")
            return
        self._move_selected_to_monitor(monitor)

    def preview_selected(self) -> None:
        profile_id = self._active_profile_id
        if not profile_id:
            messagebox.showinfo(APP_NAME, "Hãy bấm chọn một tài khoản đang chạy.")
            return
        existing = self.previews.get(profile_id)
        if existing and existing.winfo_exists():
            existing.lift()
            return
        proc = self.processes.get(profile_id)
        if not proc or proc.poll() is not None:
            messagebox.showinfo(APP_NAME, "Hồ sơ phải được mở bằng Multi trước.")
            return
        hwnd = self._window_for_pid(proc.pid)
        if not hwnd:
            messagebox.showerror(APP_NAME, "Không tìm thấy cửa sổ client.")
            return
        try:
            self._resize_client(hwnd, 1000, 1000)
            profile = next(p for p in self.profiles if p["id"] == profile_id)
            preview = PreviewWindow(self, profile_id, profile.get("name", "KVTM"), hwnd)
            self.previews[profile_id] = preview
            # Do not move/minimize/hide the source window. GameClientJS must stay
            # fully inside the active virtual monitor or Cocos may stop rendering.
            self.note.set(
                "Live View đang xem client tại vị trí hiện tại; cửa sổ game không bị di chuyển"
            )
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Không tạo được Preview:\n{exc}")

    def _apply_display_to_process(self, proc: subprocess.Popen) -> None:
        if proc.poll() is not None:
            return
        hwnd = self._window_for_pid(proc.pid)
        if not hwnd:
            self.after(800, lambda p=proc: self._apply_display_to_process(p))
            return
        display = self.settings["display"]
        self._resize_client(hwnd, display["width"], display["height"])
        self._inject_bridge(proc.pid)
        self.note.set(
            f"Đã đặt client {display['width']}x{display['height']} px; mốc quy đổi auto {display['dpi']} DPI"
        )

    def configure_display(self) -> None:
        display = self.settings["display"]
        width = simpledialog.askinteger(APP_NAME, "Chiều rộng vùng game (px):", initialvalue=display["width"], minvalue=400, maxvalue=4000, parent=self)
        if width is None:
            return
        height = simpledialog.askinteger(APP_NAME, "Chiều cao vùng game (px):", initialvalue=display["height"], minvalue=400, maxvalue=4000, parent=self)
        if height is None:
            return
        dpi = simpledialog.askinteger(APP_NAME, "Mốc DPI dùng cho quy đổi auto:", initialvalue=display["dpi"], minvalue=96, maxvalue=600, parent=self)
        if dpi is None:
            return
        self.settings["display"] = {"width": width, "height": height, "dpi": dpi}
        save_settings(self.settings)
        for proc in self.processes.values():
            self._apply_display_to_process(proc)
        self.note.set(f"Đã lưu độ phân giải {width}x{height}, mốc {dpi} DPI")

    def _bridge_files(self) -> tuple[Path, Path] | None:
        candidates = []
        saved = str(self.settings.get("bridge_bin", "")).strip()
        if saved:
            candidates.append(Path(saved))
        candidates.extend((TOOL_DIR / "bin", TOOL_DIR))
        # Portable Suite layout: <root>\Multi and <root>\AUTO_PRO\bin.
        for parent in (TOOL_DIR, *list(TOOL_DIR.parents)[:3]):
            candidates.append(parent / "AUTO_PRO" / "bin")
        for folder in candidates:
            loader = folder / "kvtm_loader.exe"
            bridge = folder / "kvtm_bridge.dll"
            if loader.is_file() and bridge.is_file():
                return loader, bridge
        return None

    def configure_bridge(self) -> bool:
        current = str(self.settings.get("bridge_bin", "")) or str(TOOL_DIR / "bin")
        selected = filedialog.askdirectory(
            title="Chọn thư mục bin có kvtm_loader.exe và kvtm_bridge.dll",
            initialdir=current if Path(current).is_dir() else str(TOOL_DIR),
            parent=self,
        )
        if not selected:
            return False
        folder = Path(selected)
        if not (folder / "kvtm_loader.exe").is_file() or not (folder / "kvtm_bridge.dll").is_file():
            messagebox.showerror(APP_NAME, "Thư mục đã chọn thiếu kvtm_loader.exe hoặc kvtm_bridge.dll.")
            return False
        self.settings["bridge_bin"] = str(folder)
        save_settings(self.settings)
        with self._bridge_lock:
            self._bridged_pids.clear()
        self.note.set(f"Đã lưu Bridge DLL: {folder}")
        return True

    def _inject_bridge(self, pid: int) -> bool:
        files = self._bridge_files()
        if not files or pid <= 0:
            return False
        with self._bridge_lock:
            if pid in self._bridged_pids:
                return True
        loader, bridge = files
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            result = subprocess.run(
                [str(loader), str(pid), str(bridge)], capture_output=True, text=True,
                creationflags=flags, timeout=15,
            )
            if result.returncode != 0:
                self._bridge_error = (result.stderr or result.stdout or f"mã {result.returncode}").strip()
                return False
            with self._bridge_lock:
                self._bridged_pids.add(pid)
            self._bridge_error = ""
            return True
        except Exception as exc:
            self._bridge_error = str(exc)
            return False

    def _bridge_monitor(self) -> None:
        while not self._bridge_stop.wait(2.0):
            try:
                rows = running_clients()
                self.after(
                    0, lambda snapshot=rows: self._adopt_running_clients(snapshot)
                )
                if ISOLATED_INSTANCE:
                    # DEV may re-adopt only clients that exactly match one of
                    # its DPAPI-protected profiles. Injection remains restricted
                    # to self.processes, so production/old-suite clients are not
                    # touched when a ClientJS reset creates a replacement PID.
                    live = {
                        int(proc.pid) for proc in list(self.processes.values())
                        if proc and proc.poll() is None
                    }
                else:
                    live = {
                        int(row.get("ProcessId", 0)) for row in rows
                        if int(row.get("ProcessId", 0)) > 0
                    }
                if not self._bridge_files():
                    continue
                with self._bridge_lock:
                    self._bridged_pids.intersection_update(live)
                    pending = live - self._bridged_pids
                for pid in pending:
                    self._inject_bridge(pid)
            except Exception as exc:
                self._bridge_error = str(exc)

    def _on_close(self) -> None:
        self._bridge_stop.set()
        for worker in [
            *list(self._auto_workers.values()),
            *list(self._clean_auto_workers.values()),
        ]:
            try:
                if worker.poll() is None and worker.stdin:
                    worker.stdin.write('{"command":"stop"}\n')
                    worker.stdin.flush()
                    worker.terminate()
            except OSError:
                pass
        for profile_id in list(self._live_thumbnails):
            self._unregister_live_thumbnail(profile_id)
        for preview in list(self.previews.values()):
            preview.close()
        self.destroy()

    def capture_diagnostic(self) -> None:
        ids = self.selected_ids()
        if len(ids) != 1:
            messagebox.showinfo(APP_NAME, "Hãy chọn đúng một hồ sơ đang chạy.")
            return
        proc = self.processes.get(ids[0])
        if not proc or proc.poll() is not None:
            messagebox.showinfo(APP_NAME, "Hồ sơ đã chọn chưa được mở bằng tool.")
            return
        try:
            destination = APP_DIR / "diagnostics" / f"client-{proc.pid}.bmp"
            info = save_diagnostic(proc.pid, destination)
            self.note.set(f"Đã chụp {info['displayWidth']}x{info['displayHeight']}: {destination}")
            os.startfile(destination)
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Không chụp được cửa sổ:\n{exc}")

    def preview_four_floor_swipe(self) -> None:
        ids = self.selected_ids()
        if len(ids) != 1:
            messagebox.showinfo(APP_NAME, "Hãy chọn đúng một hồ sơ đang chạy.")
            return
        proc = self.processes.get(ids[0])
        if not proc or proc.poll() is not None:
            messagebox.showinfo(APP_NAME, "Hồ sơ đã chọn chưa được mở bằng tool.")
            return
        try:
            destination = APP_DIR / "diagnostics" / f"swipe-4-tang-{proc.pid}.bmp"
            info = save_four_floor_swipe_preview(proc.pid, destination)
            self.note.set(f"Swipe LD: {info['reference_start']} -> {info['reference_end']}; PC: {info['start']} -> {info['end']}")
            os.startfile(destination)
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Không tạo được ảnh swipe:\n{exc}")

    def test_four_floor_swipe(self) -> None:
        ids = self.selected_ids()
        if len(ids) != 1:
            messagebox.showinfo(APP_NAME, "Hãy chọn đúng một hồ sơ đang chạy.")
            return
        proc = self.processes.get(ids[0])
        if not proc or proc.poll() is not None:
            messagebox.showinfo(APP_NAME, "Hồ sơ đã chọn chưa được mở bằng tool.")
            return
        if not messagebox.askyesno(APP_NAME, "Gửi swipe thật (387,918) → (387,69) vào client đã chọn?"):
            return
        try:
            from pc_driver import PCDriver
            PCDriver(proc.pid, reference_size=(1000, 1000)).swipe_four_floors(duration=1.0)
            self.note.set("Đã gửi swipe thật START (387,918) → END (387,69)")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Swipe thất bại:\n{exc}")

    def _poll(self) -> None:
        self.refresh()
        self.after(1500, self._poll)


def main() -> int:
    if os.name != "nt":
        print("KVTM Multi chỉ chạy trên Windows.")
        return 1
    try:
        # Prevent Windows display scaling from changing requested client pixels.
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
    MultiApp().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
