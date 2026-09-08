from __future__ import annotations

from ..errors import ScreenTimeout
from .function_one_navigation import FunctionOneNavigationActions, NavigationEvidence


__all__ = ["FunctionOnePassThreeNavigationActions"]
FILE_FUNCTIONS = (
    "Đưa camera từ máy Nước táo tầng 2 về màn hình chính bằng 1+3 nhịp goDown(1)",
    "Cho phép các nhịp settle chạm biên có frame_change thấp nhưng vẫn lấy fresh frame",
    "Sau khi gieo Bông, đi từ mốc tầng 1 lên tầng 3 bằng hai nhịp goUp(1)",
    "Cuối vòng tầng 3: goDown(1) rồi click nút xuống tầng AUTO PRO (497,978)",
    "Hậu kiểm click xuống tầng bằng frame-change; workflow exact-main là gate cuối",
)


class FunctionOnePassThreeNavigationActions(FunctionOneNavigationActions):
    """Only the routes introduced by Function 1 pass 3."""

    # AUTO PRO goDownLast recovered bytecode: after goDown and check_xuong,
    # driver.click(497, 978). The clean asset set does not contain check_xuong,
    # so this recovered coordinate is never treated as a blind PASS: fresh-frame
    # change is required here and the caller must exact-check own main afterwards.
    DOWN_FLOOR_POINT = (497, 978)

    def _settle_down_one(self, label: str) -> float:
        """Send one goDown(1) and record fresh-frame change without boundary fail.

        During post-juice normalization the last settling gestures may already be
        at the camera floor. Low or zero frame change is therefore allowed here;
        exact own-main classification in the workflow is the real gate before the
        next planting stage.
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
        self.context.detail(
            f"AUTO route | gesture={label} | frame_change={change:.2f} | "
            "fresh_frame=true | boundary_change_non_blocking=true"
        )
        return change

    def go_down_one_toward_main(self, label: str) -> float:
        """Public single-step primitive for controlled downward navigation."""
        return self._settle_down_one(label)

    def floor_3_to_main_via_down_floor(self) -> NavigationEvidence:
        """Run the operator-confirmed end-loop route from floor 3 to main.

        Sequence is exactly one goDown(1), then the recovered AUTO PRO down-floor
        button at (497,978). Since check_xuong is absent from the clean asset set,
        the button click must create a meaningful fresh-frame change. The workflow
        performs the stronger exact own-main gate immediately after this method.
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
            raise ScreenTimeout(
                "Cuối vòng Function 1: click nút xuống tầng (497,978) "
                f"không tạo thay đổi hình ảnh (change={click_change:.2f}); "
                "dừng trước vòng kế tiếp"
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
        start planting one floor too high. Use the same low-floor normalization
        contract as startup: one probe plus three settling goDown(1)s. The caller
        then performs the exact own-main classifier before cotton starts.
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
        self.context.log(
            "AUTO điều hướng • sau SX Nước táo • 1+3 x goDown(1) hoàn tất; "
            "exact-main transition check phải PASS trước khi trồng Bông"
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
