from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ..automation import KVAutomation
from ..errors import ScreenTimeout


__all__ = ["FeedMillResult", "FeedMillWorkflow"]

FILE_FUNCTIONS = (
    "Chỉ chạy tại exact-main sau Function và bán VP ở safe boundary",
    "Vào map sự kiện cám qua hitbox NPC sói do operator xác nhận",
    "Click máy xay hai lần, giữa hai click chờ animation đúng 1.5 giây",
    "Xác nhận panel ổn định rồi kéo bông lúa xuống ô nhận bằng một BATCH_SWIPE",
    "Xác nhận timer sản xuất xuất hiện trước khi đóng panel",
    "Bấm Nhà, chờ map ổn định và chứng minh lại exact-main trước khi trả scheduler",
)


@dataclass(frozen=True)
class FeedMillResult:
    profile_id: str
    produced: bool
    elapsed_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


class FeedMillWorkflow:
    """Operator-confirmed event-feed sequence in logical 1000x1000 space."""

    # Operator's red marker is on the wolf at the lower-left edge of MAIN.
    # The previous (706, 704) point hit the NPC beside the haunted house and
    # never entered the feed event map.
    EVENT_WOLF_POINT = (587, 940)
    MILL_ENTRY_POINT = (316, 749)
    WHEAT_POINT = (412, 380)
    MILL_INPUT_POINT = (245, 558)
    PANEL_CLOSE_POINT = (834, 359)
    HOME_POINT = (37, 963)

    EVENT_MAP_WAIT_SECONDS = 4.0
    BETWEEN_MILL_CLICKS_SECONDS = 1.5
    PANEL_SETTLE_SECONDS = 2.5
    WHEAT_SWIPE_DURATION_SECONDS = 0.30
    SWIPE_SETTLE_SECONDS = 1.5
    HOME_MAP_SETTLE_SECONDS = 5.0
    EVENT_MAP_CHANGE_THRESHOLD = 25.0
    EVENT_MAP_ENTRY_ATTEMPTS = 2

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context
        self.vision = automation.vision
        self.driver = automation.driver

    def _tap(self, point: tuple[int, int], stage: str) -> None:
        self.context.ensure_running()
        self.context.stage(stage)
        self.driver.click(*point)

    def _crop(self, frame, zone: tuple[int, int, int, int]):
        x, y, w, h = self.vision.logical_zone_to_frame(zone, frame)
        return frame[y : y + h, x : x + w]

    @staticmethod
    def _color_ratio(roi, predicate) -> float:
        if roi is None or getattr(roi, "size", 0) == 0:
            return 0.0
        blue = roi[..., 0]
        green = roi[..., 1]
        red = roi[..., 2]
        return float(predicate(red, green, blue).mean())

    def _production_panel_ready(self, frame) -> bool:
        # Cream/orange product header plus the dark modal overlay. This checks
        # the stable panel shown by the operator without matching animated art.
        header = self._crop(frame, (350, 340, 450, 105))
        corner = self._crop(frame, (0, 0, 120, 120))
        cream = self._color_ratio(
            header,
            lambda r, g, b: (r >= 180) & (g >= 90) & (g <= 210) & (b <= 150),
        )
        return cream >= 0.30 and float(corner.mean()) < 105.0

    def _production_started(self, frame) -> bool:
        # After a successful swipe, the left machine shows a blue countdown.
        timer = self._crop(frame, (175, 442, 105, 32))
        blue = self._color_ratio(
            timer,
            lambda r, g, b: (b >= 120) & (g >= 95) & (r <= 120),
        )
        return blue >= 0.12

    @staticmethod
    def _frame_change_score(before, after) -> float:
        if before is None or after is None or before.shape != after.shape:
            return 0.0
        # int16 prevents uint8 subtraction wrap-around. A real MAIN -> event
        # transition is a full-screen change (operator evidence is ~98 mean
        # absolute levels); ordinary idle animation stays far below 25.
        delta = before.astype("int16") - after.astype("int16")
        return float(abs(delta).mean())

    def _enter_event_map(self, main_frame) -> None:
        for attempt in range(1, self.EVENT_MAP_ENTRY_ATTEMPTS + 1):
            self._tap(
                self.EVENT_WOLF_POINT,
                f"auto-feed-mill-enter-event-map-{attempt}",
            )
            self.auto.wait.sleep(self.EVENT_MAP_WAIT_SECONDS)
            score = self._frame_change_score(main_frame, self.vision.frame())
            self.context.log(
                "AUTO Sx cám • kiểm tra vào map sự kiện • "
                f"attempt={attempt}/{self.EVENT_MAP_ENTRY_ATTEMPTS} • "
                f"frame_change={score:.2f}/{self.EVENT_MAP_CHANGE_THRESHOLD:.2f}"
            )
            if score >= self.EVENT_MAP_CHANGE_THRESHOLD:
                return
        raise ScreenTimeout("Sx cám chưa vào được map sự kiện sau khi click NPC sói")

    def run(self) -> FeedMillResult:
        started = time.monotonic()
        self.context.ensure_running()
        if not self.auto.popup.is_own_exact_main_screen():
            raise ScreenTimeout("Sx cám chỉ được bắt đầu từ own exact-main")

        self.context.stage("auto-feed-mill-start")
        self.context.log(
            "AUTO Sx cám • bắt đầu tại safe boundary sau Function + bán VP"
        )
        main_frame = self.vision.frame()
        self.context.invalidate_camera_main("feed-mill-leave-own-main")
        self._enter_event_map(main_frame)

        self._tap(self.MILL_ENTRY_POINT, "auto-feed-mill-entry-click-1")
        self.auto.wait.sleep(self.BETWEEN_MILL_CLICKS_SECONDS)
        self._tap(self.MILL_ENTRY_POINT, "auto-feed-mill-entry-click-2")
        self.auto.wait.sleep(self.PANEL_SETTLE_SECONDS)

        if not self._production_panel_ready(self.vision.frame()):
            raise ScreenTimeout("Sx cám chưa xác nhận được panel máy xay ổn định")

        self.context.stage("auto-feed-mill-wheat-swipe")
        self.driver.swipe_points(
            (self.WHEAT_POINT, self.MILL_INPUT_POINT),
            duration=self.WHEAT_SWIPE_DURATION_SECONDS,
        )
        self.auto.wait.sleep(self.SWIPE_SETTLE_SECONDS)
        if not self._production_started(self.vision.frame()):
            raise ScreenTimeout("Sx cám swipe xong nhưng chưa thấy timer sản xuất")

        self._tap(self.PANEL_CLOSE_POINT, "auto-feed-mill-close-panel")
        self.auto.wait.sleep(0.5)
        self._tap(self.HOME_POINT, "auto-feed-mill-return-home")
        self.auto.wait.sleep(self.HOME_MAP_SETTLE_SECONDS)
        self.context.ensure_running()

        # The event-map Home button is a deterministic own-home transition.
        self.context.mark_camera_exact_main("feed-mill event-home deterministic route")
        if not self.auto.popup.is_own_exact_main_screen():
            raise ScreenTimeout("Sx cám đã bấm Nhà nhưng chưa chứng minh exact-main")

        self.context.stage("auto-feed-mill-finished")
        self.context.action("Đã xay cám • chu kỳ tiếp theo sau 35 phút")
        self.context.log("AUTO Sx cám • PASS • đã về own exact-main")
        return FeedMillResult(
            profile_id=self.context.profile_id,
            produced=True,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )
