from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import threading
import time
from typing import Any


VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_FPS = 60.0
VIDEO_CODEC = "mp4v"
VIDEO_EXTENSION = ".mp4"
MAX_CAPTURE_FAILURES = 30
MAX_CATCHUP_FRAMES = 8


@dataclass
class ClientVideoSession:
    profile_id: str
    pid: int
    hwnd: int
    output_path: Path
    stop_event: threading.Event
    thread: threading.Thread | None = None
    frames_written: int = 0
    capture_failures: int = 0


def _safe_name(value: str) -> str:
    text = re.sub(r"[^0-9A-Za-z._-]+", "_", str(value).strip())
    return text.strip("._-") or "client"


def _find_widget_by_text(root: Any, needle: str):
    for child in root.winfo_children():
        try:
            text = str(child.cget("text"))
        except Exception:
            text = ""
        if needle in text:
            return child
        found = _find_widget_by_text(child, needle)
        if found is not None:
            return found
    return None


def _letterbox_full_hd(frame_bgra, cv2, np):
    """Scale native ClientJS into a 1920x1080 canvas without stretching."""
    if frame_bgra.ndim != 3 or frame_bgra.shape[2] < 3:
        raise RuntimeError(f"Frame ClientJS không hợp lệ: shape={frame_bgra.shape!r}")
    source = frame_bgra[:, :, :3]
    src_h, src_w = source.shape[:2]
    if src_w <= 0 or src_h <= 0:
        raise RuntimeError("Frame ClientJS có kích thước rỗng")

    scale = min(VIDEO_WIDTH / float(src_w), VIDEO_HEIGHT / float(src_h))
    out_w = max(1, int(round(src_w * scale)))
    out_h = max(1, int(round(src_h * scale)))
    interpolation = cv2.INTER_CUBIC if scale >= 1.0 else cv2.INTER_AREA
    resized = cv2.resize(source, (out_w, out_h), interpolation=interpolation)
    canvas = np.zeros((VIDEO_HEIGHT, VIDEO_WIDTH, 3), dtype=np.uint8)
    left = (VIDEO_WIDTH - out_w) // 2
    top = (VIDEO_HEIGHT - out_h) // 2
    canvas[top : top + out_h, left : left + out_w] = resized
    return canvas


def install_client_video_recorder(app_cls, core) -> None:
    """Install one-click ClientJS MP4 recording into the Multi DEV GUI.

    Recorder capture uses the existing Windows client-area capture helper and is
    independent from the isolated AUTO worker/CAPTURE3 owner.
    """
    if getattr(app_cls, "_client_video_recorder_installed", False):
        return

    original_build_ui = app_cls._build_ui
    original_on_close = app_cls._on_close

    def _video_log(self, message: str) -> None:
        print(f"[KVTM DEV] {message}", flush=True)
        try:
            status = getattr(self, "status_var", None)
            if status is not None:
                status.set(str(message))
        except Exception:
            pass

    def _set_video_button(self, text: str, *, enabled: bool = True) -> None:
        button = getattr(self, "_client_video_button", None)
        if button is None:
            return
        try:
            button.configure(text=text, state=("normal" if enabled else "disabled"))
            button.update_idletasks()
        except Exception:
            pass

    def _reject_start(self, message: str) -> None:
        _video_log(self, f"VIDEO ClientJS • KHÔNG THỂ START • {message}")
        _set_video_button(self, "⏺ Quay MP4", enabled=True)

    def _finish_video_ui(self, session: ClientVideoSession, error: str | None) -> None:
        current = getattr(self, "_client_video_session", None)
        if current is session:
            self._client_video_session = None
        _set_video_button(self, "⏺ Quay MP4", enabled=True)
        if error:
            _video_log(self, f"VIDEO ClientJS • ERROR • {error}")
            try:
                core.messagebox.showerror(core.APP_NAME, error)
            except Exception:
                pass
            return
        _video_log(
            self,
            "VIDEO ClientJS • STOP • "
            f"profile={session.profile_id} • frames={session.frames_written} • "
            f"MP4={session.output_path}",
        )

    def _record_worker(self, session: ClientVideoSession) -> None:
        writer = None
        error: str | None = None
        try:
            import cv2
            import numpy as np

            session.output_path.parent.mkdir(parents=True, exist_ok=True)
            fourcc = cv2.VideoWriter_fourcc(*VIDEO_CODEC)
            writer = cv2.VideoWriter(
                str(session.output_path),
                fourcc,
                VIDEO_FPS,
                (VIDEO_WIDTH, VIDEO_HEIGHT),
            )
            if not writer.isOpened():
                raise RuntimeError(
                    "Không mở được MP4 encoder mp4v của OpenCV; runtime video chưa sẵn sàng"
                )

            _video_log(
                self,
                "VIDEO ClientJS • START • "
                f"profile={session.profile_id} • pid={session.pid} • hwnd={session.hwnd} • "
                f"1920x1080 @ 60fps • MP4/mp4v • {session.output_path}",
            )
            started = time.perf_counter()
            next_tick = started
            last_canvas = None

            while not session.stop_event.is_set():
                proc = self.processes.get(session.profile_id)
                if proc is None or proc.poll() is not None:
                    raise RuntimeError(
                        f"ClientJS {session.profile_id} đã dừng trong lúc quay"
                    )

                capture = None
                capture_error = None
                try:
                    capture = core.capture_bgra(session.hwnd)
                except Exception as exc:
                    capture_error = exc

                if capture is None:
                    session.capture_failures += 1
                    if session.capture_failures == 1:
                        _video_log(
                            self,
                            "VIDEO ClientJS • capture MISS 1/"
                            f"{MAX_CAPTURE_FAILURES} • "
                            f"{type(capture_error).__name__ if capture_error else 'UNKNOWN'}: "
                            f"{capture_error if capture_error else 'no frame'}",
                        )
                    if session.capture_failures >= MAX_CAPTURE_FAILURES:
                        raise RuntimeError(
                            "Mất frame ClientJS liên tục; MP4 đã được đóng an toàn"
                        )
                    if last_canvas is not None:
                        writer.write(last_canvas)
                        session.frames_written += 1
                    session.stop_event.wait(1.0 / VIDEO_FPS)
                    continue

                session.capture_failures = 0
                # pc_driver.capture_bgra() contract is exactly (raw, width, height).
                # The first recorder version unpacked this backwards as
                # (width, height, raw), causing the worker to fail immediately
                # after the button was pressed and making the GUI look inert.
                raw, width, height = capture
                width = int(width)
                height = int(height)
                expected_bytes = width * height * 4
                if width <= 0 or height <= 0 or len(raw) < expected_bytes:
                    raise RuntimeError(
                        f"Frame BGRA lỗi: {width}x{height}, bytes={len(raw)}"
                    )
                frame = np.frombuffer(raw, dtype=np.uint8, count=expected_bytes)
                frame = frame.reshape((height, width, 4))
                canvas = _letterbox_full_hd(frame, cv2, np)
                last_canvas = canvas

                now = time.perf_counter()
                expected_total = max(
                    session.frames_written + 1,
                    int((now - started) * VIDEO_FPS) + 1,
                )
                missing = max(1, expected_total - session.frames_written)
                write_count = min(missing, MAX_CATCHUP_FRAMES)
                for _ in range(write_count):
                    writer.write(canvas)
                session.frames_written += write_count

                if missing > MAX_CATCHUP_FRAMES:
                    started = time.perf_counter() - (
                        session.frames_written / VIDEO_FPS
                    )

                next_tick += 1.0 / VIDEO_FPS
                delay = next_tick - time.perf_counter()
                if delay > 0:
                    session.stop_event.wait(delay)
                elif delay < -0.50:
                    next_tick = time.perf_counter()
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        finally:
            if writer is not None:
                try:
                    writer.release()
                except Exception:
                    pass
            if session.frames_written <= 0:
                try:
                    session.output_path.unlink(missing_ok=True)
                except Exception:
                    pass
            try:
                self.after(0, lambda: _finish_video_ui(self, session, error))
            except Exception:
                pass

    def _start_client_video(self) -> None:
        selected = list(map(str, self.selected_ids()))
        _video_log(
            self,
            f"VIDEO ClientJS • BUTTON • start requested • selected={selected}",
        )
        if len(selected) != 1:
            _reject_start(self, "Hãy chọn đúng 1 tài khoản ClientJS đang chạy.")
            return

        profile_id = selected[0]
        proc = self.processes.get(profile_id)
        if proc is None or proc.poll() is not None:
            _reject_start(self, f"ClientJS profile={profile_id} chưa chạy hoặc đã thoát.")
            return

        hwnd = core.find_window(proc.pid)
        if not hwnd:
            _reject_start(
                self,
                f"Không tìm thấy cửa sổ ClientJS profile={profile_id} pid={proc.pid}.",
            )
            return

        videos_dir = Path(core.APP_DIR) / "videos"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = videos_dir / (
            f"ClientJS_{_safe_name(profile_id)}_{stamp}_1080p60{VIDEO_EXTENSION}"
        )
        session = ClientVideoSession(
            profile_id=profile_id,
            pid=int(proc.pid),
            hwnd=int(hwnd),
            output_path=output,
            stop_event=threading.Event(),
        )
        thread = threading.Thread(
            target=_record_worker,
            args=(self, session),
            name=f"kvtm-client-video-{profile_id}",
            daemon=True,
        )
        session.thread = thread
        self._client_video_session = session
        _set_video_button(self, "■ Dừng MP4", enabled=True)
        _video_log(
            self,
            f"VIDEO ClientJS • THREAD STARTING • profile={profile_id} • pid={proc.pid} • hwnd={hwnd}",
        )
        thread.start()

    def _toggle_client_video(self) -> None:
        session = getattr(self, "_client_video_session", None)
        if session is None:
            _start_client_video(self)
            return
        if session.stop_event.is_set():
            _video_log(self, "VIDEO ClientJS • BUTTON • stop đã được yêu cầu trước đó")
            return
        session.stop_event.set()
        _set_video_button(self, "■ Đang dừng...", enabled=False)
        _video_log(self, "VIDEO ClientJS • STOP requested • đang finalize MP4")

    def wrapped_build_ui(self) -> None:
        original_build_ui(self)
        self._client_video_session = None
        screenshot_button = _find_widget_by_text(self, "Chụp ảnh")
        if screenshot_button is None:
            raise RuntimeError("Không tìm thấy nút Chụp ảnh để gắn Quay MP4")
        master = screenshot_button.master
        info = screenshot_button.grid_info()
        row = int(info.get("row", 0))
        column = int(info.get("column", 0)) + 1
        self._client_video_button = core.ttk.Button(
            master,
            text="⏺ Quay MP4",
            command=lambda: _toggle_client_video(self),
        )
        self._client_video_button.grid(
            row=row,
            column=column,
            sticky="ew",
            padx=3,
            pady=3,
        )
        try:
            master.columnconfigure(column, weight=1)
        except Exception:
            pass
        _video_log(
            self,
            "VIDEO GUI READY • nút Quay MP4 cạnh Chụp ảnh • output=1920x1080@60fps",
        )

    def wrapped_on_close(self) -> None:
        session = getattr(self, "_client_video_session", None)
        if session is not None:
            session.stop_event.set()
            thread = session.thread
            if thread is not None and thread.is_alive():
                thread.join(timeout=5.0)
        original_on_close(self)

    app_cls._build_ui = wrapped_build_ui
    app_cls._on_close = wrapped_on_close
    app_cls._client_video_recorder_installed = True
