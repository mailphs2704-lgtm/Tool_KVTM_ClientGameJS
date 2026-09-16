from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import threading
import time


class RuntimeLogStore:
    """Small persistent per-account log used by the standalone Dọn quầy UI.

    The log deliberately receives lifecycle/progress text only.  Login secrets
    and launch arguments are never passed to this class by the controller.
    """

    MAX_BYTES = 4 * 1024 * 1024
    READ_MAX_BYTES = 512 * 1024

    def __init__(self, app_dir: Path) -> None:
        self.log_dir = Path(app_dir) / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    @staticmethod
    def _file_key(profile_id: str) -> str:
        raw = str(profile_id or "unknown")
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._-") or "profile"
        digest = hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:8]
        return f"{safe[:48]}-{digest}"

    def path(self, profile_id: str) -> Path:
        return self.log_dir / f"{self._file_key(profile_id)}.log"

    def _rotate_if_needed(self, path: Path) -> None:
        try:
            if not path.is_file() or path.stat().st_size < self.MAX_BYTES:
                return
            rotated = path.with_suffix(".1.log")
            try:
                rotated.unlink()
            except FileNotFoundError:
                pass
            path.replace(rotated)
        except OSError:
            pass

    def append(self, profile_id: str, event: str, message: str = "", **data) -> None:
        path = self.path(profile_id)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        clean_event = str(event or "event").strip() or "event"
        clean_message = str(message or "").replace("\r", " ").replace("\n", " ").strip()
        extras = {key: value for key, value in data.items() if value is not None}
        parts = [stamp, clean_event]
        if clean_message:
            parts.append(clean_message)
        if extras:
            try:
                parts.append(json.dumps(extras, ensure_ascii=False, sort_keys=True, default=str))
            except Exception:
                parts.append(str(extras))
        line = " | ".join(parts) + "\n"
        with self._lock:
            self._rotate_if_needed(path)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8", newline="") as handle:
                    handle.write(line)
            except OSError:
                pass

    def read_tail(self, profile_id: str, max_lines: int = 800) -> str:
        path = self.path(profile_id)
        if not path.is_file():
            return "Chưa có log cho tài khoản này.\n"
        with self._lock:
            try:
                size = path.stat().st_size
                with path.open("rb") as handle:
                    if size > self.READ_MAX_BYTES:
                        handle.seek(-self.READ_MAX_BYTES, 2)
                    raw = handle.read()
            except OSError as exc:
                return f"Không đọc được log: {exc}\n"
        text = raw.decode("utf-8", errors="replace")
        lines = text.splitlines()
        if max_lines > 0 and len(lines) > max_lines:
            lines = lines[-max_lines:]
            lines.insert(0, "… log trước đó đã được thu gọn …")
        return "\n".join(lines) + ("\n" if lines else "")
