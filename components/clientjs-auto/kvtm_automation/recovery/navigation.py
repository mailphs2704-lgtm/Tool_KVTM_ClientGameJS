from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from ..errors import ScreenTimeout
from .events import RecoveryEvent, RecoveryEventKind

if TYPE_CHECKING:
    from ..automation import KVAutomation


EventSink = Callable[[RecoveryEvent], None]
RouteHandler = Callable[[str], None]


class NavigationRecovery:
    """Reusable camera/floor recovery shared by every Function and Recipe.

    Default routes cover the currently proven floors 1..3. Future Functions can
    inject main/floor or floor/floor routes without copying unknown-camera,
    XUỐNG-button, exact-main, or retry policy into business code.
    """

    UNKNOWN_FLOOR_MAIN_RECOVERY_PASSES = 6

    def __init__(
        self,
        automation: KVAutomation,
        *,
        emit: EventSink,
        to_main_routes: Mapping[int, RouteHandler] | None = None,
        from_main_routes: Mapping[int, RouteHandler] | None = None,
        between_floor_routes: Mapping[tuple[int, int], RouteHandler] | None = None,
    ) -> None:
        self.auto = automation
        self.context = automation.context
        self.emit = emit
        self._to_main_routes = dict(to_main_routes or {})
        self._from_main_routes = dict(from_main_routes or {})
        self._between_floor_routes = dict(between_floor_routes or {})

    def ensure_main(self, label: str) -> None:
        self.context.ensure_running()
        if not self.auto.popup.is_own_exact_main_screen():
            raise ScreenTimeout(
                f"Recovery: {label} chưa xác nhận exact-main; dừng trước bước kế tiếp"
            )
        self.emit(RecoveryEvent(RecoveryEventKind.MAIN_PROVEN, label=label))
        self.context.log(f"AUTO recovery • {label} • exact main PASS")

    def recover_unknown_to_main(
        self,
        label: str,
        *,
        reason: str = "unknown-camera",
        max_passes: int | None = None,
    ) -> None:
        """Normalize an unknown camera using the proven goDown/XUỐNG/boundary path."""
        passes = int(max_passes or self.UNKNOWN_FLOOR_MAIN_RECOVERY_PASSES)
        self.context.stage("auto-recovery-unknown-camera-to-main")
        self.context.invalidate_camera_main(reason)
        self.emit(
            RecoveryEvent(
                RecoveryEventKind.UNKNOWN_CAMERA,
                label=label,
                details={"reason": reason, "max_passes": passes},
            )
        )

        for attempt in range(1, passes + 1):
            self.context.ensure_running()
            if self.auto.popup.is_own_exact_main_screen():
                break
            self.auto.function_one_pass_three_navigation.go_down_one_toward_main(
                f"recovery-{label}-{attempt}-of-{passes}"
            )
            if self.auto.popup.is_own_exact_main_screen():
                break
        else:
            self.emit(
                RecoveryEvent(
                    RecoveryEventKind.RECOVERY_EXHAUSTED,
                    label=label,
                    attempt=passes,
                    details={"reason": reason},
                )
            )
            raise ScreenTimeout(
                f"Recovery {label}: không chứng minh được exact-main sau {passes} lượt"
            )

        self.ensure_main(f"{label}: unknown → main")

    def to_main_from_floor(self, floor: int, label: str) -> None:
        """Use a known-floor deterministic route, then require exact-main proof."""
        floor = int(floor)
        self.context.stage(f"auto-recovery-floor-{floor}-to-main")
        custom = self._to_main_routes.get(floor)
        if custom is not None:
            custom(label)
        elif floor == 1:
            self.auto.function_one_navigation.floor_1_to_main()
        elif floor == 2:
            self.auto.function_one_pass_three_navigation.floor_2_to_main()
        elif floor == 3:
            self.auto.function_one_pass_three_navigation.floor_3_to_main_via_down_floor()
        else:
            raise ValueError(
                f"Chưa có route tầng {floor} → main; Function/Recipe phải inject to_main_routes"
            )
        self.ensure_main(f"{label}: tầng {floor} → main")

    def from_main_to_floor(self, floor: int, label: str) -> None:
        """Enter a requested floor from proven main using a default or injected route."""
        floor = int(floor)
        self.ensure_main(f"{label}: trước main → tầng {floor}")
        self.context.invalidate_camera_main(f"recovery-main-to-floor-{floor}:{label}")
        self.context.stage(f"auto-recovery-main-to-floor-{floor}")
        custom = self._from_main_routes.get(floor)
        if custom is not None:
            custom(label)
        elif floor == 1:
            self.auto.function_one_navigation.main_to_floor_1()
        elif floor == 2:
            self.auto.function_one_navigation.main_to_floor_2()
        elif floor == 3:
            self.auto.function_one_navigation.main_to_floor_1()
            self.auto.function_one_pass_three_navigation.floor_1_to_floor_3()
        else:
            raise ValueError(
                f"Chưa có route main → tầng {floor}; Function/Recipe phải inject from_main_routes"
            )

        self.emit(
            RecoveryEvent(
                RecoveryEventKind.FLOOR_REENTERED,
                label=label,
                floor=floor,
            )
        )
        self.context.log(
            f"AUTO recovery • đã vào candidate tầng {floor} cho {label}; "
            "business action vẫn phải tự xác minh đúng target"
        )

    def from_floor_to_floor(
        self,
        source_floor: int,
        target_floor: int,
        label: str,
    ) -> None:
        """Move between two known floors without pretending the source is main.

        This is used after planting actions that deliberately leave the camera at
        a known floor. The target is still only a candidate until the next
        business action proves its own machine/product anchor.
        """
        source = int(source_floor)
        target = int(target_floor)
        self.context.ensure_running()
        self.context.invalidate_camera_main(
            f"recovery-floor-{source}-to-floor-{target}:{label}"
        )
        self.context.stage(f"auto-recovery-floor-{source}-to-floor-{target}")
        custom = self._between_floor_routes.get((source, target))
        if custom is not None:
            custom(label)
        elif (source, target) == (1, 3):
            self.auto.function_one_pass_three_navigation.floor_1_to_floor_3()
        else:
            raise ValueError(
                f"Chưa có route tầng {source} → tầng {target}; "
                "Function/Recipe phải inject between_floor_routes"
            )
        self.emit(
            RecoveryEvent(
                RecoveryEventKind.FLOOR_REENTERED,
                label=label,
                floor=target,
                details={"source_floor": source},
            )
        )
        self.context.log(
            f"AUTO recovery • candidate tầng {source} → tầng {target} cho {label}; "
            "target business action sẽ xác minh lại"
        )

    def recover_unknown_to_floor(
        self,
        floor: int,
        label: str,
        *,
        reason: str,
        max_passes: int | None = None,
    ) -> None:
        self.recover_unknown_to_main(
            label,
            reason=reason,
            max_passes=max_passes,
        )
        self.from_main_to_floor(floor, label)
