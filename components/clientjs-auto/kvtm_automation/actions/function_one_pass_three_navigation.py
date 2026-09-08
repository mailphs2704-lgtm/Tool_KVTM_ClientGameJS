from __future__ import annotations

from .function_one_navigation import FunctionOneNavigationActions, NavigationEvidence


__all__ = ["FunctionOnePassThreeNavigationActions"]
FILE_FUNCTIONS = (
    "Đưa camera từ máy Nước táo tầng 2 về màn hình chính bằng 1+3 nhịp goDown(1)",
    "Sau khi gieo Bông, đi từ mốc tầng 1 lên tầng 3 bằng hai nhịp goUp(1)",
    "Tái sử dụng hậu kiểm fresh-frame change fail-closed của navigation pass trước",
)


class FunctionOnePassThreeNavigationActions(FunctionOneNavigationActions):
    """Only the two routes introduced by Function 1 pass 3."""

    def floor_2_to_main(self) -> NavigationEvidence:
        """Normalize the post-juice camera all the way to main before cotton.

        A single goDown(1) only moves floor 2 toward floor 1. Immediately letting
        CottonPlantingActions issue its own goUp(1) can therefore cancel that
        movement and start planting one floor too high. Match the proven low-floor
        normalization contract instead: one probe plus three settling goDown(1)s,
        with a fresh-frame change check after every gesture. The caller performs
        the exact own-main classifier before cotton starts.
        """
        changes = (
            self._gesture(self.DOWN_ONE, "post-juice-goDown(1)-probe-1-of-4"),
            self._gesture(self.DOWN_ONE, "post-juice-goDown(1)-settle-2-of-4"),
            self._gesture(self.DOWN_ONE, "post-juice-goDown(1)-settle-3-of-4"),
            self._gesture(self.DOWN_ONE, "post-juice-goDown(1)-settle-4-of-4"),
        )
        self.context.log(
            "AUTO điều hướng • sau SX Nước táo • 1+3 x goDown(1) đã ép camera về đáy; "
            "chờ exact-main transition check trước khi trồng Bông"
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
