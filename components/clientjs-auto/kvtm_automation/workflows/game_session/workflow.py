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
        self.auto.ensure_main_screen(timeout=float(timeout))
        self.context.ensure_running()
        self.context.stage("clean-session-main-screen-ready")
        return GameSessionResult(
            profile_id=self.context.profile_id,
            main_screen_ready=True,
            elapsed_seconds=round(time.monotonic() - started, 3),
            bridge_mode=str(self.auto.bridge_mode),
        )
