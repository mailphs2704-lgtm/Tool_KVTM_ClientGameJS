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
    """Connect/enter ClientJS and prepare the startup camera without stage gates."""

    CLOSE_SIDE = (975, 316)
    DOWN_ONE = (514, 314, 514, 214)
    PORTAL_GRACE_SECONDS = 8.0

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context

    def _startup_go_down_one(self, label: str) -> None:
        """Dispatch one startup goDown(1) and keep fresh-frame diagnostics only."""
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
        """Startup low-floor settling: one probe plus exactly three goDown(1)s.

        This route no longer owns a fatal main-screen classifier. The operator's
        latest contract places exact state checks only at business transitions
        between planting/production stages. Startup merely normalizes the camera
        and hands control to the first business action.
        """
        self.context.stage("clean-session-start-low-floor-recovery")
        self.context.log(
            "AUTO khởi điểm STEP 2 • chưa ở main • thử nhánh tầng 1/2 bằng goDown(1)"
        )

        self._startup_go_down_one("startup-low-floor-probe-1-of-4")
        for index in range(2, 5):
            self._startup_go_down_one(
                f"startup-low-floor-settle-{index}-of-4"
            )

        self.context.ensure_running()
        self.context.stage("clean-session-start-low-floor-settled")
        self.context.log(
            "AUTO khởi điểm STEP 2 • 1+3 goDown(1) hoàn tất • "
            "không gate main tại startup; exact check chỉ chạy ở transition nghiệp vụ"
        )

    def run(self, timeout: float = 180.0) -> GameSessionResult:
        started = time.monotonic()
        self.context.stage("clean-session-enter-game")

        # Keep the initial home probe only as a routing hint so a clone already
        # at main does not receive unnecessary down gestures. It is not a PASS
        # gate. Fatal exact-main checks belong to inter-stage navigation.
        started_on_main = self.auto.popup.is_own_main_screen()
        recovered_low_floor = False
        if started_on_main:
            self.context.stage("clean-session-start-main-detected")
            self.context.log(
                "AUTO khởi điểm • thấy màn hình chính • giữ nguyên camera, không goDown"
            )
        else:
            # Give the existing portal/popup route a short opportunity to enter
            # the game or clear blockers. A timeout here is only a signal to run
            # low-floor camera settling; it is not itself a startup failure.
            grace = min(float(timeout), self.PORTAL_GRACE_SECONDS)
            try:
                self.auto.ensure_main_screen(timeout=grace)
            except ScreenTimeout:
                self._recover_floor_1_or_2_start()
                recovered_low_floor = True
            else:
                started_on_main = True

        self.context.ensure_running()
        self.context.stage("clean-session-startup-route-ready")

        if started_on_main:
            self.context.log(
                "AUTO khởi điểm • route sẵn sàng • bàn giao pipeline; "
                "không đặt exact-main gate tại session"
            )
        elif recovered_low_floor:
            self.context.log(
                "AUTO khởi điểm STEP 2 • bàn giao pipeline sau 1+3 goDown(1); "
                "exact-main gate được hoãn tới transition trồng/sản xuất"
            )

        return GameSessionResult(
            profile_id=self.context.profile_id,
            main_screen_ready=bool(started_on_main),
            elapsed_seconds=round(time.monotonic() - started, 3),
            bridge_mode=str(self.auto.bridge_mode),
        )
