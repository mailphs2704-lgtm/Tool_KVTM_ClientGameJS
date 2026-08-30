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
DEFAULT_CLIENT = Path(r"C:\Program Files\ZingPlay\data\flutter_assets\assets\runtime\GameClientJS.exe")
DEFAULT_GAME = Path(os.environ.get("APPDATA", Path.home())) / "VNG Corporation" / "ZingPlay" / "zpp" / GAME_ID / "game"
DEFAULT_DISPLAY = {"width": 1000, "height": 1000, "dpi": 240}
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
    return {"display": {
        "width": int(display.get("width", DEFAULT_DISPLAY["width"])),
        "height": int(display.get("height", DEFAULT_DISPLAY["height"])),
        "dpi": int(display.get("dpi", DEFAULT_DISPLAY["dpi"])),
    }, "bridge_bin": str(saved.get("bridge_bin", "")) if isinstance(saved, dict) else ""}


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
        self.geometry("1180x760")
        self.minsize(940, 620)
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
        self.after(1500, self._poll)

    def _keep_control_on_primary(self) -> None:
        """Keep the Multi control panel visible when clients move off-screen."""
        primary = next((item for item in self._monitors() if item["primary"]), None)
        if not primary:
            return
        self.update_idletasks()
        work_w = primary["right"] - primary["left"]
        work_h = primary["bottom"] - primary["top"]
        width = min(max(760, self.winfo_width()), work_w)
        height = min(max(480, self.winfo_height()), work_h)
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
            padding=(12, 7), font=("Segoe UI", 9),
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
            "AutoKey.TLabel", background="#ffffff", foreground="#64748b",
            font=("Segoe UI Semibold", 8),
        )
        style.configure(
            "AutoValue.TLabel", background="#ffffff", foreground="#17233b",
            font=("Segoe UI Semibold", 10),
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
        style.configure("Sash", sashthickness=6, background="#dbe3ef")

        header = ttk.Frame(self, padding=(18, 13), style="Header.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="KVTM MULTI", style="Title.TLabel").pack(side="left")
        ttk.Label(
            header, text="Quản lý ClientJS và AUTO tập trung",
            style="Subtitle.TLabel",
        ).pack(side="left", padx=(18, 0), pady=(5, 0))

        # Scroll the complete workspace when the window is shorter than its
        # requested content. Header and bottom status remain permanently visible.
        body = ttk.Frame(self, style="App.TFrame")
        body.pack(fill="both", expand=True)
        self.content_canvas = tk.Canvas(
            body, background="#f3f6fa", highlightthickness=0, borderwidth=0
        )
        content_scroll = ttk.Scrollbar(
            body, orient="vertical", command=self.content_canvas.yview
        )
        self.content_canvas.configure(yscrollcommand=content_scroll.set)
        content_scroll.pack(side="right", fill="y")
        self.content_canvas.pack(side="left", fill="both", expand=True)
        self.content_frame = ttk.Frame(self.content_canvas, style="App.TFrame")
        self._content_window = self.content_canvas.create_window(
            (0, 0), window=self.content_frame, anchor="nw"
        )
        self.content_frame.bind(
            "<Configure>",
            lambda _event: self.content_canvas.configure(
                scrollregion=self.content_canvas.bbox("all")
            ),
        )
        self.content_canvas.bind(
            "<Configure>",
            lambda event: self.content_canvas.itemconfigure(
                self._content_window, width=event.width
            ),
        )
        self.content_canvas.bind("<MouseWheel>", self._scroll_content)
        self.content_frame.bind("<MouseWheel>", self._scroll_content)
        self.bind_all("<MouseWheel>", self._scroll_content, add="+")
        self.content_canvas.bind("<Button-4>", self._scroll_content)
        self.content_canvas.bind("<Button-5>", self._scroll_content)

        controls = ttk.LabelFrame(
            self.content_frame, text="BẢNG ĐIỀU KHIỂN", padding=(10, 8), style="Panel.TLabelframe"
        )
        controls.pack(fill="x", padx=12, pady=(8, 8))
        for column in range(6):
            controls.columnconfigure(column, weight=1, uniform="control")

        buttons = (
            (0, 0, "Lưu client", self.capture),
            (0, 1, "Mở chọn", self.launch_selected),
            (0, 2, "Mở tất cả", self.launch_all),
            (0, 3, "Dừng chọn", self.stop_selected),
            (0, 4, "Xóa hồ sơ", self.delete_selected),
            (0, 5, "Bridge DLL", self.configure_bridge),
            (1, 0, "Xếp cửa sổ", self.tile),
            (1, 1, "Sang màn ảo", self.move_selected_to_virtual),
            (1, 2, "Về màn chính", self.move_selected_to_primary),
            (1, 3, "Độ phân giải", self.configure_display),
            (1, 4, "Chụp ảnh", self.capture_diagnostic),
        )
        for row, column, label, command in buttons:
            ttk.Button(
                controls, text=label, command=command, style="Action.TButton"
            ).grid(row=row, column=column, sticky="ew", padx=4, pady=4)

        # Main workspace: account status on the left, selected account data on the right.
        workspace = ttk.Panedwindow(self.content_frame, orient="horizontal", height=420)
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
        for row, (label, key) in enumerate(fields):
            ttk.Label(fields_frame, text=label.upper(), style="Key.TLabel").grid(
                row=row, column=0, sticky="w", padx=(2, 18), pady=6
            )
            value = tk.StringVar(value="—")
            self.detail_vars[key] = value
            ttk.Label(
                fields_frame, textvariable=value, style="Value.TLabel"
            ).grid(row=row, column=1, sticky="w", pady=6)
        fields_frame.columnconfigure(1, weight=1)

        self._build_auto_panel()

        self.note = tk.StringVar(value="Sẵn sàng")
        ttk.Label(self, textvariable=self.note, style="Status.TLabel").pack(fill="x")

    def _scroll_content(self, event) -> str:
        """Scroll the responsive content area with mouse wheel or Linux buttons."""
        if getattr(event, "num", None) == 4:
            delta = -3
        elif getattr(event, "num", None) == 5:
            delta = 3
        else:
            wheel = int(getattr(event, "delta", 0))
            delta = -int(wheel / 120) * 3 if wheel else 0
        if delta:
            self.content_canvas.yview_scroll(delta, "units")
        return "break"

    def _build_auto_panel(self) -> None:
        """Build the ClientJS AUTO control surface below the account workspace."""
        panel = ttk.LabelFrame(
            self.content_frame, text="AUTO CLIENTJS", padding=(12, 9), style="Auto.TLabelframe"
        )
        panel.pack(fill="x", padx=12, pady=(0, 7))

        panel.columnconfigure(0, weight=3)
        panel.columnconfigure(1, weight=2)
        panel.columnconfigure(2, weight=2)
        panel.columnconfigure(3, weight=3)

        function_box = ttk.Frame(panel, style="Detail.TFrame")
        function_box.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        ttk.Label(function_box, text="CHỨC NĂNG", style="AutoKey.TLabel").pack(anchor="w")
        self.auto_function = tk.StringVar(value=self._auto_function_names[0])
        self.auto_function_combo = ttk.Combobox(
            function_box, textvariable=self.auto_function,
            values=self._auto_function_names, state="readonly", height=8,
        )
        self.auto_function_combo.pack(fill="x", pady=(4, 0))

        target_box = ttk.Frame(panel, style="Detail.TFrame")
        target_box.grid(row=0, column=1, sticky="ew", padx=(0, 12))
        ttk.Label(target_box, text="TÀI KHOẢN ÁP DỤNG", style="AutoKey.TLabel").pack(anchor="w")
        self.auto_target = tk.StringVar(value="Chưa chọn tài khoản")
        ttk.Label(
            target_box, textvariable=self.auto_target, style="AutoValue.TLabel",
            anchor="w",
        ).pack(fill="x", pady=(7, 0))

        state_box = ttk.Frame(panel, style="Detail.TFrame")
        state_box.grid(row=0, column=2, sticky="ew", padx=(0, 12))
        ttk.Label(state_box, text="TRẠNG THÁI", style="AutoKey.TLabel").pack(anchor="w")
        self.auto_status = tk.StringVar(value="Sẵn sàng")
        ttk.Label(
            state_box, textvariable=self.auto_status, style="AutoValue.TLabel",
            anchor="w",
        ).pack(fill="x", pady=(7, 0))

        progress_box = ttk.Frame(panel, style="Detail.TFrame")
        progress_box.grid(row=0, column=3, sticky="ew")
        progress_header = ttk.Frame(progress_box, style="Detail.TFrame")
        progress_header.pack(fill="x")
        ttk.Label(progress_header, text="TIẾN TRÌNH", style="AutoKey.TLabel").pack(side="left")
        self.auto_progress_text = tk.StringVar(value="0%")
        ttk.Label(
            progress_header, textvariable=self.auto_progress_text,
            style="AutoKey.TLabel",
        ).pack(side="right")
        self.auto_progress = tk.DoubleVar(value=0.0)
        ttk.Progressbar(
            progress_box, variable=self.auto_progress, maximum=100,
            style="Auto.Horizontal.TProgressbar",
        ).pack(fill="x", pady=(7, 0))

        action_row = ttk.Frame(panel, style="Detail.TFrame")
        action_row.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(10, 0))
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

    def _auto_ui_start(self) -> None:
        ids = self.selected_ids()
        if not ids:
            messagebox.showinfo(APP_NAME, "Hãy chọn ít nhất một tài khoản để chạy AUTO.")
            return
        function_name = self.auto_function.get()
        function_spec = self._auto_functions_by_label.get(function_name)
        if not function_spec:
            messagebox.showinfo(APP_NAME, "Hãy chọn chức năng AUTO đã được cho phép.")
            return
        self.auto_status.set("Chờ kết nối engine")
        self.auto_progress.set(0)
        self.auto_progress_text.set("0%")
        self.auto_scope_note.set(
            f"Function {function_spec.get('auto_pro_function_id')} • "
            f"đã chuẩn bị {len(ids)} tài khoản • chưa gửi lệnh thao tác game"
        )
        self.note.set("Đang kiểm tra runtime AUTO PRO cho Function 136...")
        threading.Thread(
            target=self._probe_auto_runtime,
            args=(function_spec,),
            daemon=True,
        ).start()

    def _probe_auto_runtime(self, function_spec: dict) -> None:
        """Validate the recovered AUTO PRO libraries without touching the game."""
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
            self.after(0, lambda p=payload: self._auto_probe_ok(p))
        except Exception as exc:
            self.after(0, lambda error=str(exc): self._auto_probe_failed(error))

    def _auto_probe_ok(self, payload: dict) -> None:
        self.auto_status.set("Thư viện sẵn sàng")
        self.auto_progress.set(10)
        self.auto_progress_text.set("10%")
        self.auto_scope_note.set(
            f"Đã xác nhận {payload.get('entrypoint')} • chưa thao tác game"
        )
        self.note.set("AUTO PRO Function 136 và các thư viện ClientJS đã sẵn sàng.")

    def _auto_probe_failed(self, error: str) -> None:
        self.auto_status.set("Lỗi thư viện")
        self.auto_progress.set(0)
        self.auto_progress_text.set("0%")
        self.auto_scope_note.set("Runtime probe thất bại")
        messagebox.showerror(APP_NAME, f"Không nạp được thư viện AUTO PRO:\n{error}")

    def _auto_ui_pause(self) -> None:
        self.auto_status.set("Tạm dừng")
        self.auto_scope_note.set("UI đã ghi nhận tạm dừng • engine chưa được kết nối")

    def _auto_ui_stop(self) -> None:
        self.auto_status.set("Đã dừng")
        self.auto_progress.set(0)
        self.auto_progress_text.set("0%")
        self.auto_scope_note.set("Không có thao tác AUTO đang chạy")

    def _auto_ui_configure(self) -> None:
        messagebox.showinfo(
            APP_NAME,
            "Khung cấu hình AUTO sẽ được nối với cấu hình AUTO PRO ở bước tiếp theo.\n\n"
            "AUTO LD hiện tại không bị thay đổi.",
        )

    def _create_account_tree(self, parent, title: str):
        box = ttk.LabelFrame(
            parent, text=title.upper(), padding=7, style="Panel.TLabelframe"
        )
        parent.add(box, weight=1)
        tree = ttk.Treeview(
            box, columns=("name", "pid"), show=("tree", "headings"),
            selectmode="browse", style="Account.Treeview",
        )
        tree.heading("#0", text="Chọn")
        tree.column("#0", width=54, minwidth=54, stretch=False, anchor="center")
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
            tree.item(profile_id, text="☑" if profile_id in self._checked_profiles else "☐")
        self._show_account_details(profile_id)
        self._refresh_auto_target()

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
                text="☑" if profile_id in self._checked_profiles else "☐",
                values=(profile.get("name", "Chưa đặt tên"), proc.pid if alive else "—"),
                tags=("online" if alive else "offline",),
            )
            if profile_id == self._active_profile_id:
                target.selection_set(profile_id)
        if self._active_profile_id not in valid_ids:
            self._active_profile_id = None
        self._show_account_details(self._active_profile_id)
        self._refresh_auto_target()

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
                if ISOLATED_INSTANCE:
                    # A development instance must never adopt or inject into
                    # clients owned by the production Multi/AUTO process.
                    live = {
                        int(proc.pid) for proc in list(self.processes.values())
                        if proc and proc.poll() is None
                    }
                else:
                    rows = running_clients()
                    self.after(0, lambda snapshot=rows: self._adopt_running_clients(snapshot))
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
