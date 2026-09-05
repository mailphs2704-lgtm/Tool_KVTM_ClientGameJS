from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import threading
import time
from typing import Callable

from .errors import AutomationStopped


LogFn = Callable[[str], None]
StageFn = Callable[[str], None]


@dataclass
class AutomationContext:
    """Runtime state shared by reusable KVTM automation actions.

    No AUTO PRO object is stored here. The context owns only the selected
    ClientJS process/profile, paths, cancellation signal and reporting hooks.
    """

    pid: int
    profile_id: str
    profile_name: str
    auto_root: Path
    work_dir: Path
    stop_event: threading.Event
    logger: LogFn
    stage_reporter: StageFn | None = None
    profile_file: Path | None = None
    started_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        self.pid = int(self.pid)
        self.profile_id = str(self.profile_id)
        self.profile_name = str(self.profile_name)
        self.auto_root = Path(self.auto_root).resolve()
        self.work_dir = Path(self.work_dir).resolve()
        if self.profile_file is not None:
            self.profile_file = Path(self.profile_file).resolve()
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def log(self, message: str) -> None:
        self.logger(str(message))

    def stage(self, name: str) -> None:
        if self.stage_reporter is not None:
            self.stage_reporter(str(name))
        self.log(str(name))

    def ensure_running(self) -> None:
        if self.stop_event.is_set():
            raise AutomationStopped("Dọn quầy đã được yêu cầu dừng")
