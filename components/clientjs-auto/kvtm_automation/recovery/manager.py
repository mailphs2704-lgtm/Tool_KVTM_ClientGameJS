from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, TypeVar

from .events import RecoveryEvent, RecoveryEventKind
from .module_execution import ModuleErrorHandler, ModuleRecoveryExecutor
from .navigation import NavigationRecovery, RouteHandler
from .production import ProductionRecovery
from .cycle_checkpoint import CycleCheckpoint

if TYPE_CHECKING:
    from ..automation import KVAutomation


_T = TypeVar("_T")
RecoveryEventHandler = Callable[[RecoveryEvent], None]


class RecoveryManager:
    """One recovery facade shared by all Recipes in a Function.

    Recipes may register additional verified navigation routes on this same
    manager. They must not create a second manager merely because a later Recipe
    uses another floor; one manager keeps event/checkpoint ownership coherent.

    Navigation recovery is intentionally independent from production metadata.
    ProductionRecovery is created lazily only when production policy/spec is
    actually requested. This lets lifecycle re-entry normalize an unknown camera
    without inventing an AUTO Builder Function merely to use navigation recovery.
    """

    def __init__(
        self,
        automation: KVAutomation,
        *,
        function_id: str,
        event_handlers: Mapping[
            RecoveryEventKind | str, RecoveryEventHandler
        ] | None = None,
        to_main_routes: Mapping[int, RouteHandler] | None = None,
        from_main_routes: Mapping[int, RouteHandler] | None = None,
        between_floor_routes: Mapping[tuple[int, int], RouteHandler] | None = None,
    ) -> None:
        self.auto = automation
        self.context = automation.context
        self.function_id = str(function_id)
        self._event_handlers: dict[str, RecoveryEventHandler] = {}
        for key, handler in dict(event_handlers or {}).items():
            normalized = key.value if isinstance(key, RecoveryEventKind) else str(key)
            self._event_handlers[normalized] = handler

        self.navigation = NavigationRecovery(
            automation,
            emit=self._emit,
            to_main_routes=to_main_routes,
            from_main_routes=from_main_routes,
            between_floor_routes=between_floor_routes,
        )
        self.cycle = CycleCheckpoint(
            self.context,
            function_id=self.function_id,
        )
        self._production: ProductionRecovery | None = None

    def commit_cycle(self) -> None:
        """Release side-effect locks only after the caller completion gate."""
        self.cycle.commit_cycle()

    @property
    def production(self) -> ProductionRecovery:
        """Create product/catalog recovery policy only when production needs it."""
        if self._production is None:
            self._production = ProductionRecovery(
                self.auto,
                navigation=self.navigation,
                emit=self._emit,
                function_id=self.function_id,
            )
        return self._production

    @property
    def spec(self):
        """Compatibility facade for callers that need the Function product spec."""
        return self.production.spec

    def _emit(self, event: RecoveryEvent) -> None:
        self.context.detail(
            "AUTO recovery event | "
            f"kind={event.kind.value} | label={event.label} | "
            f"floor={event.floor} | attempt={event.attempt} | error={event.error}"
        )
        handler = self._event_handlers.get(event.kind.value)
        if handler is None:
            handler = self._event_handlers.get("*")
        if handler is None:
            return
        try:
            handler(event)
        except Exception as exc:
            self.context.log(
                "AUTO recovery hook • bỏ qua lỗi hook non-blocking • "
                f"event={event.kind.value} • {exc!r}"
            )

    def register_navigation_routes(
        self,
        *,
        to_main_routes: Mapping[int, RouteHandler] | None = None,
        from_main_routes: Mapping[int, RouteHandler] | None = None,
        between_floor_routes: Mapping[tuple[int, int], RouteHandler] | None = None,
    ) -> None:
        self.navigation.register_routes(
            to_main_routes=to_main_routes,
            from_main_routes=from_main_routes,
            between_floor_routes=between_floor_routes,
        )

    def ensure_main(self, label: str) -> None:
        self.navigation.ensure_main(label)

    def recover_unknown_to_main(
        self,
        label: str,
        *,
        reason: str,
        max_passes: int | None = None,
    ) -> None:
        self.navigation.recover_unknown_to_main(
            label,
            reason=reason,
            max_passes=max_passes,
        )

    def recover_unknown_to_floor(
        self,
        floor: int,
        label: str,
        *,
        reason: str,
        max_passes: int | None = None,
    ) -> None:
        self.navigation.recover_unknown_to_floor(
            floor,
            label,
            reason=reason,
            max_passes=max_passes,
        )

    def to_main_from_floor(self, floor: int, label: str) -> None:
        self.navigation.to_main_from_floor(floor, label)

    def from_main_to_floor(self, floor: int, label: str) -> None:
        self.navigation.from_main_to_floor(floor, label)

    def from_floor_to_floor(
        self,
        source_floor: int,
        target_floor: int,
        label: str,
    ) -> None:
        self.navigation.from_floor_to_floor(source_floor, target_floor, label)

    def run_module(
        self,
        *,
        module_id: str,
        label: str,
        runner: Callable[[], _T],
        floor: int | None = None,
        handlers: Sequence[tuple[type[Exception], ModuleErrorHandler]] = (),
    ) -> _T:
        """Execute a module behind one checkpoint until it succeeds/fails closed."""
        executor = ModuleRecoveryExecutor(
            self.auto,
            function_id=self.function_id,
            emit=self._emit,
        )
        return executor.run(
            module_id=module_id,
            label=label,
            floor=floor,
            runner=runner,
            handlers=handlers,
        )

    def run_production(
        self,
        *,
        floor: int,
        label: str,
        producer: Callable[[], _T],
    ) -> _T:
        return self.production.run_production(
            floor=floor,
            label=label,
            producer=producer,
        )
