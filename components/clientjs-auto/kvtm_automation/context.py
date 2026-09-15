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
    "Ghi log hành động tối giản theo tài khoản qua action()",
    "Đưa log nghiệp vụ/kỹ thuật đầy đủ sang Log chi tiết qua log()/detail()",
    "Báo stage nghiệp vụ mà không làm nhiễu Log hành động",
    "Giữ bằng chứng camera exact-main theo nguồn chứng minh rõ ràng",
    "Đánh dấu MAIN mặc định sau login/restart mà không gửi goDown",
    "Dừng tác vụ theo stop-event",
)


@dataclass
class AutomationContext:
    """Runtime state shared by reusable KVTM automation actions.

    No AUTO PRO object is stored here. The context owns only the selected
    ClientJS process/profile, paths, cancellation signal and reporting hooks.

    ``action()`` is deliberately reserved for operator-facing milestones. The
    historical ``log()`` API remains available to every existing Action/Recipe,
    but now routes to the detailed stream so hundreds of recognition/navigation
    lines cannot flood the concise action log.

    ``camera_exact_main_proven`` is runtime state evidence instead of an
    account-background classification. Most of the run proves MAIN through a
    deterministic navigation route/boundary. Startup is the one explicit
    exception agreed by the operator: immediately after a fresh login/restart,
    the game camera is already at MAIN, so startup records that contract without
    sending a synthetic ``goDown(1)``.
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
    pirate_chest_opened_at_monotonic: float | None = field(
        default=None,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        self.pid = int(self.pid)
        self.profile_id = str(self.profile_id)
        self.profile_name = str(self.profile_name)
        self.auto_root = Path(self.auto_root).resolve()
        self.work_dir = Path(self.work_dir).resolve()
        if self.profile_file is not None:
            self.profile_file = Path(self.profile_file).resolve()
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def action(self, message: str) -> None:
        """Write one concise operator-facing milestone with account identity."""
        name = self.profile_name.strip() or self.profile_id
        self.logger(f". {name} . {str(message).strip()}")

    def log(self, message: str) -> None:
        """Compatibility log API: keep full runtime chatter in Log chi tiết."""
        if self.detail_logger is not None:
            self.detail_logger(str(message))
            return
        self.logger(str(message))

    def detail(self, message: str) -> None:
        if self.detail_logger is not None:
            self.detail_logger(str(message))
            return
        self.logger(str(message))

    def stage(self, name: str) -> None:
        if self.stage_reporter is not None:
            self.stage_reporter(str(name))
        self.detail(str(name))

    def invalidate_camera_main(self, reason: str = "") -> None:
        """Forget exact-main proof before/after any camera state uncertainty."""
        self.camera_exact_main_proven = False
        self.camera_main_boundary_streak = 0
        if reason:
            self.detail(f"AUTO camera proof | exact_main=false | reason={reason}")

    def mark_camera_exact_main(
        self,
        reason: str,
        *,
        source: str = "runtime-route",
    ) -> None:
        """Record exact-main with an explicit proof source.

        ``source`` is diagnostic metadata only. Callers still own the safety
        decision that allows exact-main to be marked.
        """
        self.camera_exact_main_proven = True
        self.camera_main_boundary_streak = 0
        self.detail(
            "AUTO camera proof | exact_main=true | "
            f"source={str(source)} | reason={reason}"
        )

    def mark_startup_exact_main(self, reason: str = "fresh login/restart default MAIN") -> None:
        """Apply the operator-approved startup camera contract without goDown."""
        self.mark_camera_exact_main(reason, source="startup-contract")

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

    def mark_pirate_chest_opened(self) -> float:
        """Record one proven open after reward modal close + center chest return."""
        opened_at = time.monotonic()
        self.pirate_chest_opened_at_monotonic = opened_at
        self.detail(
            "AUTO rương hải tặc | OPENED evidence stored | "
            "reward_modal_closed=true | center_chest_visible=true"
        )
        return opened_at

    def ensure_running(self) -> None:
        if self.stop_event.is_set():
            raise AutomationStopped("AUTO ClientJS đã được yêu cầu dừng")
