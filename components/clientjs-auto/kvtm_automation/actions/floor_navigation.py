from __future__ import annotations

from dataclasses import dataclass

from ..context import AutomationContext
from ..errors import ScreenTimeout
from ..runtime.auto_speed_config import AutoSpeedConfig
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter


__all__ = ["FloorMoveResult", "FloorNavigationActions"]
FILE_FUNCTIONS = (
    "Chuyển đúng một tầng bằng nhịp goUp(1) đã đối chiếu AUTO PRO",
    "Hỗ trợ chuyển lên hoặc xuống theo từng nhịp đối xứng",
    "Giới hạn mỗi yêu cầu trong tối đa năm tầng",
    "Chụp fresh frame trước và sau từng nhịp để phát hiện thao tác không phản hồi",
    "Chờ camera ổn định sau từng tầng trước khi module sản xuất quét máy",
    "Phát lại nguyên nhánh goUp(4) của Auto Pro mà không tự nhận tầng",
)


@dataclass(frozen=True)
class FloorMoveResult:
    direction: str
    requested_steps: int
    completed_steps: int
    frame_change_scores: tuple[float, ...]


class FloorNavigationActions:
    """Deterministic one-floor camera movement for AUTO MULTI DEV."""

    MAX_STEPS = 5
    UP_SWIPE = (514, 214, 514, 314)
    DOWN_SWIPE = (514, 314, 514, 214)
    VIEW_ZONE = (180, 170, 700, 720)
    MIN_FRAME_CHANGE = 1.0
    SETTLE_SECONDS = 0.65
    AUTO_PRO_GO_UP_4_SWIPE = (387, 69, 387, 918)
    AUTO_PRO_GO_UP_3_POINT = (257, 191)
    AUTO_PRO_GO_UP_WAIT = 0.70
    AUTO_PRO_POST_WAIT = 0.15
    CLOSE_SIDE_POINT = (975, 316)

    def __init__(
        self,
        context: AutomationContext,
        vision: VisionEngine,
        waiter: Waiter,
        speed_config: AutoSpeedConfig | None = None,
    ) -> None:
        self.context = context
        self.vision = vision
        self.waiter = waiter
        self.speed_config = speed_config or AutoSpeedConfig()

    @classmethod
    def _frame_change(cls, before, after) -> float:
        x, y, width, height = cls.VIEW_ZONE
        old = before[y:y + height, x:x + width].astype("int16")
        new = after[y:y + height, x:x + width].astype("int16")
        if old.shape != new.shape or not old.size:
            return 0.0
        return float(abs(new - old).mean())

    def _move_one(self, direction: str, ordinal: int, total: int) -> float:
        self.context.ensure_running()
        points = self.UP_SWIPE if direction == "UP" else self.DOWN_SWIPE
        before = self.vision.frame().copy()
        self.vision.driver.swipe(
            *points, duration=self.speed_config.floor_swipe_duration
        )
        self.waiter.sleep(self.SETTLE_SECONDS)
        after = self.vision.frame().copy()
        change = self._frame_change(before, after)
        self.context.detail(
            "AUTO floor movement | "
            f"direction={direction} | step={ordinal}/{total} | "
            f"duration={self.speed_config.floor_swipe_duration:.3f}s | "
            f"frame_change={change:.2f}"
        )
        if change < self.MIN_FRAME_CHANGE:
            raise ScreenTimeout(
                "Chuyển tầng không tạo thay đổi hình ảnh; "
                "dừng trước khi quét hoặc chọn máy sản xuất"
            )
        self.context.log(
            f"AUTO chuyển tầng • {direction} • nhịp {ordinal}/{total} "
            f"đã có phản hồi hình ảnh"
        )
        return change

    def move(self, direction: str, steps: int = 1) -> FloorMoveResult:
        normalized = str(direction).strip().upper()
        if normalized not in {"UP", "DOWN"}:
            raise ValueError("direction chỉ nhận UP hoặc DOWN")
        requested = int(steps)
        if not 1 <= requested <= self.MAX_STEPS:
            raise ValueError("steps phải nằm trong khoảng 1..5")

        scores = []
        for ordinal in range(1, requested + 1):
            scores.append(self._move_one(normalized, ordinal, requested))
        return FloorMoveResult(
            direction=normalized,
            requested_steps=requested,
            completed_steps=len(scores),
            frame_change_scores=tuple(scores),
        )

    def reference_main_to_floor_6(self) -> FloorMoveResult:
        """Replay Auto Pro's target-6 sequence: goUp(4), then goUp(3)."""
        self.context.ensure_running()
        before = self.vision.frame().copy()

        self.vision.driver.click(*self.CLOSE_SIDE_POINT)
        self.vision.driver.swipe(
            *self.AUTO_PRO_GO_UP_4_SWIPE,
            duration=self.speed_config.plant_harvest_duration,
        )
        self.waiter.sleep(self.AUTO_PRO_GO_UP_WAIT)
        self.waiter.sleep(self.AUTO_PRO_POST_WAIT)
        after_mode_4 = self.vision.frame().copy()
        first_change = self._frame_change(before, after_mode_4)
        if first_change < self.MIN_FRAME_CHANGE:
            raise ScreenTimeout(
                "Auto Pro goUp(4) không tạo thay đổi; chưa tới mốc live tầng 3"
            )
        self.context.log(
            "DEMO • goUp(4) đã có phản hồi • mốc live kỳ vọng=tầng 3"
        )

        self.context.ensure_running()
        self.vision.driver.click(*self.CLOSE_SIDE_POINT)
        self.vision.driver.click(*self.AUTO_PRO_GO_UP_3_POINT)
        self.waiter.sleep(self.AUTO_PRO_GO_UP_WAIT)
        self.waiter.sleep(self.AUTO_PRO_POST_WAIT)
        after_mode_3 = self.vision.frame().copy()
        second_change = self._frame_change(after_mode_4, after_mode_3)
        if second_change < self.MIN_FRAME_CHANGE:
            raise ScreenTimeout(
                "Auto Pro goUp(3) không tạo thay đổi sau mốc tầng 3"
            )
        self.context.detail(
            "AUTO PRO floor sequence | target=6 | commands=goUp(4),goUp(3) | "
            f"mode4_path={self.AUTO_PRO_GO_UP_4_SWIPE} | "
            f"mode3_click={self.AUTO_PRO_GO_UP_3_POINT} | "
            f"duration={self.speed_config.plant_harvest_duration:.3f}s | "
            f"changes=({first_change:.2f},{second_change:.2f})"
        )
        self.context.log(
            "DEMO • đã gửi chuỗi Auto Pro goUp(4) → goUp(3) • "
            "chờ người vận hành xác nhận tầng 6"
        )
        return FloorMoveResult(
            direction="AUTO_PRO_TARGET_6",
            requested_steps=6,
            completed_steps=2,
            frame_change_scores=(first_change, second_change),
        )

    def up(self, steps: int = 1) -> FloorMoveResult:
        return self.move("UP", steps)

    def down(self, steps: int = 1) -> FloorMoveResult:
        return self.move("DOWN", steps)
