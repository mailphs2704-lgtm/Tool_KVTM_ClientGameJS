from __future__ import annotations

import json
from pathlib import Path
import queue
import sys
import threading
from typing import Callable


def configure_utf8_stdio() -> None:
    """Force JSON-line workers to survive Vietnamese text on Windows consoles."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, ValueError, OSError):
            pass


def install_component_path() -> Path:
    """Expose `components/clientjs-auto` without importing legacy auto_worker."""
    component_root = Path(__file__).resolve().parents[1]
    text = str(component_root)
    if text not in sys.path:
        sys.path.insert(0, text)
    return component_root


def emit(event: str, **data) -> None:
    print(
        json.dumps({"event": str(event), **data}, ensure_ascii=True),
        flush=True,
    )


class StopChannel:
    """Read stop/pause commands concurrently while the clean workflow runs."""

    def __init__(
        self,
        *,
        on_stop: Callable[[dict], None] | None = None,
    ) -> None:
        self.event = threading.Event()
        self.commands: queue.Queue[dict] = queue.Queue()
        self.on_stop = on_stop
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._reader,
            name="kvtm-clean-worker-command-reader",
            daemon=True,
        )
        self._thread.start()

    def _reader(self) -> None:
        for line in sys.stdin:
            try:
                payload = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(payload, dict):
                continue
            self.commands.put(payload)
            action = str(payload.get("command") or "").strip().lower()
            if action not in {"stop", "pause"}:
                continue
            self.event.set()
            if self.on_stop is not None:
                try:
                    self.on_stop(payload)
                except Exception:
                    pass
            return
