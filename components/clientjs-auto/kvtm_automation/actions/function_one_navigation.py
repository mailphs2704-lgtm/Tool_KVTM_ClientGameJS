from __future__ import annotations

from dataclasses import dataclass

from .floor_navigation import FloorNavigationActions


__all__ = ["FunctionOneNavigationActions", "NavigationEvidence"]
FILE_FUNCTIONS = (
    "Compatibility route composer; primitive input lives only in FloorNavigationActions",
    "main → tầng 1 bằng goUp(1)",
    "tầng 1 → tầng 5 bằng goUp(4)",
    "tầng 1 → tầng 6 bằng goUp(4) + goUp(1)",
    "tầng 6 → candidate tầng 2 bằng goDown(4)",
    "main → tầng 2 bằng hai lệnh goUp(1), không được gọi goUp(2)",
    "Không giữ tọa độ/swipe Function-specific trùng với Action dùng chung",
)


@dataclass(frozen=True)
class NavigationEvidence:
    route: str
    frame_changes: tuple[float, ...]


class FunctionOneNavigationActions(FloorNavigationActions):
    """Verified Function-1 route composition over canonical navigation Actions.

    This class intentionally contains routes only. Coordinates and the semantic
    meaning of goUp modes are owned by ``FloorNavigationActions`` so another
    Function can reuse the same primitives without copying input logic.
    """

    # Compatibility aliases used by the older pass-three/down-boundary adapter.
    CLOSE_SIDE = FloorNavigationActions.CLOSE_SIDE_POINT
    UP_ONE = FloorNavigationActions.GO_UP_ONE_SWIPE
    DOWN_ONE = FloorNavigationActions.GO_DOWN_ONE_SWIPE
    UP_FOUR = FloorNavigationActions.GO_UP_FOUR_SWIPE
    DOWN_FOUR = FloorNavigationActions.GO_DOWN_FOUR_SWIPE
    MIN_CHANGE = FloorNavigationActions.MIN_FRAME_CHANGE

    @staticmethod
    def _scores(*results) -> tuple[float, ...]:
        scores: list[float] = []
        for result in results:
            scores.extend(result.frame_change_scores)
        return tuple(scores)

    def _gesture(self, points, label: str) -> float:
        """Legacy internal adapter; all known geometry routes to canonical Actions."""
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
        self.context.log(
            "AUTO điều hướng • tầng 1 → MAIN • goDown(1) PASS"
        )
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
        # Critical distinction: goUp(2) means the floor-4-pot anchor jump and
        # would be wrong here. MAIN → floor2 is explicitly two goUp(1) Actions.
        first = self.go_up(1, label="main-goUp(1)-to-floor1")
        second = self.go_up(1, label="floor1-goUp(1)-to-floor2")
        self.context.log(
            "AUTO điều hướng • MAIN → tầng 2 • goUp(1) + goUp(1) PASS"
        )
        return NavigationEvidence(
            "main-to-floor2",
            self._scores(first, second),
        )
