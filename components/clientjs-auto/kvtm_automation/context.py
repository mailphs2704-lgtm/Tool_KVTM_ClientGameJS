from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import threading
import time
from typing import Callable

from .errors import AutomationStopped


LogFn = Callable[[str], None]
StageFn = Callable[[str], None]

__all__ = ["AutomationContext", "LogFn", "StageFn"]
FILE_FUNCTIONS = (
    "Giữ identity và đường dẫn của một tác vụ AUTO",
    "Ghi log hành động",
    "Ghi log kỹ thuật chi tiết",
    "Báo stage nghiệp vụ",
    "Giữ bằng chứng camera exact-main theo runtime, không theo background tài khoản",
    "Dừng tác vụ theo stop-event",
)


@dataclass
class AutomationContext:
    """Runtime state shared by reusable KVTM automation actions.

    No AUTO PRO object is stored here. The context owns only the selected
    ClientJS process/profile, paths, cancellation signal and reporting hooks.

    ``camera_exact_main_proven`` is deliberately runtime evidence instead of an
    image/template classification. KVTM accounts may use different farm
    backgrounds, so a world-space object such as the stall must never be the
    exact-main gate. Navigation owns this proof and invalidates it whenever the
    vertical camera is moved.
    """

    pid: int
    profile_id: str
    profile_name: str
    auto_root: Path
    work_dir: Path
    stop_event: threading.Event
    logger: LogFn
    stage_reporter: StageFn | None = None
    detail_logger: LogFn | None = None
    profile_file: Path | None = None
    started_at: float = field(default_factory=time.time)
    camera_exact_main_proven: bool = field(default=False, init=False, repr=False)
    camera_main_boundary_streak: int = field(default=0, init=False, repr=False)

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

    def detail(self, message: str) -> None:
        if self.detail_logger is not None:
            self.detail_logger(str(message))

    def stage(self, name: str) -> None:
        if self.stage_reporter is not None:
            self.stage_reporter(str(name))
        self.log(str(name))

    def invalidate_camera_main(self, reason: str = "") -> None:
        """Forget exact-main proof before/after any camera state uncertainty."""
        self.camera_exact_main_proven = False
        self.camera_main_boundary_streak = 0
        if reason:
            self.detail(f"AUTO camera proof | exact_main=false | reason={reason}")

    def mark_camera_exact_main(self, reason: str) -> None:
        """Record exact-main only after a deterministic route/boundary proof."""
        self.camera_exact_main_proven = True
        self.camera_main_boundary_streak = 0
        self.detail(
            f"AUTO camera proof | exact_main=true | source=runtime-route | reason={reason}"
        )

    def observe_camera_down_boundary(
        self,
        change: float,
        *,
        max_change: float,
        stable_required: int,
        reason: str,
    ) -> bool:
        """Accumulate consecutive no-motion goDown evidence for the main boundary.

        This intentionally uses the result of an input gesture, not any farm
        artwork. A real vertical move resets the streak; repeated low-change
        goDown gestures at the lower boundary prove exact-main for any account
        background.
        """
        value = float(change)
        if value <= float(max_change):
            self.camera_main_boundary_streak += 1
        else:
            self.camera_main_boundary_streak = 0
            self.camera_exact_main_proven = False

        if self.camera_main_boundary_streak >= int(stable_required):
            self.camera_exact_main_proven = True

        self.detail(
            "AUTO camera boundary | "
            f"reason={reason} | frame_change={value:.2f} | "
            f"max_change={float(max_change):.2f} | "
            f"stable={self.camera_main_boundary_streak}/{int(stable_required)} | "
            f"exact_main={str(self.camera_exact_main_proven).lower()}"
        )
        return bool(self.camera_exact_main_proven)

    def ensure_running(self) -> None:
        if self.stop_event.is_set():
            raise AutomationStopped("AUTO ClientJS đã được yêu cầu dừng")
