from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from pc_driver import BITMAPINFO, capture_bgra, capture_shared_bgra


APP_TITLE = "KVTM Game Workspace"
TARGET_FPS = 20.0
RUNNING_MAP_MAX_AGE_SECONDS = 30.0
REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNTIME_RELATIVE = Path(
    "dist/KVTM-ClientJS-Suite-Multi-DEV/data-dev/running_clients.json"
)
DEV_RUNNING_MAP_CANDIDATES = tuple(
    path for path in (
        (
            Path(os.environ["KVTM_MULTI_DEV_ROOT"]) / _RUNTIME_RELATIVE
            if os.environ.get("KVTM_MULTI_DEV_ROOT")
            else None
        ),
        REPO_ROOT.parent / "Tool_KVTM_Multi_DEV" / _RUNTIME_RELATIVE,
        REPO_ROOT / _RUNTIME_RELATIVE,
    )
    if path is not None
)

MAIN_DEV_ROOT = (
    Path(os.environ["KVTM_MULTI_DEV_ROOT"])
    if os.environ.get("KVTM_MULTI_DEV_ROOT")
    else REPO_ROOT.parent / "Tool_KVTM_Multi_DEV"
)
MAIN_RUNTIME_ROOT = (
    MAIN_DEV_ROOT / "dist" / "KVTM-ClientJS-Suite-Multi-DEV"
)
BRIDGE_DIR_CANDIDATES = (
    MAIN_RUNTIME_ROOT / "Multi" / "bin",
    MAIN_RUNTIME_ROOT / "Multi",
    MAIN_RUNTIME_ROOT / "AUTO_PRO" / "bin",
)


def find_bridge_files() -> tuple[Path, Path] | None:
    for folder in BRIDGE_DIR_CANDIDATES:
        loader = folder / "kvtm_loader.exe"
        bridge = folder / "kvtm_bridge.dll"
        if loader.is_file() and bridge.is_file():
            return loader, bridge
    return None


def load_dev_client_allowlist() -> tuple[dict[int, dict], str]:
    """Read the secret-free PID/profile map published by authoritative Multi DEV."""
    reasons = []
    for running_map in DEV_RUNNING_MAP_CANDIDATES:
        try:
            age = time.time() - running_map.stat().st_mtime
            if age < 0 or age > RUNNING_MAP_MAX_AGE_SECONDS:
                reasons.append(
                    f"{running_map.parent.parent.name}: cũ {max(0, int(age))} giây"
                )
                continue
            payload = json.loads(running_map.read_text(encoding="utf-8-sig"))
            if int(payload.get("version", 0)) != 1:
                reasons.append(f"{running_map.parent.parent.name}: sai phiên bản")
                continue
            allowed: dict[int, dict] = {}
            for row in payload.get("clients", []):
                if not isinstance(row, dict):
                    continue
                pid = int(row.get("pid", 0))
                profile_id = str(row.get("profile_id") or "").strip()
                if pid <= 0 or not profile_id:
                    continue
                allowed[pid] = {
                    "profile_id": profile_id,
                    "name": str(row.get("name") or f"PID {pid}"),
                }
            return (
                allowed,
                f"allowlist DEV: {len(allowed)} profile • {running_map.parent}",
            )
        except FileNotFoundError:
            reasons.append(f"{running_map.parent.parent.name}: chưa có map")
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            reasons.append(f"{running_map.parent.parent.name}: lỗi {exc}")
    return {}, "Không có allowlist DEV mới • " + "; ".join(reasons)


def enumerate_game_windows(allowed: dict[int, dict]) -> list[dict]:
    """Return only GameClientJS windows authorized by the fresh DEV PID map."""
    user32 = ctypes.windll.user32
    rows: list[dict] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def callback(hwnd, _lparam):
        if not user32.IsWindow(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        length = user32.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(max(1, length + 1))
        user32.GetWindowTextW(hwnd, title, len(title))
        class_name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_name, len(class_name))
        text = title.value.strip()
        cls = class_name.value.strip()
        identity = allowed.get(int(pid.value))
        if identity and text and (
            "Khu Vườn Trên Mây" in text or "GameClientJS" in text or cls == "GLFW30"
        ):
            rows.append({
                "hwnd": int(hwnd),
                "pid": int(pid.value),
                "profile_id": identity["profile_id"],
                "name": identity["name"],
                "title": text,
            })
        return True

    user32.EnumWindows(callback, 0)
    unique: dict[int, dict] = {}
    for row in rows:
        unique.setdefault(row["pid"], row)
    return sorted(unique.values(), key=lambda item: (item["title"], item["pid"]))


class CaptureWorker:
    def __init__(self, pid: int, hwnd: int):
        self.pid = pid
        self.hwnd = hwnd
        self.frames: queue.Queue = queue.Queue(maxsize=1)
        self.stop_event = threading.Event()
        self.enabled = threading.Event()
        self.shared_error = ""
        self.bridge_state = "Chưa kiểm tra bridge"
        self.bridge_attempted = False
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _try_inject_bridge(self):
        if self.bridge_attempted:
            return
        self.bridge_attempted = True
        files = find_bridge_files()
        if not files:
            searched = ", ".join(str(path) for path in BRIDGE_DIR_CANDIDATES)
            self.bridge_state = f"Thiếu bridge; đã tìm: {searched}"[:220]
            return
        loader, bridge = files
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            result = subprocess.run(
                [str(loader), str(self.pid), str(bridge)],
                capture_output=True, text=True, errors="replace",
                creationflags=flags, timeout=15,
            )
            if result.returncode == 0:
                self.bridge_state = (
                    f"Đã inject {bridge.parent}; đang chờ OpenGL pipe"
                )
            else:
                detail = (result.stderr or result.stdout or "").strip()
                self.bridge_state = (
                    f"Loader rc={result.returncode}: {detail}"[:220]
                )
        except Exception as exc:
            self.bridge_state = f"Inject lỗi: {exc}"[:220]

    def _run(self):
        shared_failures = 0
        while not self.stop_event.is_set():
            if not self.enabled.wait(0.25):
                continue
            started = time.monotonic()
            try:
                raw, width, height = capture_shared_bgra(self.pid, timeout_ms=750)
                source = "OpenGL"
                shared_failures = 0
                self.shared_error = ""
                self.bridge_state = "OpenGL shared capture READY"
            except Exception as exc:
                shared_failures += 1
                self.shared_error = str(exc)[:220]
                if shared_failures >= 2:
                    self._try_inject_bridge()
                try:
                    raw, width, height = capture_bgra(self.hwnd)
                    source = "HWND"
                except Exception:
                    self.stop_event.wait(0.2)
                    continue
            frame = (raw, int(width), int(height), source)
            try:
                self.frames.put_nowait(frame)
            except queue.Full:
                try:
                    self.frames.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self.frames.put_nowait(frame)
                except queue.Full:
                    pass
            self.stop_event.wait(max(0.0, 1.0 / TARGET_FPS - (time.monotonic() - started)))

    def close(self):
        self.enabled.clear()
        self.stop_event.set()


class DeviceView(ttk.Frame):
    def __init__(self, owner, device: dict):
        super().__init__(owner)
        self.device = device
        self.worker = CaptureWorker(device["pid"], device["hwnd"])
        self.latest = None
        self.pixel_buffer = None
        self.pixel_size = 0
        self.header = ttk.Frame(self)
        self.header.pack(fill="x")
        ttk.Label(
            self.header,
            text=f"{device['name']} • PID {device['pid']}",
            anchor="w",
        ).pack(side="left", fill="x", expand=True, padx=6, pady=3)
        ttk.Button(
            self.header, text="Hiện Client", command=self.show_client
        ).pack(side="right", padx=4)
        self.canvas = tk.Canvas(self, background="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.status = tk.StringVar(value="Đang kết nối capture...")
        ttk.Label(self, textvariable=self.status, anchor="center").pack(fill="x")
        self.canvas.bind("<Expose>", lambda _event: self.paint())

    def set_live(self, enabled: bool):
        if enabled:
            self.worker.enabled.set()
        else:
            self.worker.enabled.clear()

    def poll(self):
        newest = None
        try:
            while True:
                newest = self.worker.frames.get_nowait()
        except queue.Empty:
            pass
        if newest:
            raw, width, height, source = newest
            size = len(raw)
            if self.pixel_buffer is None or self.pixel_size != size:
                self.pixel_buffer = ctypes.create_string_buffer(size)
                self.pixel_size = size
            ctypes.memmove(self.pixel_buffer, raw, size)
            self.latest = (self.pixel_buffer, width, height, source)
            self.paint()

    def paint(self):
        if not self.latest or not self.canvas.winfo_exists():
            return
        pixels, width, height, source = self.latest
        target_w = max(1, self.canvas.winfo_width())
        target_h = max(1, self.canvas.winfo_height())
        scale = min(target_w / width, target_h / height)
        draw_w, draw_h = max(1, int(width * scale)), max(1, int(height * scale))
        left, top = (target_w - draw_w) // 2, (target_h - draw_h) // 2
        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(info.bmiHeader)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = 0
        dc = ctypes.windll.user32.GetDC(self.canvas.winfo_id())
        if dc:
            try:
                ctypes.windll.gdi32.SetStretchBltMode(dc, 4)
                ctypes.windll.gdi32.StretchDIBits(
                    dc, left, top, draw_w, draw_h,
                    0, 0, width, height,
                    pixels, ctypes.byref(info), 0, 0x00CC0020,
                )
            finally:
                ctypes.windll.user32.ReleaseDC(self.canvas.winfo_id(), dc)
        if source == "OpenGL":
            detail = "OpenGL shared • AUTO/Workspace cùng PID"
        else:
            pipe_error = self.worker.shared_error or "chưa có lỗi pipe"
            detail = (
                f"HWND fallback • {self.worker.bridge_state} • pipe={pipe_error}"
            )
        self.status.set(
            f"{detail} • {width}×{height} • Live View {int(TARGET_FPS)} FPS"
        )

    def show_client(self):
        hwnd = int(self.device["hwnd"])
        user32 = ctypes.windll.user32
        if not user32.IsWindow(hwnd):
            messagebox.showerror(APP_TITLE, "Client DEV không còn chạy.")
            return
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)

    def close(self):
        self.worker.close()


class WorkspaceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1180x760")
        self.minsize(640, 420)
        self.views: list[DeviceView] = []
        self.devices: list[dict] = []
        self.mode = tk.StringVar(value="All")
        self.status = tk.StringVar(value="Sẵn sàng")
        self.identity_status = "Chưa đọc allowlist DEV"
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(50, self.refresh_devices)
        self.after(50, self._tick)

    def _build_ui(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=8, pady=6)
        ttk.Label(bar, text="Workspace mặc định", font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Label(bar, text="ClientJS và AUTO vẫn chạy khi Workspace thu nhỏ").pack(side="left", padx=12)
        ttk.Button(bar, text="Làm mới", command=self.refresh_devices).pack(side="right")
        self.selector = ttk.Combobox(bar, textvariable=self.mode, state="readonly", width=24)
        self.selector.pack(side="right", padx=6)
        self.selector.bind("<<ComboboxSelected>>", lambda _event: self.render_views())
        ttk.Label(bar, text="Device").pack(side="right")
        self.body = ttk.Frame(self)
        self.body.pack(fill="both", expand=True, padx=8, pady=(0, 6))
        ttk.Label(self, textvariable=self.status, anchor="w").pack(fill="x", padx=8, pady=(0, 5))

    def refresh_devices(self):
        try:
            allowed, self.identity_status = load_dev_client_allowlist()
            devices = enumerate_game_windows(allowed)
        except Exception as exc:
            self.status.set(f"Không thể dò ClientJS DEV: {exc}")
            return
        signature = [(d["pid"], d["hwnd"]) for d in devices]
        if signature == [(d["pid"], d["hwnd"]) for d in self.devices]:
            if not devices:
                self.status.set(f"0 Device • {self.identity_status}")
            return
        self.devices = devices
        values = ["All"] + [f"{d['name']} | PID {d['pid']}" for d in devices]
        self.selector.configure(values=values)
        if self.mode.get() not in values:
            self.mode.set("All")
        self.render_views()

    def render_views(self):
        for view in self.views:
            view.close()
            view.destroy()
        self.views.clear()
        selected = self.devices
        if self.mode.get() != "All":
            try:
                pid = int(self.mode.get().rsplit("PID ", 1)[1])
                selected = [d for d in self.devices if d["pid"] == pid]
            except (IndexError, ValueError):
                selected = []
        if not selected:
            ttk.Label(self.body, text="Chưa có GameClientJS đang chạy", anchor="center").pack(fill="both", expand=True)
            self.status.set(f"0 Device • {self.identity_status}")
            return
        columns = 1 if len(selected) == 1 else 2
        for index, device in enumerate(selected):
            view = DeviceView(self.body, device)
            view.grid(row=index // columns, column=index % columns, sticky="nsew", padx=2, pady=2)
            self.views.append(view)
        for column in range(columns):
            self.body.columnconfigure(column, weight=1, uniform="device")
        for row in range((len(selected) + columns - 1) // columns):
            self.body.rowconfigure(row, weight=1, uniform="device")
        self.status.set(
            f"{len(selected)} Device DEV • Capture nền độc lập với AUTO"
        )

    def _is_visible(self) -> bool:
        return self.state() != "iconic" and bool(self.winfo_viewable())

    def _tick(self):
        visible = self._is_visible()
        for view in tuple(self.views):
            view.set_live(visible)
            if visible:
                view.poll()
        self.after(50 if visible else 500, self._tick)

    def close(self):
        for view in self.views:
            view.close()
        self.destroy()


def main() -> int:
    if os.name != "nt":
        print("KVTM Workspace chỉ chạy trên Windows.")
        return 1
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        pass
    WorkspaceApp().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
