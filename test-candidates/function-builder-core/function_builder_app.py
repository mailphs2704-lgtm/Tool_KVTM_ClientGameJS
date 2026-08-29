from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import math
from pathlib import Path
import shutil
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from kvtm_function_core import AutoFunction, FunctionRecorder, FunctionRuntime, Step
from game_client_engine import BridgeClient, capture_bgra, find_game_window


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp"}

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


class DwmRecorderWindow(tk.Toplevel):
    """Smooth DWM view; only mouse coordinates pass through Python."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.source_hwnd = owner.engine.hwnd
        self.thumbnail = ctypes.c_void_p()
        self._closing = False
        self._drag_points = []
        self._drag_started = 0.0
        self.title(f"Live Recorder - PID {owner.pid}")
        self.configure(background="black")
        self.geometry("700x700")
        self.minsize(300, 300)
        self.update_idletasks()

        dwm = ctypes.windll.dwmapi
        dwm.DwmRegisterThumbnail.argtypes = [
            wintypes.HWND, wintypes.HWND, ctypes.POINTER(ctypes.c_void_p)
        ]
        dwm.DwmRegisterThumbnail.restype = ctypes.c_long
        dwm.DwmUpdateThumbnailProperties.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(DWM_THUMBNAIL_PROPERTIES)
        ]
        dwm.DwmUpdateThumbnailProperties.restype = ctypes.c_long
        dwm.DwmUnregisterThumbnail.argtypes = [ctypes.c_void_p]
        dwm.DwmUnregisterThumbnail.restype = ctypes.c_long

        user32 = ctypes.windll.user32
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        destination = user32.GetAncestor(self.winfo_id(), 2) or self.winfo_id()
        result = dwm.DwmRegisterThumbnail(destination, self.source_hwnd, ctypes.byref(self.thumbnail))
        if result < 0:
            raise OSError(f"DwmRegisterThumbnail loi 0x{result & 0xffffffff:08X}")

        self.bind("<Configure>", self._update_thumbnail)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", self._release)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after_idle(self._update_thumbnail)

    def _content_rect(self):
        width, height = max(1, self.winfo_width()), max(1, self.winfo_height())
        side = min(width, height)
        left, top = (width - side) // 2, (height - side) // 2
        return left, top, side

    def _logical(self, event):
        left, top, side = self._content_rect()
        return (
            max(0.0, min(1000.0, (event.x - left) * 1000.0 / side)),
            max(0.0, min(1000.0, (event.y - top) * 1000.0 / side)),
        )

    def _update_thumbnail(self, _event=None):
        if self._closing or not self.thumbnail.value:
            return
        left, top, side = self._content_rect()
        props = DWM_THUMBNAIL_PROPERTIES()
        props.dwFlags = (
            DWM_TNP_RECTDESTINATION | DWM_TNP_VISIBLE |
            DWM_TNP_SOURCECLIENTAREAONLY
        )
        props.rcDestination = wintypes.RECT(left, top, left + side, top + side)
        props.fVisible = True
        props.fSourceClientAreaOnly = True
        ctypes.windll.dwmapi.DwmUpdateThumbnailProperties(self.thumbnail, ctypes.byref(props))

    def _press(self, event):
        import time
        point = self._logical(event)
        self._drag_points = [point]
        self._drag_started = time.monotonic()
        self.owner.recorder.swipe_start(*point, now=self._drag_started)

    def _drag(self, event):
        point = self._logical(event)
        self._drag_points.append(point)
        self.owner.recorder.swipe_move(*point)

    def _release(self, event):
        import time
        point = self._logical(event)
        start = self._drag_points[0]
        moved = any(
            abs(x - start[0]) + abs(y - start[1]) > 5
            for x, y in self._drag_points[1:]
        )
        try:
            if moved:
                self.owner.recorder.swipe_end(*point, now=time.monotonic())
                step = self.owner.recorder.function.steps[-1]
                self.owner.engine.swipe_points(
                    [tuple(item) for item in step.data["points"]],
                    step.data["duration"],
                )
            else:
                self.owner.recorder._swipe = None
                self.owner.recorder.click(*point)
                self.owner.engine.click(*point)
            self.owner.refresh_steps()
            self.owner.status_var.set("Da ghi thao tac tu DWM Live")
        except Exception as exc:
            messagebox.showerror("Ghi thao tac loi", str(exc), parent=self)

    def close(self):
        if self._closing:
            return
        self._closing = True
        if self.thumbnail.value:
            ctypes.windll.dwmapi.DwmUnregisterThumbnail(self.thumbnail)
            self.thumbnail = ctypes.c_void_p()
        self.owner.live_window = None
        self.destroy()


class GameEngineAdapter:
    def __init__(self, pid: int):
        self.pid = int(pid)
        self.hwnd = find_game_window(pid)
        self.bridge = BridgeClient(pid)
        self.bridge.ping()

    def click(self, x: float, y: float) -> None:
        self.bridge.touch("DOWN", x, y)
        self.bridge.touch("UP", x, y)

    def swipe_points(self, points, duration: float) -> None:
        self.bridge.swipe_points(list(points), duration)

    def capture(self):
        return capture_bgra(self.hwnd)

    def find_image(self, asset: Path, confidence: float):
        try:
            import cv2
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("Can cai opencv-python va numpy de nhan dien anh") from exc
        raw, geometry = self.capture()
        screen = np.frombuffer(raw, dtype=np.uint8).reshape(
            geometry.height, geometry.width, 4
        )[:, :, :3]
        if (geometry.width, geometry.height) != (1000, 1000):
            screen = cv2.resize(screen, (1000, 1000), interpolation=cv2.INTER_AREA)
        template = cv2.imread(str(asset), cv2.IMREAD_COLOR)
        if template is None:
            raise RuntimeError(f"Khong doc duoc anh {asset.name}")
        if template.shape[0] > screen.shape[0] or template.shape[1] > screen.shape[1]:
            return None
        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        _minimum, maximum, _min_location, location = cv2.minMaxLoc(result)
        if maximum < confidence:
            return None
        return (
            location[0] + template.shape[1] / 2,
            location[1] + template.shape[0] / 2,
        )


class WindowsFileDrop:
    WM_DROPFILES = 0x0233
    GWLP_WNDPROC = -4

    def __init__(self, root: tk.Tk, callback):
        self.root = root
        self.callback = callback
        self.hwnd = int(root.winfo_id())
        self.shell32 = ctypes.windll.shell32
        self.user32 = ctypes.windll.user32
        self.proc_type = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
            wintypes.WPARAM, wintypes.LPARAM,
        )
        self.user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        self.user32.SetWindowLongPtrW.restype = ctypes.c_void_p
        self.user32.CallWindowProcW.argtypes = [
            ctypes.c_void_p, wintypes.HWND, wintypes.UINT,
            wintypes.WPARAM, wintypes.LPARAM,
        ]
        self.user32.CallWindowProcW.restype = ctypes.c_ssize_t
        self._proc = self.proc_type(self._window_proc)
        self._old_proc = self.user32.SetWindowLongPtrW(
            self.hwnd, self.GWLP_WNDPROC, ctypes.cast(self._proc, ctypes.c_void_p)
        )
        self.shell32.DragAcceptFiles(self.hwnd, True)

    def _window_proc(self, hwnd, message, wp, lp):
        if message == self.WM_DROPFILES:
            count = self.shell32.DragQueryFileW(wp, 0xFFFFFFFF, None, 0)
            paths = []
            for index in range(count):
                length = self.shell32.DragQueryFileW(wp, index, None, 0)
                buffer = ctypes.create_unicode_buffer(length + 1)
                self.shell32.DragQueryFileW(wp, index, buffer, len(buffer))
                paths.append(Path(buffer.value))
            self.shell32.DragFinish(wp)
            self.root.after(0, self.callback, paths)
            return 0
        return self.user32.CallWindowProcW(self._old_proc, hwnd, message, wp, lp)


class FunctionBuilderApp(tk.Tk):
    def __init__(self, pid: int, workspace: Path):
        super().__init__()
        self.pid = int(pid)
        self.workspace = workspace.resolve()
        self.assets = self.workspace / "assets"
        self.functions = self.workspace / "functions"
        self.assets.mkdir(parents=True, exist_ok=True)
        self.functions.mkdir(parents=True, exist_ok=True)
        self.engine = GameEngineAdapter(pid)
        self.recorder = FunctionRecorder()
        self.preview = None
        self.preview_source = None
        self.preview_width = 1
        self.preview_height = 1
        self.drag_points = []
        self.drag_start_time = 0
        self.live_window = None
        self.title(f"KVTM Function Builder - PID {pid}")
        self.geometry("1240x760")
        self.minsize(980, 620)
        self._build_ui()
        try:
            self._drop = WindowsFileDrop(self, self.import_assets)
        except Exception:
            self._drop = None
            self.status_var.set("Keo-tha khong san sang; dung nut Them anh")
        self.refresh_assets()
        self.refresh_steps()
        self.after(150, self.open_live_recorder)

    def _build_ui(self):
        toolbar = ttk.Frame(self, padding=6)
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Ten chuc nang:").pack(side="left")
        self.name_var = tk.StringVar(value="Chuc nang moi")
        ttk.Entry(toolbar, textvariable=self.name_var, width=30).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Chup lai", command=self.capture_preview).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Mo Live DWM", command=self.open_live_recorder).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Chay thu", command=self.run_function).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Luu JSON", command=self.save_function).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Mo JSON", command=self.load_function).pack(side="left", padx=3)
        self.status_var = tk.StringVar(value="San sang")
        ttk.Label(toolbar, textvariable=self.status_var).pack(side="right")

        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        asset_frame = ttk.LabelFrame(body, text="Thu vien anh - keo tha file vao tool", padding=6)
        self.asset_list = tk.Listbox(asset_frame, width=28, exportselection=False)
        self.asset_list.pack(fill="both", expand=True)
        asset_buttons = ttk.Frame(asset_frame)
        asset_buttons.pack(fill="x", pady=(5, 0))
        ttk.Button(asset_buttons, text="Them anh", command=self.browse_assets).pack(side="left")
        ttk.Button(asset_buttons, text="Cho anh", command=self.add_wait_image).pack(side="left", padx=3)
        ttk.Button(asset_buttons, text="Click anh", command=self.add_click_image).pack(side="left")
        body.add(asset_frame, weight=1)

        preview_frame = ttk.LabelFrame(body, text="Live View - click hoac keo de ghi thao tac", padding=4)
        self.canvas = tk.Canvas(preview_frame, background="black", width=640, height=640)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        body.add(preview_frame, weight=3)

        step_frame = ttk.LabelFrame(body, text="Cac buoc", padding=6)
        self.step_tree = ttk.Treeview(step_frame, columns=("index", "type", "detail"), show="headings")
        self.step_tree.heading("index", text="#")
        self.step_tree.heading("type", text="Loai")
        self.step_tree.heading("detail", text="Du lieu")
        self.step_tree.column("index", width=35, stretch=False)
        self.step_tree.column("type", width=95, stretch=False)
        self.step_tree.column("detail", width=250)
        self.step_tree.pack(fill="both", expand=True)
        controls = ttk.Frame(step_frame)
        controls.pack(fill="x", pady=(5, 0))
        ttk.Button(controls, text="Cho", command=self.add_wait).pack(side="left")
        ttk.Button(controls, text="Len", command=lambda: self.move_step(-1)).pack(side="left", padx=2)
        ttk.Button(controls, text="Xuong", command=lambda: self.move_step(1)).pack(side="left")
        ttk.Button(controls, text="Xoa", command=self.delete_step).pack(side="right")
        body.add(step_frame, weight=2)

    def capture_preview(self):
        try:
            raw, geometry = self.engine.capture()
            try:
                import numpy as np
                frame = np.frombuffer(raw, dtype=np.uint8).reshape(geometry.height, geometry.width, 4)
                rgb = frame[:, :, [2, 1, 0]].tobytes()
            except ImportError:
                rgb = bytearray(geometry.width * geometry.height * 3)
                for source in range(0, len(raw), 4):
                    target = source // 4 * 3
                    rgb[target:target + 3] = (raw[source + 2], raw[source + 1], raw[source])
                rgb = bytes(rgb)
            ppm = f"P6\n{geometry.width} {geometry.height}\n255\n".encode() + rgb
            preview_file = self.workspace / ".live-preview.ppm"
            preview_file.write_bytes(ppm)
            self.preview_source = tk.PhotoImage(file=str(preview_file), format="PPM")
            canvas_width, canvas_height = self._display_size()
            available = max(1, min(canvas_width, canvas_height))
            factor = max(1, math.ceil(max(geometry.width, geometry.height) / available))
            self.preview = self.preview_source.subsample(factor, factor)
            self.preview_width = self.preview.width()
            self.preview_height = self.preview.height()
            self.canvas.delete("all")
            width, height = self._display_size()
            self.canvas.create_image(width / 2, height / 2, image=self.preview, anchor="center")
            self.status_var.set(f"Capture {geometry.width}x{geometry.height}")
        except Exception as exc:
            messagebox.showerror("Capture loi", str(exc))

    def open_live_recorder(self):
        try:
            if self.live_window and self.live_window.winfo_exists():
                self.live_window.lift()
                self.live_window.focus_force()
                return
            self.live_window = DwmRecorderWindow(self)
            self.status_var.set("DWM Live Recorder dang mo")
        except Exception as exc:
            self.live_window = None
            messagebox.showerror("DWM Live loi", str(exc))

    def _display_size(self):
        return max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())

    def _logical(self, event):
        width, height = self._display_size()
        left = (width - self.preview_width) / 2
        top = (height - self.preview_height) / 2
        x = max(0, min(1000, (event.x - left) * 1000 / self.preview_width))
        y = max(0, min(1000, (event.y - top) * 1000 / self.preview_height))
        return x, y

    def on_press(self, event):
        import time
        point = self._logical(event)
        self.drag_points = [point]
        self.drag_start_time = time.monotonic()
        self.recorder.swipe_start(*point, now=self.drag_start_time)

    def on_drag(self, event):
        point = self._logical(event)
        self.drag_points.append(point)
        self.recorder.swipe_move(*point)

    def on_release(self, event):
        import time
        point = self._logical(event)
        moved = len(self.drag_points) > 1 and any(
            abs(x - self.drag_points[0][0]) + abs(y - self.drag_points[0][1]) > 5
            for x, y in self.drag_points[1:]
        )
        if moved:
            self.recorder.swipe_end(*point, now=time.monotonic())
            step = self.recorder.function.steps[-1]
            self.engine.swipe_points(
                [tuple(item) for item in step.data["points"]], step.data["duration"]
            )
        else:
            self.recorder._swipe = None
            self.recorder.click(*point)
            self.engine.click(*point)
        self.refresh_steps()
        self.status_var.set("Da ghi thao tac")

    def refresh_assets(self):
        self.asset_list.delete(0, "end")
        for path in sorted(self.assets.iterdir()):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                self.asset_list.insert("end", path.name)

    def browse_assets(self):
        selected = filedialog.askopenfilenames(filetypes=[("Image", "*.png *.jpg *.jpeg *.bmp")])
        self.import_assets([Path(item) for item in selected])

    def import_assets(self, paths):
        imported = 0
        for source in paths:
            if source.is_file() and source.suffix.lower() in IMAGE_EXTENSIONS:
                destination = self.assets / source.name
                counter = 2
                while destination.exists() and source.resolve() != destination.resolve():
                    destination = self.assets / f"{source.stem}_{counter}{source.suffix.lower()}"
                    counter += 1
                if source.resolve() != destination.resolve():
                    shutil.copy2(source, destination)
                imported += 1
        self.refresh_assets()
        self.status_var.set(f"Da them {imported} anh")

    def selected_asset(self):
        selection = self.asset_list.curselection()
        if not selection:
            messagebox.showwarning("Chua chon anh", "Hay chon mot anh trong thu vien")
            return None
        return self.asset_list.get(selection[0])

    def add_wait_image(self):
        asset = self.selected_asset()
        if asset:
            self.recorder.function.steps.append(Step("wait_image", {"asset": asset, "confidence": 0.85, "timeout": 10}))
            self.refresh_steps()

    def add_click_image(self):
        asset = self.selected_asset()
        if asset:
            self.recorder.function.steps.append(Step("click_image", {"asset": asset, "confidence": 0.85, "timeout": 10}))
            self.refresh_steps()

    def add_wait(self):
        seconds = simpledialog.askfloat("Thoi gian cho", "So giay:", initialvalue=1.0, minvalue=0, maxvalue=3600)
        if seconds is not None:
            self.recorder.add_wait(seconds)
            self.refresh_steps()

    def refresh_steps(self):
        self.step_tree.delete(*self.step_tree.get_children())
        for index, step in enumerate(self.recorder.function.steps):
            detail = json.dumps(step.data, ensure_ascii=False, separators=(",", ":"))
            self.step_tree.insert("", "end", iid=str(index), values=(index + 1, step.type, detail))

    def selected_step(self):
        selection = self.step_tree.selection()
        return int(selection[0]) if selection else None

    def delete_step(self):
        index = self.selected_step()
        if index is not None:
            del self.recorder.function.steps[index]
            self.refresh_steps()

    def move_step(self, delta):
        index = self.selected_step()
        if index is None:
            return
        destination = index + delta
        if 0 <= destination < len(self.recorder.function.steps):
            steps = self.recorder.function.steps
            steps[index], steps[destination] = steps[destination], steps[index]
            self.refresh_steps()
            self.step_tree.selection_set(str(destination))

    def save_function(self):
        self.recorder.function.name = self.name_var.get().strip() or "Chuc nang moi"
        default = self.functions / (self.recorder.function.name.replace(" ", "_") + ".json")
        path = filedialog.asksaveasfilename(initialdir=self.functions, initialfile=default.name, defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            self.recorder.function.save(Path(path))
            self.status_var.set(f"Da luu {Path(path).name}")

    def load_function(self):
        path = filedialog.askopenfilename(initialdir=self.functions, filetypes=[("JSON", "*.json")])
        if path:
            self.recorder.function = AutoFunction.load(Path(path))
            self.name_var.set(self.recorder.function.name)
            self.refresh_steps()

    def run_function(self):
        self.recorder.function.name = self.name_var.get().strip() or "Chuc nang moi"
        def worker():
            try:
                events = FunctionRuntime(self.engine, self.assets).run(self.recorder.function)
                self.after(0, self.status_var.set, f"PASS {len(events)} buoc")
                self.after(0, self.capture_preview)
            except Exception as exc:
                self.after(0, messagebox.showerror, "Chay thu loi", str(exc))
        threading.Thread(target=worker, daemon=True).start()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pid", type=int)
    parser.add_argument("--workspace", default="function-builder-workspace")
    args = parser.parse_args()
    app = FunctionBuilderApp(args.pid, Path(args.workspace))
    app.mainloop()


if __name__ == "__main__":
    main()
