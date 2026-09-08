from __future__ import annotations

from .function_one_navigation import FunctionOneNavigationActions, NavigationEvidence


__all__ = ["FunctionOnePassThreeNavigationActions"]
FILE_FUNCTIONS = (
    "Đưa camera từ máy Nước táo tầng 2 về màn hình chính bằng 1+3 nhịp goDown(1)",
    "Cho phép các nhịp settle chạm biên có frame_change thấp nhưng vẫn lấy fresh frame",
    "Sau khi gieo Bông, đi từ mốc tầng 1 lên tầng 3 bằng hai nhịp goUp(1)",
)


class FunctionOnePassThreeNavigationActions(FunctionOneNavigationActions):
    """Only the two routes introduced by Function 1 pass 3."""

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
