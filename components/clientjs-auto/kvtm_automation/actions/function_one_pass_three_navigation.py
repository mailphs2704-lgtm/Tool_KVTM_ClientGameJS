from __future__ import annotations

from ..errors import ScreenTimeout
from ..runtime.down_floor_button import find_down_floor_button
from .function_one_navigation import FunctionOneNavigationActions, NavigationEvidence


__all__ = ["FunctionOnePassThreeNavigationActions"]
FILE_FUNCTIONS = (
    "Đưa camera từ máy Nước táo tầng 2 về màn hình chính bằng các nhịp goDown đã xác minh",
    "Xác minh biên main bằng goDown no-motion runtime evidence",
    "Sau khi gieo Bông, dùng Action goUp(2) dùng chung để click chậu tầng 4",
    "Cuối vòng tầng 3: goDown(1) rồi nhận diện/click nút XUỐNG ở mép dưới",
    "Giữ fallback nút XUỐNG operator-confirmed cho route đã live-verified",
    "Không sở hữu lại tọa độ goUp(1)/goUp(2)/goUp(4) trong file Function-specific",
)


class FunctionOnePassThreeNavigationActions(FunctionOneNavigationActions):
    """Compatibility route layer for Function-1 pass-three/down-boundary flows."""

    DOWN_FLOOR_POINT = (497, 978)
    DOWN_FLOOR_BUTTON_THRESHOLD = 0.78
    MAIN_BOUNDARY_MAX_CHANGE = 6.0
    MAIN_BOUNDARY_STABLE_REQUIRED = 2
    RECOVERY_DOWN_CHAIN_LIMIT = 10

    def _go_up_two(self, label: str) -> float:
        """Compatibility wrapper around the canonical goUp(2) Action."""
        result = self.go_up(2, label=label)
        change = float(result.frame_change_scores[0])
        self.context.log(
            "AUTO điều hướng • tầng 1 → tầng 3 • goUp(2) shared Action PASS • "
            f"point={self.GO_UP_TWO_POT_POINT} • frame_change={change:.2f}"
        )
        return change

    def _settle_down_one(self, label: str) -> float:
        """Boundary-aware goDown(1): low motion is evidence, not immediate failure.

        Do not invalidate the boundary streak before this gesture. Two or more
        consecutive low-motion goDown observations are exactly the proof used to
        establish the lower MAIN boundary. A real camera move resets that streak
        inside ``observe_camera_down_boundary``.
        """
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
        """Known upper-floor route: goDown(1), then the verified XUỐNG control."""
        swipe_label = f"{label}-goDown(1)"
        swipe_change = self._settle_down_one(swipe_label)
        click_change = self._click_down_floor_if_visible(swipe_label)

        if click_change is None:
            self.context.log(
                "AUTO route • nút XUỐNG template MISS • "
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
            f"AUTO điều hướng • {label} → goDown(1) → click XUỐNG → exact-main PASS"
        )
        return NavigationEvidence(
            f"{label}-via-down-floor",
            (swipe_change, click_change),
        )

    def floor_3_to_main_via_down_floor(self) -> NavigationEvidence:
        swipe_change = self._settle_down_one(
            "function1-end-loop-floor3-goDown(1)"
        )
        click_change = self._click_down_floor_if_visible(
            "function1-end-loop-floor3-goDown(1)"
        )
        if click_change is None:
            self.context.invalidate_camera_main(
                "end-loop down-floor button absent or no response"
            )
            raise ScreenTimeout(
                "Cuối vòng Function 1: sau goDown(1) không xác minh/click được "
                "nút XUỐNG ở mép dưới; dừng trước vòng kế tiếp"
            )
        self.context.mark_camera_exact_main(
            "floor3-to-main-via-down-floor deterministic route",
            source="navigation-route",
        )
        self.context.log(
            "AUTO điều hướng • cuối vòng tầng 3 → goDown(1) → "
            "click XUỐNG → exact-main PASS"
        )
        return NavigationEvidence(
            "floor3-to-main-via-down-floor",
            (swipe_change, click_change),
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
            self._go_up_two("floor1-goUp(2)-floor4-pot-to-floor3"),
        )
        self.context.log(
            "AUTO điều hướng • tầng 1 → tầng 3 • goUp(2) shared Action PASS"
        )
        return NavigationEvidence("floor1-to-floor3-goUp2", changes)
