from __future__ import annotations

from dataclasses import dataclass

from ..errors import ScreenTimeout
from ..runtime.down_floor_button import find_down_floor_button
from .floor_navigation import FloorNavigationActions


__all__ = [
    "FarmRouteActions",
    "FarmBoundaryRouteActions",
    "NavigationEvidence",
]


@dataclass(frozen=True)
class NavigationEvidence:
    route: str
    frame_changes: tuple[float, ...]


class FarmRouteActions(FloorNavigationActions):
    """Canonical reusable farm route composer over floor primitives.

    Route composition belongs here because the same verified routes are consumed
    by Functions, Recipes and Global Recovery. Function-specific compatibility
    classes may inherit this implementation, but canonical code must depend on
    FarmRouteActions/FarmBoundaryRouteActions.
    """

    CLOSE_SIDE = FloorNavigationActions.CLOSE_SIDE_POINT
    UP_ONE = FloorNavigationActions.GO_UP_ONE_SWIPE
    DOWN_ONE = FloorNavigationActions.GO_DOWN_ONE_SWIPE
    UP_FOUR = FloorNavigationActions.GO_UP_FOUR_SWIPE
    DOWN_FOUR = FloorNavigationActions.GO_DOWN_FOUR_SWIPE
    MIN_CHANGE = FloorNavigationActions.MIN_FRAME_CHANGE
    MAIN_TO_FLOOR_CLICK_ROUTE = {
        1: (),
        2: (1,),
        3: (2,),
        4: (3,),
        5: (3, 1),
        6: (3, 2),
        7: (3, 3),
        8: (3, 3, 1),
        9: (3, 3, 2),
        10: (3, 3, 3),
    }

    @staticmethod
    def _scores(*results) -> tuple[float, ...]:
        scores: list[float] = []
        for result in results:
            scores.extend(result.frame_change_scores)
        return tuple(scores)

    def _gesture(self, points, label: str) -> float:
        """Compatibility adapter for historical route callers."""
        normalized = tuple(points)
        if normalized == self.UP_ONE:
            result = self.go_up(1, label=label)
        elif normalized == self.UP_FOUR:
            result = self.go_up(4, label=label)
        elif normalized == self.DOWN_ONE:
            result = self.go_down(1, label=label)
        elif normalized == self.DOWN_FOUR:
            result = self.go_down(4, label=label)
        else:
            raise ValueError(
                f"Route adapter nhận geometry chưa đăng ký: {normalized}; fail-close"
            )
        return float(result.frame_change_scores[0])

    def floor_1_to_main(self) -> NavigationEvidence:
        result = self.go_down(1, label="floor1-goDown(1)-to-main")
        self.context.mark_camera_exact_main(
            "floor1-to-main deterministic route",
            source="navigation-route",
        )
        self.context.log("AUTO điều hướng • tầng 1 → MAIN • goDown(1) PASS")
        return NavigationEvidence("floor1-to-main", self._scores(result))

    def main_to_floor_1(self) -> NavigationEvidence:
        result = self.go_up(1, label="main-goUp(1)-to-floor1")
        self.context.log("AUTO điều hướng • MAIN → tầng 1 • goUp(1) PASS")
        return NavigationEvidence("main-to-floor1", self._scores(result))

    def floor_1_to_floor_5(self) -> NavigationEvidence:
        result = self.go_up(4, label="floor1-goUp(4)-to-floor5")
        self.context.log("AUTO điều hướng • tầng 1 → tầng 5 • goUp(4) PASS")
        return NavigationEvidence("floor1-to-floor5", self._scores(result))

    def floor_1_to_floor_6(self) -> NavigationEvidence:
        first = self.go_up(4, label="floor1-goUp(4)-to-floor5")
        second = self.go_up(1, label="floor5-goUp(1)-to-floor6")
        self.context.log(
            "AUTO điều hướng • tầng 1 → tầng 6 • goUp(4) → goUp(1) PASS"
        )
        return NavigationEvidence(
            "floor1-to-floor6",
            self._scores(first, second),
        )

    def floor_6_to_floor_2(self) -> NavigationEvidence:
        result = self.go_down(4, label="floor6-goDown(4)-to-floor2-candidate")
        self.context.log(
            "AUTO điều hướng • tầng 6 → candidate tầng 2 • goDown(4) PASS • "
            "Recipe chịu trách nhiệm xác minh anchor máy"
        )
        return NavigationEvidence(
            "floor6-to-floor2-candidate",
            self._scores(result),
        )

    def floor_6_to_main(self) -> NavigationEvidence:
        first = self.go_down(4, label="floor6-goDown(4)-to-floor2")
        second = self.go_down(1, label="floor2-goDown(1)-to-floor1")
        third = self.go_down(1, label="floor1-goDown(1)-to-main")
        self.context.mark_camera_exact_main(
            "floor6-to-main deterministic route",
            source="navigation-route",
        )
        self.context.log("AUTO điều hướng • tầng 6 → MAIN PASS")
        return NavigationEvidence(
            "floor6-to-main",
            self._scores(first, second, third),
        )

    def main_to_floor_2(self) -> NavigationEvidence:
        return self.main_to_floor(2)

    def main_to_floor_3(self) -> NavigationEvidence:
        return self.main_to_floor(3)

    def main_to_floor(self, target_floor: int) -> NavigationEvidence:
        floor = int(target_floor)
        click_route = self.MAIN_TO_FLOOR_CLICK_ROUTE.get(floor)
        if click_route is None:
            raise ValueError("Recovery MAIN hiện chỉ có route tầng 1..10")

        results = [self.go_up(1, label="main-goUp(1)-to-floor1")]
        current_floor = 1
        for ordinal, click_floors in enumerate(click_route, start=1):
            next_floor = current_floor + int(click_floors)
            results.append(
                self.go_up_click(
                    click_floors,
                    label=(
                        f"recovery-main-floor{floor}-click-{ordinal}-"
                        f"goUpClick({click_floors})-to-floor{next_floor}"
                    ),
                )
            )
            current_floor = next_floor

        if current_floor != floor:
            raise RuntimeError(
                f"Route MAIN → tầng {floor} sai tổng bước: kết thúc tầng {current_floor}"
            )
        route_text = " → ".join(
            ("goUp(1) swipe", *(f"goUpClick({step})" for step in click_route))
        )
        self.context.log(
            f"AUTO recovery route • MAIN → tầng {floor} • {route_text} PASS"
        )
        return NavigationEvidence(
            f"main-to-floor{floor}",
            self._scores(*results),
        )


class FarmBoundaryRouteActions(FarmRouteActions):
    """Canonical boundary-aware farm routes shared by Recipes and Recovery."""

    DOWN_FLOOR_POINT = (497, 978)
    DOWN_FLOOR_BUTTON_THRESHOLD = 0.78
    DOWN_FLOOR_ANIMATION_SETTLE_SECONDS = 1.0
    MAIN_BOUNDARY_MAX_CHANGE = 6.0
    MAIN_BOUNDARY_STABLE_REQUIRED = 2
    RECOVERY_DOWN_CHAIN_LIMIT = 10

    def _go_up_two(self, label: str) -> float:
        result = self.go_up_click(2, label=label)
        change = float(result.frame_change_scores[0])
        self.context.log(
            "AUTO điều hướng • tầng 1 → tầng 3 • goUpClick(2) PASS • "
            f"point={self.GO_UP_CLICK_TWO_POINT} • frame_change={change:.2f}"
        )
        return change

    def _settle_down_one(self, label: str) -> float:
        """Boundary-aware goDown(1): low motion is evidence, not immediate failure."""
        self.context.ensure_running()
        before = self.vision.frame().copy()
        self.vision.driver.click(*self.CLOSE_SIDE)
        self.waiter.sleep(0.15)
        self.vision.driver.swipe(
            *self.DOWN_ONE,
            duration=self.speed_config.floor_swipe_duration,
        )
        self.waiter.sleep(0.70)
        after = self.vision.frame().copy()
        change = self._change(before, after)
        was_exact = bool(self.context.camera_exact_main_proven)
        exact = self.context.observe_camera_down_boundary(
            change,
            max_change=self.MAIN_BOUNDARY_MAX_CHANGE,
            stable_required=self.MAIN_BOUNDARY_STABLE_REQUIRED,
            reason=label,
        )
        self.context.detail(
            f"AUTO route | gesture={label} | frame_change={change:.2f} | "
            "fresh_frame=true | boundary_change_non_blocking=true | "
            f"exact_main={str(exact).lower()}"
        )
        if exact and not was_exact:
            self.context.log(
                "AUTO điều hướng • exact-main PASS bằng biên goDown • "
                f"{self.MAIN_BOUNDARY_STABLE_REQUIRED} nhịp liên tiếp không dịch camera "
                f"(change≤{self.MAIN_BOUNDARY_MAX_CHANGE:.1f})"
            )
        return change

    def _click_down_floor_if_visible(self, label: str) -> float | None:
        self.context.ensure_running()
        before_click = self.vision.frame().copy()
        match = find_down_floor_button(
            before_click,
            threshold=self.DOWN_FLOOR_BUTTON_THRESHOLD,
        )
        if match is None:
            self.context.detail(
                "AUTO route | down_floor_button=false | "
                f"after={label} | floor1_or_button_not_exposed=true"
            )
            return None

        self.context.invalidate_camera_main(f"down-floor-button-visible:{label}")
        self.vision.driver.click(*match.center)
        self.waiter.sleep(0.70)
        after_click = self.vision.frame().copy()
        click_change = self._change(before_click, after_click)
        self.context.detail(
            "AUTO route | gesture=click-down-floor-visible | "
            f"after={label} | score={match.score:.4f} | "
            f"center={match.center} | box={match.box} | scale={match.scale:.2f} | "
            f"frame_change={click_change:.2f} | fresh_frame=true"
        )
        if click_change < self.MIN_CHANGE:
            self.context.detail(
                "AUTO route | down_floor_button_click_response=false | "
                f"after={label} | frame_change={click_change:.2f}"
            )
            return None

        self.context.log(
            "AUTO điều hướng • thấy nút XUỐNG ở mép dưới → click ngay • "
            f"score={match.score:.3f}"
        )
        return click_change

    def go_down_one_toward_main(self, label: str) -> float:
        changes: list[float] = []
        for step in range(1, self.RECOVERY_DOWN_CHAIN_LIMIT + 1):
            chained_label = (
                f"{label}-chain-{step}-of-{self.RECOVERY_DOWN_CHAIN_LIMIT}"
            )
            changes.append(self._settle_down_one(chained_label))
            click_change = self._click_down_floor_if_visible(chained_label)
            if click_change is None:
                break
            changes.append(click_change)
        return max(changes) if changes else 0.0

    def known_upper_floor_to_main_via_down_floor(self, label: str) -> NavigationEvidence:
        swipe_label = f"{label}-goDown(1)"
        swipe_change = self._settle_down_one(swipe_label)
        self.context.ensure_running()
        self.context.log(
            "AUTO route • goDown(1) xong • chờ 1.0s ổn định animation nút XUỐNG trước click"
        )
        self.waiter.sleep(self.DOWN_FLOOR_ANIMATION_SETTLE_SECONDS)
        click_change = self._click_down_floor_if_visible(swipe_label)

        if click_change is None:
            self.context.log(
                "AUTO route • nút XUỐNG template MISS/no-response • "
                f"fallback operator point={self.DOWN_FLOOR_POINT}"
            )
            self.context.invalidate_camera_main(
                f"{label}: fixed down-floor fallback"
            )
            before_click = self.vision.frame().copy()
            self.vision.driver.click(*self.DOWN_FLOOR_POINT)
            self.waiter.sleep(0.70)
            after_click = self.vision.frame().copy()
            click_change = self._change(before_click, after_click)
            self.context.detail(
                "AUTO route | gesture=click-down-floor-fixed-fallback | "
                f"after={swipe_label} | point={self.DOWN_FLOOR_POINT} | "
                f"frame_change={click_change:.2f} | fresh_frame=true"
            )
            if click_change < self.MIN_CHANGE:
                self.context.invalidate_camera_main(
                    f"{label}: fixed down-floor fallback no response"
                )
                raise ScreenTimeout(
                    f"{label}: goDown(1) đã gửi nhưng click XUỐNG tại "
                    f"{self.DOWN_FLOOR_POINT} không tạo phản hồi hình ảnh"
                )
            self.context.log(
                "AUTO route • fallback nút XUỐNG PASS • "
                f"point={self.DOWN_FLOOR_POINT} • frame_change={click_change:.2f}"
            )

        self.context.mark_camera_exact_main(
            f"{label} via goDown(1)+down-floor deterministic route",
            source="navigation-route",
        )
        self.context.log(
            f"AUTO điều hướng • {label} → goDown(1) → chờ 1s → click XUỐNG → exact-main PASS"
        )
        return NavigationEvidence(
            f"{label}-via-down-floor",
            (swipe_change, click_change),
        )

    def floor_3_to_main_via_down_floor(self) -> NavigationEvidence:
        evidence = self.known_upper_floor_to_main_via_down_floor(
            "tầng 3 → MAIN"
        )
        return NavigationEvidence(
            "floor3-to-main-via-down-floor",
            evidence.frame_changes,
        )

    def floor_5_to_main_via_down_floor(self) -> NavigationEvidence:
        evidence = self.known_upper_floor_to_main_via_down_floor(
            "tầng 5 → MAIN"
        )
        return NavigationEvidence(
            "floor5-to-main-via-down-floor",
            evidence.frame_changes,
        )

    def floor_6_to_main_via_down_floor(self) -> NavigationEvidence:
        evidence = self.known_upper_floor_to_main_via_down_floor(
            "tầng 6 → MAIN"
        )
        return NavigationEvidence(
            "floor6-to-main-via-down-floor",
            evidence.frame_changes,
        )

    def floor_2_to_main(self) -> NavigationEvidence:
        changes = tuple(
            self._settle_down_one(label)
            for label in (
                "post-juice-goDown(1)-probe-1-of-4",
                "post-juice-goDown(1)-settle-2-of-4",
                "post-juice-goDown(1)-settle-3-of-4",
                "post-juice-goDown(1)-settle-4-of-4",
            )
        )
        self.context.mark_camera_exact_main(
            "floor2-to-main 1+3 deterministic route",
            source="navigation-route",
        )
        self.context.log(
            "AUTO điều hướng • sau SX Nước táo • 1+3 x goDown(1) hoàn tất; "
            "exact-main READY trước khi trồng Bông"
        )
        return NavigationEvidence("floor2-to-main-normalized", changes)

    def floor_1_to_floor_3(self) -> NavigationEvidence:
        changes = (
            self._go_up_two("floor1-goUpClick(2)-floor4-pot-to-floor3"),
        )
        self.context.log(
            "AUTO điều hướng • tầng 1 → tầng 3 • goUpClick(2) shared Action PASS"
        )
        return NavigationEvidence("floor1-to-floor3-goUp2", changes)
