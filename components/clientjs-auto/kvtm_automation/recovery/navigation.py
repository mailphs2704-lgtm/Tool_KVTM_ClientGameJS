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

    Default routes cover proven common floors through the generic farm-route
    facade. Recipes may register additional deterministic routes (for example
    floor 5 TDHH) on the same manager rather than creating a second
    RecoveryManager and splitting checkpoint/event state.
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

    def register_routes(
        self,
        *,
        to_main_routes: Mapping[int, RouteHandler] | None = None,
        from_main_routes: Mapping[int, RouteHandler] | None = None,
        between_floor_routes: Mapping[tuple[int, int], RouteHandler] | None = None,
    ) -> None:
        """Register verified deterministic routes on this live shared manager."""
        self._to_main_routes.update(dict(to_main_routes or {}))
        self._from_main_routes.update(dict(from_main_routes or {}))
        self._between_floor_routes.update(dict(between_floor_routes or {}))
        self.context.detail(
            "AUTO recovery routes | register | "
            f"to_main={sorted(self._to_main_routes)} | "
            f"from_main={sorted(self._from_main_routes)} | "
            f"between={sorted(self._between_floor_routes)}"
        )

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
            self.auto.farm_boundary_routes.go_down_one_toward_main(
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
            self.auto.farm_routes.floor_1_to_main()
        elif floor == 2:
            self.auto.farm_boundary_routes.floor_2_to_main()
        elif floor == 3:
            # Recovery is a global runtime path, not Function 1 end-of-loop.
            # Use the generic deterministic floor->main route so any error/log
            # keeps the real module label (e.g. Vải vàng inventory recovery).
            self.auto.farm_boundary_routes.known_upper_floor_to_main_via_down_floor(
                f"recovery-{label}-floor3"
            )
        else:
            raise ValueError(
                f"Chưa có route tầng {floor} → main; Recipe phải register route đã xác minh"
            )
        self.ensure_main(f"{label}: tầng {floor} → main")

    def from_main_to_floor(self, floor: int, label: str) -> None:
        """Enter a requested floor from proven main using a default or registered route."""
        floor = int(floor)
        self.ensure_main(f"{label}: trước main → tầng {floor}")
        self.context.invalidate_camera_main(f"recovery-main-to-floor-{floor}:{label}")
        self.context.stage(f"auto-recovery-main-to-floor-{floor}")
        custom = self._from_main_routes.get(floor)
        if custom is not None:
            custom(label)
        elif floor == 1:
            self.auto.farm_routes.main_to_floor_1()
        elif floor == 2:
            self.auto.farm_routes.main_to_floor_2()
        elif floor == 3:
            self.auto.farm_routes.main_to_floor_1()
            self.auto.farm_boundary_routes.floor_1_to_floor_3()
        else:
            raise ValueError(
                f"Chưa có route main → tầng {floor}; Recipe phải register route đã xác minh"
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
            self.auto.farm_boundary_routes.floor_1_to_floor_3()
        else:
            raise ValueError(
                f"Chưa có route tầng {source} → tầng {target}; "
                "Recipe phải register route đã xác minh"
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
