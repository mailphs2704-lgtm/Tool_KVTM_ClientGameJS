from __future__ import annotations

import ctypes
from ctypes import wintypes
import queue
import threading
import time


__all__ = ["pick_swipe_on_game"]
FILE_FUNCTIONS = (
    "Chọn đúng một ClientJS đang chạy từ selection của Multi DEV",
    "Cấu hình Win32 GDI pointer-safe cho Python x64",
    "Hiển thị fresh OpenGL shared capture không dùng HWND fallback",
    "Ánh xạ kéo chuột trên preview về tọa độ logic 0..1000",
    "Cho kéo nhiều đoạn liên tiếp và vẽ toàn bộ polyline Swipe",
    "Undo đoạn cuối / xóa toàn bộ đường trước khi xác nhận",
    "Chặn picker khi profile đang có AUTO/preview chiếm capture",
)


def _selected_running_profile(app, core):
    selected = list(map(str, app.selected_ids()))
    if len(selected) != 1:
        raise RuntimeError("Hãy chọn đúng 1 tài khoản đang chạy để kéo trực tiếp trên màn hình game")
    profile_id = selected[0]
    try:
        app._adopt_running_clients(core.running_clients())
    except Exception:
        pass
    process = app.processes.get(profile_id)
    if process is None or process.poll() is not None:
        raise RuntimeError("Tài khoản đã chọn chưa Online; hãy mở ClientJS trước khi chọn Swipe")
    if getattr(app, "_clean_main_alive", lambda _pid: False)(profile_id):
        raise RuntimeError("Tài khoản đang chạy AUTO MULTI DEV; hãy dừng AUTO trước khi lấy Swipe")
    preview = getattr(app, "previews", {}).get(profile_id)
    if preview is not None:
        raise RuntimeError("Hãy đóng Live View của tài khoản này trước khi lấy Swipe")
    profile = next(
        (item for item in app.profiles if str(item.get("id") or "") == profile_id),
        None,
    )
    return profile_id, profile or {}, int(process.pid)


def _configure_gdi(core) -> None:
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
        wintypes.LPVOID, ctypes.POINTER(core.BITMAPINFO),
        wintypes.UINT, wintypes.DWORD,
    ]
    gdi32.StretchDIBits.restype = ctypes.c_int
    gdi32.CreatePen.argtypes = [ctypes.c_int, ctypes.c_int, wintypes.DWORD]
    gdi32.CreatePen.restype = wintypes.HANDLE
    gdi32.SelectObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    gdi32.SelectObject.restype = wintypes.HANDLE
    gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
    gdi32.DeleteObject.restype = wintypes.BOOL
    gdi32.MoveToEx.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
    ]
    gdi32.MoveToEx.restype = wintypes.BOOL
    gdi32.LineTo.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_int]
    gdi32.LineTo.restype = wintypes.BOOL
    gdi32.Ellipse.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ]
    gdi32.Ellipse.restype = wintypes.BOOL


def _normalize_initial(initial) -> list[tuple[int, int]]:
    if not initial:
        return []
    if isinstance(initial, (list, tuple)) and len(initial) >= 2:
        if all(isinstance(item, (list, tuple)) and len(item) == 2 for item in initial):
            points = [(int(item[0]), int(item[1])) for item in initial]
            return [
                (max(0, min(1000, x)), max(0, min(1000, y)))
                for x, y in points
            ]
        if len(initial) == 4:
            return [
                (int(initial[0]), int(initial[1])),
                (int(initial[2]), int(initial[3])),
            ]
    return []


class _SwipePickerWindow:
    def __init__(self, app, core, parent, profile_id: str, profile: dict, pid: int, initial):
        self.app = app
        self.core = core
        self.profile_id = profile_id
        self.pid = int(pid)
        self.result = None
        self._stop = threading.Event()
        self._frames: queue.Queue = queue.Queue(maxsize=1)
        self._latest = None
        self._dib_pixels = None
        self._dib_size = 0
        self._target_rect = (0, 0, 1, 1)
        self._points: list[tuple[int, int]] = _normalize_initial(initial)
        self._drag_start: tuple[int, int] | None = None
        self._drag_current: tuple[int, int] | None = None
        _configure_gdi(core)

        tk, ttk = core.tk, core.ttk
        win = tk.Toplevel(parent or app)
        self.window = win
        name = str(profile.get("name") or profile_id)
        win.title(f"KVTM Multi DEV - Chọn Swipe nhiều đoạn - {name}")
        win.geometry("700x760")
        win.minsize(500, 560)
        win.configure(background="#f3f6fa")
        win.transient(parent or app)

        header = ttk.Frame(win, padding=(12, 10), style="App.TFrame")
        header.pack(fill="x")
        ttk.Label(
            header,
            text="Kéo nhiều lần trên hình game; mỗi lần kéo sẽ thêm một đoạn vào cùng một Swipe",
            style="Key.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            header,
            text="Đường mới được nối theo đúng thứ tự điểm. Có thể Undo đoạn cuối hoặc Xóa đường.",
            style="AutoValue.TLabel",
        ).pack(anchor="w", pady=(4, 0))
        self.status = tk.StringVar(value="Đang lấy OpenGL shared capture...")
        ttk.Label(header, textvariable=self.status, style="AutoValue.TLabel").pack(
            anchor="w", pady=(5, 0)
        )

        self.canvas = tk.Canvas(
            win, background="black", borderwidth=0, highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Configure>", lambda _event: self._paint_latest())

        actions = ttk.Frame(win, padding=(12, 0, 12, 12), style="App.TFrame")
        actions.pack(fill="x")
        left_actions = ttk.Frame(actions, style="App.TFrame")
        left_actions.pack(side="left")
        ttk.Button(
            left_actions, text="↶ Undo đoạn cuối", width=17, style="Action.TButton",
            command=self._undo_segment,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            left_actions, text="✕ Xóa đường", width=14, style="Action.TButton",
            command=self._clear_path,
        ).pack(side="left")

        self.selection_text = tk.StringVar(value="Chưa chọn đường Swipe")
        ttk.Label(actions, textvariable=self.selection_text, style="AutoValue.TLabel").pack(
            side="left", fill="x", expand=True, padx=(12, 8)
        )
        ttk.Button(
            actions, text="Dùng Swipe này", width=18, style="AutoStart.TButton",
            command=self._accept,
        ).pack(side="right", padx=(8, 0))
        ttk.Button(
            actions, text="Hủy", width=10, style="Action.TButton",
            command=self._cancel,
        ).pack(side="right")

        self._update_selection_text()
        win.protocol("WM_DELETE_WINDOW", self._cancel)
        threading.Thread(target=self._capture_loop, daemon=True).start()
        win.after(25, self._poll_frame)

    def _capture_loop(self) -> None:
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                # Deliberately no HWND fallback. This visual picker reads only
                # the existing OpenGL shared surface while no AUTO worker owns it.
                raw, width, height = self.core.capture_shared_bgra(
                    self.pid, timeout_ms=2000
                )
                item = (raw, int(width), int(height))
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
            except Exception as exc:
                message = str(exc)
                try:
                    self.window.after(
                        0, lambda text=message: self.status.set(
                            "Chưa lấy được OpenGL capture: " + text[:120]
                        )
                    )
                except Exception:
                    pass
            elapsed = time.monotonic() - started
            self._stop.wait(max(0.0, 0.08 - elapsed))

    def _poll_frame(self) -> None:
        if self._stop.is_set() or not self.window.winfo_exists():
            return
        newest = None
        try:
            while True:
                newest = self._frames.get_nowait()
        except queue.Empty:
            pass
        if newest is not None:
            raw, width, height = newest
            size = len(raw)
            if self._dib_pixels is None or self._dib_size != size:
                self._dib_pixels = ctypes.create_string_buffer(size)
                self._dib_size = size
            ctypes.memmove(self._dib_pixels, raw, size)
            self._latest = (self._dib_pixels, width, height)
            self.status.set(
                f"OpenGL shared capture • {width}×{height} • "
                f"{max(0, len(self._points) - 1)} đoạn đã giữ"
            )
            self._paint_latest()
        self.window.after(25, self._poll_frame)

    def _paint_latest(self) -> None:
        if self._latest is None or not self.canvas.winfo_exists():
            return
        pixels, width, height = self._latest
        canvas_w = max(1, self.canvas.winfo_width())
        canvas_h = max(1, self.canvas.winfo_height())
        side = max(1, min(canvas_w, canvas_h))
        left = (canvas_w - side) // 2
        top = (canvas_h - side) // 2
        self._target_rect = (left, top, side, side)

        info = self.core.BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(info.bmiHeader)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = 0
        hwnd = self.canvas.winfo_id()
        dc = ctypes.windll.user32.GetDC(hwnd)
        if not dc:
            return
        try:
            ctypes.windll.gdi32.SetStretchBltMode(dc, 4)
            ctypes.windll.gdi32.StretchDIBits(
                dc, left, top, side, side,
                0, 0, width, height,
                pixels, ctypes.byref(info), 0, 0x00CC0020,
            )
            self._paint_overlay(dc)
        finally:
            ctypes.windll.user32.ReleaseDC(hwnd, dc)

    def _logical_to_canvas(self, point):
        left, top, width, height = self._target_rect
        x, y = point
        return (
            int(left + (max(0, min(1000, x)) / 1000.0) * width),
            int(top + (max(0, min(1000, y)) / 1000.0) * height),
        )

    def _canvas_to_logical(self, x: int, y: int):
        left, top, width, height = self._target_rect
        if x < left or y < top or x > left + width or y > top + height:
            return None
        lx = int(round((x - left) * 1000.0 / max(1, width)))
        ly = int(round((y - top) * 1000.0 / max(1, height)))
        return max(0, min(1000, lx)), max(0, min(1000, ly))

    def _overlay_points(self) -> list[tuple[int, int]]:
        points = list(self._points)
        if self._drag_start is not None and self._drag_current is not None:
            if not points or points[-1] != self._drag_start:
                points.append(self._drag_start)
            if not points or points[-1] != self._drag_current:
                points.append(self._drag_current)
        return points

    def _paint_overlay(self, dc) -> None:
        points = self._overlay_points()
        if not points:
            return
        canvas_points = [self._logical_to_canvas(point) for point in points]
        gdi32 = ctypes.windll.gdi32
        pen = gdi32.CreatePen(0, 4, 0x0000FFFF)
        old_pen = gdi32.SelectObject(dc, pen)
        try:
            if len(canvas_points) >= 2:
                sx, sy = canvas_points[0]
                gdi32.MoveToEx(dc, sx, sy, None)
                for ex, ey in canvas_points[1:]:
                    gdi32.LineTo(dc, ex, ey)
            for index, (x, y) in enumerate(canvas_points):
                radius = 8 if index in (0, len(canvas_points) - 1) else 5
                gdi32.Ellipse(dc, x - radius, y - radius, x + radius, y + radius)
        finally:
            gdi32.SelectObject(dc, old_pen)
            gdi32.DeleteObject(pen)

    def _on_press(self, event) -> None:
        point = self._canvas_to_logical(event.x, event.y)
        if point is None:
            return
        self._drag_start = point
        self._drag_current = point
        self._update_selection_text()
        self._paint_latest()

    def _on_drag(self, event) -> None:
        if self._drag_start is None:
            return
        point = self._canvas_to_logical(event.x, event.y)
        if point is None:
            return
        self._drag_current = point
        self._update_selection_text()
        self._paint_latest()

    def _on_release(self, event) -> None:
        if self._drag_start is None:
            return
        point = self._canvas_to_logical(event.x, event.y)
        if point is not None:
            self._drag_current = point
        start, end = self._drag_start, self._drag_current
        if end is not None and start != end:
            if not self._points:
                self._points.append(start)
            elif self._points[-1] != start:
                self._points.append(start)
            if self._points[-1] != end:
                self._points.append(end)
        self._drag_start = None
        self._drag_current = None
        self._update_selection_text()
        self._paint_latest()

    def _undo_segment(self) -> None:
        if len(self._points) <= 2:
            self._points.clear()
        else:
            self._points.pop()
        self._drag_start = None
        self._drag_current = None
        self._update_selection_text()
        self._paint_latest()

    def _clear_path(self) -> None:
        self._points.clear()
        self._drag_start = None
        self._drag_current = None
        self._update_selection_text()
        self._paint_latest()

    def _update_selection_text(self) -> None:
        points = self._overlay_points()
        if len(points) < 2:
            self.selection_text.set("Chưa có đoạn Swipe • kéo trên hình để thêm đoạn")
            return
        self.selection_text.set(
            f"{len(points)} điểm / {len(points) - 1} đoạn • "
            f"{points[0][0]},{points[0][1]} → {points[-1][0]},{points[-1][1]}"
        )

    def _accept(self) -> None:
        if len(self._points) < 2:
            self.core.messagebox.showinfo(
                self.core.APP_NAME, "Hãy tạo ít nhất một đoạn Swipe trên màn hình game.",
                parent=self.window,
            )
            return
        self.result = [[int(x), int(y)] for x, y in self._points]
        self._close()

    def _cancel(self) -> None:
        self.result = None
        self._close()

    def _close(self) -> None:
        self._stop.set()
        if self.window.winfo_exists():
            self.window.destroy()


def pick_swipe_on_game(app, core, parent=None, initial=None):
    """Return ordered logical ``[[x,y], ...]`` polyline from live game drags."""
    profile_id, profile, pid = _selected_running_profile(app, core)
    picker = _SwipePickerWindow(
        app, core, parent, profile_id, profile, pid, initial,
    )
    picker.window.grab_set()
    picker.window.wait_window()
    return picker.result
