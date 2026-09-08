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
    """Enter ClientJS, close blocking popups, and never move the farm camera."""

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context

    def run(self, timeout: float = 180.0) -> GameSessionResult:
        started = time.monotonic()
        self.context.stage("clean-session-enter-game")
        self.context.log(
            "AUTO Vào game + đóng popup • bắt đầu • startup không thực hiện goDown(1)"
        )

        # PopupActions owns portal/account entry plus popup dismissal. This call
        # may passively recognize the clone's farm to know the transaction is
        # complete, but GameSession itself performs no floor/camera navigation.
        self.auto.ensure_main_screen(timeout=float(timeout))

        self.context.ensure_running()
        self.context.stage("clean-session-startup-route-ready")
        self.context.log(
            "PASS | Vào game + đóng popup • đã vào farm • không di chuyển tầng/camera"
        )
        return GameSessionResult(
            profile_id=self.context.profile_id,
            main_screen_ready=True,
            elapsed_seconds=round(time.monotonic() - started, 3),
            bridge_mode=str(self.auto.bridge_mode),
        )
