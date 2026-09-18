from __future__ import annotations

from dataclasses import dataclass

from ..context import AutomationContext
from ..errors import ScreenTimeout
from ..runtime.auto_speed_config import AutoSpeedConfig
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter


__all__ = ["FloorMoveResult", "FloorNavigationActions"]
FILE_FUNCTIONS = (
    "Cung cấp bộ Action chuyển tầng dùng chung cho toàn AUTO",
    "goUp(mode) = primitive di chuyển bằng swipe để log/recovery nhận diện",
    "goUpClick(1) = click chậu đầu hàng 3 để di chuyển một tầng",
    "goUpClick(2) = click chậu đầu hàng 4 để di chuyển hai tầng",
    "goUpClick(3) = click điểm trên cùng để di chuyển ba tầng",
    "goUp(4) = một swipe dài bốn tầng theo AUTO PRO",
    "goUp(3) chưa có contract và phải fail-close, không tự suy đoán",
    "Giữ goDown(1)/goDown(4) hiện có cho các route đã live-verified",
    "Fresh-frame verify sau mỗi primitive trước khi trả control cho Module/Function",
)


@dataclass(frozen=True)
class FloorMoveResult:
    direction: str
    requested_steps: int
    completed_steps: int
    frame_change_scores: tuple[float, ...]


class FloorNavigationActions:
    """Canonical reusable farm-camera primitives.

    Important: the integer in ``go_up(mode)`` is an AUTO action *mode*, not a
    request to repeat ``goUp(1)`` N times. The operator has explicitly defined
    swipe modes 1 and 4 as two different input primitives. Click-based
    movement is deliberately exposed only through ``go_up_click(1..3)``.
    """

    GO_UP_ONE_SWIPE = (514, 214, 514, 314)
    GO_DOWN_ONE_SWIPE = (514, 314, 514, 214)
    GO_UP_CLICK_ONE_POINT = (398, 488)
    GO_UP_CLICK_TWO_POINT = (398, 267)
    GO_UP_CLICK_THREE_POINT = (398, 59)
    GO_UP_TWO_POT_POINT = GO_UP_CLICK_TWO_POINT
    GO_UP_FOUR_SWIPE = (387, 69, 387, 918)
    GO_DOWN_FOUR_SWIPE = (387, 918, 387, 69)
    CLOSE_SIDE_POINT = (975, 316)

    # Compatibility aliases retained for older verified route adapters.
    UP_SWIPE = GO_UP_ONE_SWIPE
    DOWN_SWIPE = GO_DOWN_ONE_SWIPE
    AUTO_PRO_GO_UP_4_SWIPE = GO_UP_FOUR_SWIPE

    VIEW_ZONE = (180, 170, 700, 720)
    MIN_FRAME_CHANGE = 1.0
    SETTLE_SECONDS = 0.65
    AUTO_PRO_GO_UP_WAIT = 0.70
    AUTO_PRO_POST_WAIT = 0.15
    MAX_STEP_SEQUENCE = 8

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

    # Compatibility name used by the older Function navigation adapters.
    @classmethod
    def _change(cls, before, after) -> float:
        return cls._frame_change(before, after)

    def _verify_change(self, before, *, label: str) -> float:
        after = self.vision.frame().copy()
        change = self._frame_change(before, after)
        self.context.detail(
            "AUTO navigation primitive | "
            f"label={label} | frame_change={change:.2f} | fresh_frame=true"
        )
        if change < self.MIN_FRAME_CHANGE:
            raise ScreenTimeout(
                f"Điều hướng {label} không tạo thay đổi hình ảnh; fail-close"
            )
        return change

    def _prepare_camera_input(self, label: str) -> None:
        self.context.ensure_running()
        self.context.invalidate_camera_main(f"navigation:{label}")
        self.vision.driver.click(*self.CLOSE_SIDE_POINT)
        self.waiter.sleep(self.AUTO_PRO_POST_WAIT)

    def _swipe_primitive(
        self,
        points: tuple[int, int, int, int],
        *,
        label: str,
    ) -> float:
        self._prepare_camera_input(label)
        before = self.vision.frame().copy()
        self.vision.driver.swipe(
            *points,
            duration=self.speed_config.plant_harvest_duration,
        )
        self.waiter.sleep(self.AUTO_PRO_GO_UP_WAIT)
        self.waiter.sleep(self.AUTO_PRO_POST_WAIT)
        return self._verify_change(before, label=label)

    def _click_primitive(
        self,
        point: tuple[int, int],
        *,
        label: str,
    ) -> float:
        self._prepare_camera_input(label)
        before = self.vision.frame().copy()
        self.vision.driver.click(*point)
        self.waiter.sleep(self.AUTO_PRO_GO_UP_WAIT)
        self.waiter.sleep(self.AUTO_PRO_POST_WAIT)
        return self._verify_change(before, label=label)

    def go_up(self, mode: int, *, label: str | None = None) -> FloorMoveResult:
        """Execute one standardized swipe-based goUp mode.

        Only ``goUp(1)`` and ``goUp(4)`` exist. Never synthesize swipe modes 2
        or 3; those distances belong to ``goUpClick``.
        """
        selected = int(mode)
        action_label = str(label or f"goUp({selected})")
        if selected == 1:
            change = self._swipe_primitive(
                self.GO_UP_ONE_SWIPE,
                label=action_label,
            )
        elif selected == 4:
            change = self._swipe_primitive(
                self.GO_UP_FOUR_SWIPE,
                label=action_label,
            )
        elif selected == 3:
            raise ValueError(
                "goUp(3) chưa được operator định nghĩa; không được tự ghép/suy đoán"
            )
        else:
            raise ValueError(
                "goUp là di chuyển swipe và hiện chỉ nhận mode 1 hoặc 4; "
                "di chuyển click phải dùng goUpClick(1..3)"
            )

        self.context.log(
            f"AUTO điều hướng • {action_label} PASS • frame_change={change:.2f}"
        )
        return FloorMoveResult(
            direction=f"GO_UP_{selected}",
            requested_steps=selected,
            completed_steps=1,
            frame_change_scores=(change,),
        )

    def go_up_click(
        self,
        floors: int,
        *,
        label: str | None = None,
    ) -> FloorMoveResult:
        """Move upward by clicking an operator-confirmed pot/scene anchor."""
        selected = int(floors)
        points = {
            1: self.GO_UP_CLICK_ONE_POINT,
            2: self.GO_UP_CLICK_TWO_POINT,
            3: self.GO_UP_CLICK_THREE_POINT,
        }
        point = points.get(selected)
        if point is None:
            raise ValueError("goUpClick chỉ nhận số tầng đã chốt: 1, 2 hoặc 3")
        action_label = str(label or f"goUpClick({selected})")
        change = self._click_primitive(point, label=action_label)
        self.context.log(
            f"AUTO điều hướng click • {action_label} PASS • "
            f"point={point} • frame_change={change:.2f}"
        )
        return FloorMoveResult(
            direction=f"GO_UP_CLICK_{selected}",
            requested_steps=selected,
            completed_steps=selected,
            frame_change_scores=(change,),
        )

    def go_down(self, mode: int, *, label: str | None = None) -> FloorMoveResult:
        """Execute an already-used down primitive; no new down modes are guessed."""
        selected = int(mode)
        action_label = str(label or f"goDown({selected})")
        if selected == 1:
            change = self._swipe_primitive(
                self.GO_DOWN_ONE_SWIPE,
                label=action_label,
            )
        elif selected == 4:
            change = self._swipe_primitive(
                self.GO_DOWN_FOUR_SWIPE,
                label=action_label,
            )
        else:
            raise ValueError("goDown hiện chỉ có primitive đã dùng: 1 hoặc 4")
        self.context.log(
            f"AUTO điều hướng • {action_label} PASS • frame_change={change:.2f}"
        )
        return FloorMoveResult(
            direction=f"GO_DOWN_{selected}",
            requested_steps=selected,
            completed_steps=1,
            frame_change_scores=(change,),
        )

    def move(self, direction: str, steps: int = 1) -> FloorMoveResult:
        """Compatibility helper for an explicit sequence of one-floor swipes.

        This method is *not* goUp(mode). New business code should call
        ``go_up(mode)``. ``move('UP', 2)`` means two separate goUp(1) primitives.
        """
        normalized = str(direction).strip().upper()
        if normalized not in {"UP", "DOWN"}:
            raise ValueError("direction chỉ nhận UP hoặc DOWN")
        requested = int(steps)
        if not 1 <= requested <= self.MAX_STEP_SEQUENCE:
            raise ValueError(
                f"steps phải nằm trong khoảng 1..{self.MAX_STEP_SEQUENCE}"
            )

        scores: list[float] = []
        for ordinal in range(1, requested + 1):
            if normalized == "UP":
                result = self.go_up(
                    1,
                    label=f"move-UP-one-{ordinal}-of-{requested}",
                )
            else:
                result = self.go_down(
                    1,
                    label=f"move-DOWN-one-{ordinal}-of-{requested}",
                )
            scores.extend(result.frame_change_scores)
        return FloorMoveResult(
            direction=normalized,
            requested_steps=requested,
            completed_steps=requested,
            frame_change_scores=tuple(scores),
        )

    def reference_main_to_floor_6(self) -> FloorMoveResult:
        """Compatibility route composed only from canonical primitives."""
        first = self.go_up(1, label="target6-goUp(1)-initial")
        middle = self.go_up(4, label="target6-goUp(4)")
        final = self.go_up(1, label="target6-goUp(1)-final")
        scores = (
            *first.frame_change_scores,
            *middle.frame_change_scores,
            *final.frame_change_scores,
        )
        self.context.log(
            "AUTO route • target tầng 6 • goUp(1) → goUp(4) → goUp(1) PASS"
        )
        return FloorMoveResult(
            direction="AUTO_PRO_TARGET_6",
            requested_steps=6,
            completed_steps=3,
            frame_change_scores=tuple(scores),
        )

    def up(self, mode: int = 1) -> FloorMoveResult:
        """Standardized public alias: integer is goUp mode, not repeat count."""
        return self.go_up(mode)

    def down(self, mode: int = 1) -> FloorMoveResult:
        return self.go_down(mode)
