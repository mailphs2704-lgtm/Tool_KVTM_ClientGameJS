from __future__ import annotations

from .function_one_navigation import FunctionOneNavigationActions, NavigationEvidence


__all__ = ["FunctionOnePassThreeNavigationActions"]
FILE_FUNCTIONS = (
    "Đưa camera từ máy Nước táo tầng 2 về màn hình chính bằng hai nhịp goDown(1)",
    "Sau khi gieo Bông, đi từ mốc tầng 1 lên tầng 3 bằng hai nhịp goUp(1)",
    "Tái sử dụng hậu kiểm fresh-frame change fail-closed của navigation pass trước",
)


class FunctionOnePassThreeNavigationActions(FunctionOneNavigationActions):
    """Only the two routes introduced by Function 1 pass 3."""

    def floor_2_to_main(self) -> NavigationEvidence:
        changes = (
            self._gesture(self.DOWN_ONE, "floor2-goDown(1)-to-floor1"),
            self._gesture(self.DOWN_ONE, "floor1-goDown(1)-to-main"),
        )
        self.context.log(
            "AUTO điều hướng • tầng 2 → màn hình chính • 2 x goDown(1) đã có phản hồi"
        )
        return NavigationEvidence("floor2-to-main", changes)

    def floor_1_to_floor_3(self) -> NavigationEvidence:
        changes = (
            self._gesture(self.UP_ONE, "floor1-goUp(1)-to-floor2"),
            self._gesture(self.UP_ONE, "floor2-goUp(1)-to-floor3"),
        )
        self.context.log(
            "AUTO điều hướng • mốc tầng 1 → tầng 3 • 2 x goUp(1) đã có phản hồi"
        )
        return NavigationEvidence("floor1-to-floor3", changes)
