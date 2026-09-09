from __future__ import annotations

from ..errors import ScreenTimeout
from .function_one_navigation import FunctionOneNavigationActions, NavigationEvidence


__all__ = ["FunctionOnePassThreeNavigationActions"]
FILE_FUNCTIONS = (
    "Đưa camera từ máy Nước táo tầng 2 về màn hình chính bằng 1+3 nhịp goDown(1)",
    "Xác minh biên main bằng hai goDown liên tiếp có frame_change thấp, không dùng background",
    "Cho phép các nhịp settle chạm biên có frame_change thấp nhưng vẫn lấy fresh frame",
    "Sau khi gieo Bông, đi từ mốc tầng 1 lên tầng 3 bằng hai nhịp goUp(1)",
    "Cuối vòng tầng 3: goDown(1) rồi click nút xuống tầng AUTO PRO (497,978)",
    "Hậu kiểm click xuống tầng bằng frame-change và ghi runtime exact-main proof",
)


class FunctionOnePassThreeNavigationActions(FunctionOneNavigationActions):
    """Only the routes introduced by Function 1 pass 3."""

    # AUTO PRO goDownLast recovered bytecode: after goDown and check_xuong,
    # driver.click(497, 978). The clean asset set does not contain check_xuong,
    # so this recovered coordinate is never treated as a blind PASS: fresh-frame
    # change is required here.
    DOWN_FLOOR_POINT = (497, 978)

    # LIVE 2026-09-09 boundary evidence on an account whose farm background does
    # not match quay_hang: real downward moves measured 15.74 / 71.06 while
    # repeated no-op goDown at main measured 2.53..2.94. Require TWO consecutive
    # low-change observations so one stale/quiet frame can never prove main.
    MAIN_BOUNDARY_MAX_CHANGE = 6.0
    MAIN_BOUNDARY_STABLE_REQUIRED = 2

    def _settle_down_one(self, label: str) -> float:
        """Send one goDown(1), record fresh-frame change and learn main boundary.

        Exact-main recovery is behavioral. A real vertical move resets boundary
        evidence; two consecutive low-change goDown gestures prove that the camera
        has reached the lower boundary. No account-specific background/template is
        consulted.
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
                f"(change≤{self.MAIN_BOUNDARY_MAX_CHANGE:.1f}) • không phụ thuộc background"
            )
        return change

    def go_down_one_toward_main(self, label: str) -> float:
        """Public single-step primitive for controlled downward navigation."""
        return self._settle_down_one(label)

    def floor_3_to_main_via_down_floor(self) -> NavigationEvidence:
        """Run the operator-confirmed end-loop route from floor 3 to main.

        Sequence is exactly one goDown(1), then the recovered AUTO PRO down-floor
        button at (497,978). Since check_xuong is absent from the clean asset set,
        the button click must create a meaningful fresh-frame change. Successful
        completion itself is deterministic runtime evidence for exact-main.
        """
        swipe_change = self._settle_down_one(
            "function1-end-loop-floor3-goDown(1)"
        )
        self.context.ensure_running()
        before_click = self.vision.frame().copy()
        self.vision.driver.click(*self.DOWN_FLOOR_POINT)
        self.waiter.sleep(0.70)
        after_click = self.vision.frame().copy()
        click_change = self._change(before_click, after_click)
        self.context.detail(
            "AUTO route | gesture=function1-end-loop-click-down-floor | "
            f"point={self.DOWN_FLOOR_POINT} | frame_change={click_change:.2f} | "
            "fresh_frame=true | source=AUTO_PRO_goDownLast"
        )
        if click_change < self.MIN_CHANGE:
            self.context.invalidate_camera_main("end-loop down-floor click no response")
            raise ScreenTimeout(
                "Cuối vòng Function 1: click nút xuống tầng (497,978) "
                f"không tạo thay đổi hình ảnh (change={click_change:.2f}); "
                "dừng trước vòng kế tiếp"
            )
        self.context.mark_camera_exact_main(
            "floor3-to-main-via-down-floor deterministic route"
        )
        self.context.log(
            "AUTO điều hướng • cuối vòng tầng 3 → goDown(1) → "
            "click xuống tầng (497,978) đã có phản hồi"
        )
        return NavigationEvidence(
            "floor3-to-main-via-down-floor",
            (swipe_change, click_change),
        )

    def floor_2_to_main(self) -> NavigationEvidence:
        """Normalize the post-juice camera all the way to main before cotton.

        A single goDown(1) only moves floor 2 toward floor 1. Immediately letting
        CottonPlantingActions issue its own goUp(1) can cancel that movement and
        start planting one floor too high. Keep the operator-proven 1+3 sequence;
        its completion is deterministic exact-main evidence while each individual
        goDown also feeds the background-independent lower-boundary detector.
        """
        changes = tuple(
            self._settle_down_one(label)
            for label in (
                "post-juice-goDown(1)-probe-1-of-4",
                "post-juice-goDown(1)-settle-2-of-4",
                "post-juice-goDown(1)-settle-3-of-4",
                "post-juice-goDown(1)-settle-4-of-4",
            )
        )
        self.context.mark_camera_exact_main("floor2-to-main 1+3 deterministic route")
        self.context.log(
            "AUTO điều hướng • sau SX Nước táo • 1+3 x goDown(1) hoàn tất; "
            "exact-main runtime proof READY trước khi trồng Bông"
        )
        return NavigationEvidence("floor2-to-main-normalized", changes)

    def floor_1_to_floor_3(self) -> NavigationEvidence:
        changes = (
            self._gesture(self.UP_ONE, "floor1-goUp(1)-to-floor2"),
            self._gesture(self.UP_ONE, "floor2-goUp(1)-to-floor3"),
        )
        self.context.log(
            "AUTO điều hướng • mốc tầng 1 → tầng 3 • 2 x goUp(1) đã có phản hồi"
        )
        return NavigationEvidence("floor1-to-floor3", changes)
