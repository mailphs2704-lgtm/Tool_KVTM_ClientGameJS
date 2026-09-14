from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation
from ...errors import ScreenTimeout
from ..pirate_chest.workflow import PirateChestStatus, PirateChestWorkflow


@dataclass(frozen=True)
class GameSessionResult:
    profile_id: str
    main_screen_ready: bool
    elapsed_seconds: float
    bridge_mode: str
    popup_watch_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


class GameSessionWorkflow:
    """Login/restart startup module with a fixed 60-second popup watch window.

    Contract approved by the operator:

    * reach the clone farm/login-complete state without moving the farm camera;
    * a fresh login/restart starts at MAIN, so record that startup contract;
    * for the next 60 seconds continuously detect and close any popup that
      appears; do not sleep for 60 seconds and sweep only afterwards;
    * never send ``goDown(1)`` merely to prove MAIN during this startup phase.
    """

    POPUP_WATCH_SECONDS = 60.0
    POPUP_POLL_SECONDS = 0.45

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context

    def _resume_pirate_chest_if_visible(
        self,
        *,
        require_exact_main_after_close: bool,
    ) -> bool:
        result = PirateChestWorkflow(
            self.auto
        ).resume_open_prompt_if_visible(
            require_exact_main_after_close=require_exact_main_after_close,
        )
        if result is None:
            return False
        if result.status != PirateChestStatus.OPENED.value:
            raise ScreenTimeout(
                "Startup phát hiện modal rương tồn tại nhưng chưa hoàn tất an toàn: "
                f"status={result.status}, detail={result.detail}"
            )
        self.context.log(
            "AUTO startup • resume modal rương PASS • "
            "đã nhận quà và đóng panel trước khi tiếp tục popup/login"
        )
        return True

    def _watch_popups(self, seconds: float) -> None:
        duration = max(0.0, float(seconds))
        deadline = time.monotonic() + duration
        closed = 0
        self.context.stage("clean-session-popup-watch-start")
        self.context.log(
            f"AUTO startup • bắt đầu check popup liên tục {duration:.0f}s"
        )

        while time.monotonic() < deadline:
            self.context.ensure_running()
            if self._resume_pirate_chest_if_visible(
                require_exact_main_after_close=True
            ):
                continue
            if self.auto.popup.dismiss_one():
                closed += 1
                self.context.detail(
                    "AUTO startup popup watch | "
                    f"closed={closed} | remaining={max(0.0, deadline - time.monotonic()):.2f}s"
                )
                continue
            self.auto.wait.sleep(
                min(self.POPUP_POLL_SECONDS, max(0.0, deadline - time.monotonic()))
            )

        self.context.ensure_running()
        self.context.stage("clean-session-popup-watch-finished")
        self.context.log(
            f"AUTO startup • đủ {duration:.0f}s • dừng check popup • đã đóng={closed}"
        )

    def run(self, timeout: float = 180.0) -> GameSessionResult:
        started = time.monotonic()
        self.context.stage("clean-session-enter-game")
        self.context.log(
            "AUTO Vào game + đóng popup • bắt đầu • startup không thực hiện goDown(1)"
        )

        # A persisted Pirate Chest prompt cannot be dismissed by the generic
        # modal/backdrop handler. Finish it first, then let PopupActions own the
        # remaining portal/account and ordinary popup recovery.
        self._resume_pirate_chest_if_visible(
            require_exact_main_after_close=False
        )
        self.auto.ensure_main_screen(timeout=float(timeout))
        self.context.ensure_running()

        # User-approved invariant: after a fresh login/restart the game camera is
        # already at MAIN. Record this explicitly instead of manufacturing a
        # navigation proof with goDown.
        self.context.mark_startup_exact_main(
            "login/restart hoàn tất; camera mặc định MAIN trước popup watch"
        )

        self._watch_popups(self.POPUP_WATCH_SECONDS)

        # Popups may hide the HUD temporarily, but closing a popup must not move
        # the camera. If the own-farm HUD is no longer visible at the end, fail
        # closed rather than trying an unrequested camera route.
        if not self.auto.popup.is_own_main_screen():
            raise ScreenTimeout(
                "Startup đã đủ 60s nhưng không còn xác nhận được farm HUD; "
                "không tự goDown để sửa camera"
            )
        if not self.context.camera_exact_main_proven:
            raise ScreenTimeout(
                "Startup mất MAIN contract trong lúc popup watch; dừng fail-close"
            )

        self.context.stage("clean-session-startup-route-ready")
        self.context.log(
            "PASS | Vào game + popup watch 60s • camera MAIN giữ nguyên • không goDown"
        )
        return GameSessionResult(
            profile_id=self.context.profile_id,
            main_screen_ready=True,
            elapsed_seconds=round(time.monotonic() - started, 3),
            bridge_mode=str(self.auto.bridge_mode),
            popup_watch_seconds=self.POPUP_WATCH_SECONDS,
        )
