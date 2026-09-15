from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import threading


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

    @staticmethod
    def _safe(message: str) -> str:
        return _SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=<redacted>", str(message))

    @staticmethod
    def _line(message: str) -> str:
        stamp = datetime.now().strftime("%H:%M:%S")
        return f"[{stamp}] {message.rstrip()}\n"

    def _write(self, path: Path, message: str) -> None:
        line = self._line(self._safe(message))
        with self._lock:
            with path.open("a", encoding="utf-8", newline="") as stream:
                stream.write(line)
                stream.flush()

    def action(self, message: str) -> None:
        """Write only explicit per-account milestones; demote legacy noise."""
        text = str(message).strip()
        if text.startswith(_ACTION_PREFIX):
            self._write(self.action_path, text)
            return
        self._write(self.detail_path, text)

    def detail(self, message: str) -> None:
        self._write(self.detail_path, message)
