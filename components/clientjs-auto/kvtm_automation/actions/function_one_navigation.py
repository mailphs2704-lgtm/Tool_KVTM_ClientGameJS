from __future__ import annotations

from dataclasses import dataclass

from ..context import AutomationContext
from ..errors import ScreenTimeout
from ..runtime.auto_speed_config import AutoSpeedConfig
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter


__all__ = ["FunctionOneNavigationActions", "NavigationEvidence"]
FILE_FUNCTIONS = (
    "Đi từ màn hình chính lên tầng 1 và từ tầng 1 về main bằng đúng một goUp/goDown(1)",
    "Đi từ tầng 1 lên tầng 5 bằng nhánh goUp(4) AUTO PRO",
    "Đi từ tầng 1 lên tầng 6 bằng phần còn lại goUp(4), goUp(1)",
    "Đi thẳng từ tầng 6 xuống candidate tầng 2 bằng đúng goDown(4)",
    "Giữ route tầng 6 về main đối xứng 4,1,1 cho recovery cũ",
    "Đi từ màn hình chính lên tầng 2 bằng hai nhịp goUp(1)",
    "Kiểm tra fresh-frame change sau từng gesture và fail-closed",
    "Đánh dấu exact-main bằng route runtime đã biết, không bằng background",
)


@dataclass(frozen=True)
class NavigationEvidence:
    route: str
    frame_changes: tuple[float, ...]


class FunctionOneNavigationActions:
    CLOSE_SIDE = (975, 316)
    UP_ONE = (514, 214, 514, 314)
    DOWN_ONE = (514, 314, 514, 214)
    UP_FOUR = (387, 69, 387, 918)
    DOWN_FOUR = (387, 918, 387, 69)
    VIEW_ZONE = (180, 170, 700, 720)
    MIN_CHANGE = 1.0

    def __init__(self, context: AutomationContext, vision: VisionEngine,
                 waiter: Waiter, speed_config: AutoSpeedConfig | None = None) -> None:
        self.context = context
        self.vision = vision
        self.waiter = waiter
        self.speed_config = speed_config or AutoSpeedConfig()

    @classmethod
    def _change(cls, before, after) -> float:
        x, y, width, height = cls.VIEW_ZONE
        old = before[y:y + height, x:x + width].astype("int16")
        new = after[y:y + height, x:x + width].astype("int16")
        if old.shape != new.shape or not old.size:
            return 0.0
        return float(abs(new - old).mean())

    def _gesture(self, points, label: str) -> float:
        self.context.ensure_running()
        self.context.invalidate_camera_main(f"vertical-gesture:{label}")
        before = self.vision.frame().copy()
        self.vision.driver.click(*self.CLOSE_SIDE)
        self.vision.driver.swipe(
            *points, duration=self.speed_config.plant_harvest_duration
        )
        self.waiter.sleep(0.70)
        self.waiter.sleep(0.15)
        change = self._change(before, self.vision.frame().copy())
        self.context.detail(f"AUTO route | gesture={label} | frame_change={change:.2f}")
        if change < self.MIN_CHANGE:
            raise ScreenTimeout(f"Điều hướng {label} không tạo thay đổi hình ảnh")
        return change

    def floor_1_to_main(self) -> NavigationEvidence:
        changes = (
            self._gesture(self.DOWN_ONE, "floor1-goDown(1)-to-main"),
        )
        self.context.mark_camera_exact_main("floor1-to-main deterministic route")
        self.context.log(
            "AUTO điều hướng • tầng 1 → màn hình chính • goDown(1) đã có phản hồi"
        )
        return NavigationEvidence("floor1-to-main", changes)

    def main_to_floor_1(self) -> NavigationEvidence:
        changes = (
            self._gesture(self.UP_ONE, "main-goUp(1)-to-floor1"),
        )
        self.context.log(
            "AUTO điều hướng • màn hình chính → tầng 1 • goUp(1) đã có phản hồi"
        )
        return NavigationEvidence("main-to-floor1", changes)

    def floor_1_to_floor_5(self) -> NavigationEvidence:
        changes = (
            self._gesture(self.UP_FOUR, "floor1-goUp(4)-to-floor5"),
        )
        self.context.log(
            "AUTO điều hướng • tầng 1 → tầng 5 • goUp(4) AUTO PRO đã có phản hồi"
        )
        return NavigationEvidence("floor1-to-floor5", changes)

    def floor_1_to_floor_6(self) -> NavigationEvidence:
        changes = (
            self._gesture(self.UP_FOUR, "floor1-goUp(4)-to-floor5"),
            self._gesture(self.UP_ONE, "floor5-goUp(1)-to-floor6"),
        )
        self.context.log(
            "AUTO điều hướng • tầng 1 → tầng 6 • goUp(4) → goUp(1) đã có phản hồi"
        )
        return NavigationEvidence("floor1-to-floor6", changes)

    def floor_6_to_floor_2(self) -> NavigationEvidence:
        """Fast Function-1 route: floor 6 -> candidate floor 2 with one goDown(4)."""
        changes = (
            self._gesture(self.DOWN_FOUR, "floor6-goDown(4)-to-floor2-candidate"),
        )
        self.context.log(
            "AUTO điều hướng • tầng 6 → candidate tầng 2 • goDown(4) đã có phản hồi "
            "• chờ anchor Nước táo xác minh tầng"
        )
        return NavigationEvidence("floor6-to-floor2-candidate", changes)

    def floor_6_to_main(self) -> NavigationEvidence:
        changes = (
            self._gesture(self.DOWN_FOUR, "floor6-goDown(4)-to-floor2"),
            self._gesture(self.DOWN_ONE, "floor2-goDown(1)-to-floor1"),
            self._gesture(self.DOWN_ONE, "floor1-goDown(1)-to-main"),
        )
        self.context.mark_camera_exact_main("floor6-to-main deterministic route")
        self.context.log("AUTO điều hướng • tầng 6 → màn hình chính đã có phản hồi")
        return NavigationEvidence("floor6-to-main", changes)

    def main_to_floor_2(self) -> NavigationEvidence:
        changes = (
            self._gesture(self.UP_ONE, "main-goUp(1)-to-floor1"),
            self._gesture(self.UP_ONE, "floor1-goUp(1)-to-floor2"),
        )
        self.context.log("AUTO điều hướng • màn hình chính → tầng 2 đã có phản hồi")
        return NavigationEvidence("main-to-floor2", changes)
