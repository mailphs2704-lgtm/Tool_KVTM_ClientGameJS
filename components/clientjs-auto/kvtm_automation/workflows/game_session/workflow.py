from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation
from ...errors import ScreenTimeout


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

    CLOSE_SIDE = (975, 316)
    DOWN_ONE = (514, 314, 514, 214)
    PORTAL_GRACE_SECONDS = 8.0

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context

    def _startup_go_down_one(self, label: str) -> None:
        """Dispatch one goDown(1), then force a fresh CAPTURE3 observation.

        Frame change is diagnostic only here. Repeated low-floor settling is
        allowed to reach the camera boundary, where a valid goDown can produce
        little or no visual movement. Only the final own-main classifier may
        declare startup normalization complete.
        """
        self.context.ensure_running()
        before = self.auto.screenshot().copy()
        self.auto.driver.click(*self.CLOSE_SIDE)
        self.auto.wait.sleep(0.15)
        self.auto.driver.swipe(
            *self.DOWN_ONE,
            duration=self.auto.speed_config.floor_swipe_duration,
        )
        self.auto.wait.sleep(0.70)
        after = self.auto.screenshot().copy()
        try:
            change = float(abs(
                after.astype("int16") - before.astype("int16")
            ).mean())
        except Exception:
            change = 0.0
        self.context.detail(
            "AUTO startup route | "
            f"gesture={label} | frame_change={change:.2f} | fresh_frame=true"
        )

    def _recover_floor_1_or_2_start(self) -> None:
        """STEP 2: one probe down plus exactly three settling goDown(1)s."""
        self.context.stage("clean-session-start-low-floor-recovery")
        self.context.log(
            "AUTO khởi điểm STEP 2 • chưa ở main • thử nhánh tầng 1/2 bằng goDown(1)"
        )

        self._startup_go_down_one("startup-low-floor-probe-1-of-4")

        # STEP 3/4 will add the short-lived down-floor button branch. Until that
        # detector is live-proven, this STEP 2 build only owns the low-floor
        # branch: exactly three additional goDown(1)s, then an exact main check.
        # A higher-floor start therefore fails closed below instead of continuing
        # production under a guessed camera state.
        for index in range(2, 5):
            self._startup_go_down_one(
                f"startup-low-floor-settle-{index}-of-4"
            )

        self.context.ensure_running()
        if not self.auto.popup.is_own_main_screen():
            raise ScreenTimeout(
                "STEP 2 đã gửi 1+3 goDown(1) nhưng chưa xác nhận được màn hình chính; "
                "dừng fail-close. Nếu khởi điểm tầng 3-10, chờ STEP 3 nút xuống tầng."
            )

        self.context.stage("clean-session-start-low-floor-main-confirmed")
        self.context.log(
            "AUTO khởi điểm STEP 2 • 1+3 goDown(1) hoàn tất • "
            "fresh-frame đã xác nhận màn hình chính"
        )

    def run(self, timeout: float = 180.0) -> GameSessionResult:
        started = time.monotonic()
        self.context.stage("clean-session-enter-game")

        # STEP 1: when already on own main, stay passive. This exact probe also
        # prevents an unnecessary low-floor recovery on the canonical start.
        started_on_main = self.auto.popup.is_own_main_screen()
        recovered_low_floor = False
        if started_on_main:
            self.context.stage("clean-session-start-main-detected")
            self.context.log(
                "AUTO khởi điểm • đã ở màn hình chính • giữ nguyên camera, không goDown"
            )
        else:
            # Preserve the proven portal/popup path first. A bounded grace window
            # lets ClientJS enter the game or dismiss blockers without turning a
            # portal/loading frame into a floor gesture. If it still cannot reach
            # main, STEP 2 takes ownership of the loaded non-main camera state.
            grace = min(float(timeout), self.PORTAL_GRACE_SECONDS)
            try:
                self.auto.ensure_main_screen(timeout=grace)
            except ScreenTimeout:
                self._recover_floor_1_or_2_start()
                recovered_low_floor = True
            else:
                started_on_main = True

        remaining = max(1.0, float(timeout) - (time.monotonic() - started))
        self.auto.ensure_main_screen(timeout=remaining)
        self.context.ensure_running()
        self.context.stage("clean-session-main-screen-ready")

        if started_on_main:
            self.context.log(
                "AUTO khởi điểm • màn hình chính đã xác nhận • bàn giao pipeline; "
                "goUp(1) chỉ do action gieo phát đúng một lần"
            )
        elif recovered_low_floor:
            self.context.log(
                "AUTO khởi điểm STEP 2 • bàn giao pipeline từ main đã chuẩn hóa; "
                "không phát thêm goUp ngoài action gieo"
            )

        return GameSessionResult(
            profile_id=self.context.profile_id,
            main_screen_ready=True,
            elapsed_seconds=round(time.monotonic() - started, 3),
            bridge_mode=str(self.auto.bridge_mode),
        )
