from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import queue
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
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        while not self.stop_event.is_set():
            if not self.enabled.wait(0.25):
                continue
            started = time.monotonic()
            try:
                raw, width, height = capture_shared_bgra(self.pid, timeout_ms=750)
                source = "OpenGL"
            except Exception:
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
        self.attached = False
        self.original_parent = None
        self.original_style = None
        self.original_ex_style = None
        self.original_rect = None
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
        self.detach_button = ttk.Button(
            self.header, text="Tách ra Desktop", command=self.detach_from_workspace
        )
        self.detach_button.pack(side="right", padx=4)
        self.detach_button.configure(state="disabled")
        self.attach_button = ttk.Button(
            self.header, text="Gắn vào Workspace", command=self.attach_to_workspace
        )
        self.attach_button.pack(side="right", padx=4)
        self.canvas = tk.Canvas(self, background="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.status = tk.StringVar(value="Đang kết nối capture...")
        ttk.Label(self, textvariable=self.status, anchor="center").pack(fill="x")
        self.canvas.bind("<Expose>", lambda _event: self.paint())
        self.canvas.bind("<Configure>", lambda _event: self._layout_attached())

    def set_live(self, enabled: bool):
        enabled = bool(enabled and not self.attached)
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
        if self.attached or not self.latest or not self.canvas.winfo_exists():
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
        self.status.set(f"{source} • {width}×{height} • Live View {int(TARGET_FPS)} FPS")

    def _layout_attached(self):
        if not self.attached:
            return
        hwnd = int(self.device["hwnd"])
        if not ctypes.windll.user32.IsWindow(hwnd):
            return
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        ctypes.windll.user32.SetWindowPos(
            hwnd, 0, 0, 0, width, height,
            0x0004 | 0x0010 | 0x0040,
        )

    def attach_to_workspace(self):
        if self.attached:
            return
        user32 = ctypes.windll.user32
        user32.GetParent.argtypes = [wintypes.HWND]
        user32.GetParent.restype = wintypes.HWND
        user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
        user32.SetParent.restype = wintypes.HWND
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = wintypes.LONG
        user32.SetWindowLongW.argtypes = [
            wintypes.HWND, ctypes.c_int, wintypes.LONG,
        ]
        user32.SetWindowLongW.restype = wintypes.LONG
        hwnd = int(self.device["hwnd"])
        self.status.set("Đang gắn ClientJS vào Workspace...")
        self.update_idletasks()
        if not user32.IsWindow(hwnd):
            messagebox.showerror(APP_TITLE, "Client DEV không còn chạy.")
            return
        self.canvas.update_idletasks()
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            messagebox.showerror(APP_TITLE, "Không đọc được vị trí cửa sổ ClientJS.")
            return
        self.original_parent = int(user32.GetParent(hwnd) or 0)
        self.original_style = int(user32.GetWindowLongW(hwnd, -16))
        self.original_ex_style = int(user32.GetWindowLongW(hwnd, -20))
        self.original_rect = (
            int(rect.left), int(rect.top),
            int(rect.right - rect.left), int(rect.bottom - rect.top),
        )
        child_style = (self.original_style & ~0x80000000) | 0x40000000 | 0x10000000
        ctypes.windll.kernel32.SetLastError(0)
        user32.SetWindowLongW(hwnd, -16, child_style)
        user32.SetParent(hwnd, self.canvas.winfo_id())
        if int(user32.GetParent(hwnd) or 0) != int(self.canvas.winfo_id()):
            user32.SetWindowLongW(hwnd, -16, self.original_style)
            messagebox.showerror(
                APP_TITLE,
                "Windows từ chối gắn ClientJS vào Workspace; đã giữ nguyên cửa sổ.",
            )
            return
        self.attached = True
        self.worker.enabled.clear()
        self._layout_attached()
        self.attach_button.configure(state="disabled")
        self.detach_button.configure(state="normal")
        self.status.set("Đã gắn ClientJS thật vào Workspace • AUTO vẫn theo PID")

    def detach_from_workspace(self):
        if not self.attached:
            return
        user32 = ctypes.windll.user32
        hwnd = int(self.device["hwnd"])
        if not user32.IsWindow(hwnd):
            self.attached = False
            return
        user32.SetParent(hwnd, int(self.original_parent or 0))
        if self.original_style is not None:
            user32.SetWindowLongW(hwnd, -16, int(self.original_style))
        if self.original_ex_style is not None:
            user32.SetWindowLongW(hwnd, -20, int(self.original_ex_style))
        left, top, width, height = self.original_rect or (0, 0, 1000, 1000)
        user32.SetWindowPos(
            hwnd, 0, left, top, width, height,
            0x0004 | 0x0010 | 0x0020 | 0x0040,
        )
        self.attached = False
        self.attach_button.configure(state="normal")
        self.detach_button.configure(state="disabled")
        self.status.set("Đã trả ClientJS về Desktop")
        self.worker.enabled.set()

    def close(self):
        self.detach_from_workspace()
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
