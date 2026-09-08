from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation


@dataclass(frozen=True)
class GameSessionResult:
    profile_id: str
    main_screen_ready: bool
    elapsed_seconds: float
    bridge_mode: str

    def to_dict(self) -> dict:
        return asdict(self)


class GameSessionWorkflow:
    """First clean AUTO layer: connect, enter game, clear modals, verify home."""

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context

    def run(self, timeout: float = 180.0) -> GameSessionResult:
        started = time.monotonic()
        self.context.stage("clean-session-enter-game")

        # Startup normalization is being added case-by-case. The first locked
        # case is intentionally passive: when the worker already starts on the
        # clone's own main farm screen, do not emit any downward floor gesture.
        # Keep the camera at the canonical main anchor and let the existing
        # production path own the single goUp(1) transition when planting begins.
        started_on_main = self.auto.popup.is_own_main_screen()
        if started_on_main:
            self.context.stage("clean-session-start-main-detected")
            self.context.log(
                "AUTO khởi điểm • đã ở màn hình chính • giữ nguyên camera, không goDown"
            )

        self.auto.ensure_main_screen(timeout=float(timeout))
        self.context.ensure_running()
        self.context.stage("clean-session-main-screen-ready")

        if started_on_main:
            self.context.log(
                "AUTO khởi điểm • màn hình chính đã xác nhận • bàn giao pipeline; "
                "goUp(1) chỉ do action gieo phát đúng một lần"
            )

        return GameSessionResult(
            profile_id=self.context.profile_id,
            main_screen_ready=True,
            elapsed_seconds=round(time.monotonic() - started, 3),
            bridge_mode=str(self.auto.bridge_mode),
        )
