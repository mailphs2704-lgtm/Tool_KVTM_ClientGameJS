from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import threading
import time


__all__ = ["MainLogWriter"]
FILE_FUNCTIONS = (
    "Tạo hai file log riêng cho một lượt AUTO Main",
    "Chỉ giữ milestone dạng '. tài khoản . hành động' trong Log hành động",
    "Tự chuyển mọi chatter cũ/kỹ thuật sang Log chi tiết",
    "Che dữ liệu nhạy cảm trước khi ghi ra đĩa",
)

_SECRET_PATTERN = re.compile(
    r"(?i)(password|token|cookie|authorization|secret|launch_args)\s*[:=]\s*([^\s,;]+)"
)
_ACTION_PREFIX = ". "


class MainLogWriter:
    """Thread-safe concise action + full detail logs for one profile/run."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = Path(run_dir).resolve()
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.action_path = self.run_dir / "action.log"
        self.detail_path = self.run_dir / "detail.log"
        self._lock = threading.Lock()
        self._streams = {}
        self._last_detail_flush = 0.0
        self._detail_flush_timer = None

    @staticmethod
    def _safe(message: str) -> str:
        return _SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=<redacted>", str(message))

    @staticmethod
    def _line(message: str) -> str:
        stamp = datetime.now().strftime("%H:%M:%S")
        return f"[{stamp}] {message.rstrip()}\n"

    def _stream(self, path: Path):
        stream = self._streams.get(path)
        if stream is None or stream.closed:
            stream = path.open("a", encoding="utf-8", newline="")
            self._streams[path] = stream
        return stream

    def _write(self, path: Path, message: str, *, flush: bool) -> None:
        line = self._line(self._safe(message))
        with self._lock:
            stream = self._stream(path)
            stream.write(line)
            now = time.monotonic()
            if flush or now - self._last_detail_flush >= 0.75:
                stream.flush()
                if path == self.detail_path:
                    self._last_detail_flush = now
            elif path == self.detail_path and self._detail_flush_timer is None:
                timer = threading.Timer(0.75, self._flush_detail)
                timer.daemon = True
                self._detail_flush_timer = timer
                timer.start()

    def _flush_detail(self) -> None:
        with self._lock:
            self._detail_flush_timer = None
            stream = self._streams.get(self.detail_path)
            if stream is not None and not stream.closed:
                stream.flush()
                self._last_detail_flush = time.monotonic()

    def action(self, message: str) -> None:
        """Write only explicit per-account milestones; demote legacy noise."""
        text = str(message).strip()
        if text.startswith(_ACTION_PREFIX):
            # Operator milestones are infrequent and should be durable immediately.
            self._write(self.action_path, text, flush=True)
            return
        self._write(self.detail_path, text, flush=False)

    def detail(self, message: str) -> None:
        # Technical chatter is buffered briefly instead of open+flush per line.
        self._write(self.detail_path, message, flush=False)

    def close(self) -> None:
        with self._lock:
            if self._detail_flush_timer is not None:
                self._detail_flush_timer.cancel()
                self._detail_flush_timer = None
            for stream in self._streams.values():
                try:
                    stream.flush()
                    stream.close()
                except OSError:
                    pass
            self._streams.clear()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
