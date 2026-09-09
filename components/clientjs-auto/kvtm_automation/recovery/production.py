from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

from ..errors import InventoryFull, ScreenTimeout, WrongProductionMachine
from ..workflows.auto_builder.catalog import get_function_spec
from ..workflows.auto_vp_sale import AutoVpSaleWorkflow
from .events import RecoveryEvent, RecoveryEventKind
from .navigation import EventSink, NavigationRecovery

if TYPE_CHECKING:
    from ..automation import KVAutomation


_T = TypeVar("_T")


class ProductionRecovery:
    """Central policy for recoverable production events.

    Only explicit business/navigation signals are recovered here. Generic
    ``ScreenTimeout`` is intentionally not caught because a production gesture may
    already have produced a side effect and must not be replayed blindly.
    """

    WRONG_MACHINE_RECOVERY_LIMIT = 3

    def __init__(
        self,
        automation: KVAutomation,
        *,
        navigation: NavigationRecovery,
        emit: EventSink,
        function_id: str,
    ) -> None:
        self.auto = automation
        self.context = automation.context
        self.navigation = navigation
        self.emit = emit
        self.spec = get_function_spec(function_id)

    def run_production(
        self,
        *,
        floor: int,
        label: str,
        producer: Callable[[], _T],
    ) -> _T:
        warehouse_recovery_round = 0
        wrong_machine_recovery_round = 0

        while True:
            self.context.ensure_running()
            try:
                return producer()

            except WrongProductionMachine as exc:
                wrong_machine_recovery_round += 1
                self.emit(
                    RecoveryEvent(
                        RecoveryEventKind.WRONG_PRODUCTION_MACHINE,
                        label=label,
                        floor=int(floor),
                        attempt=wrong_machine_recovery_round,
                        error=str(exc),
                    )
                )
                if wrong_machine_recovery_round > self.WRONG_MACHINE_RECOVERY_LIMIT:
                    self.emit(
                        RecoveryEvent(
                            RecoveryEventKind.RECOVERY_EXHAUSTED,
                            label=label,
                            floor=int(floor),
                            attempt=wrong_machine_recovery_round,
                            error=str(exc),
                            details={"kind": "wrong_machine"},
                        )
                    )
                    raise ScreenTimeout(
                        f"{label}: mở sai máy quá {self.WRONG_MACHINE_RECOVERY_LIMIT} lần; "
                        "dừng để tránh lặp điều hướng vô hạn"
                    ) from exc

                self.context.stage("auto-production-wrong-machine-recovery")
                self.context.log(
                    f"AUTO {label} • sai máy/sai tầng • recovery="
                    f"{wrong_machine_recovery_round}/{self.WRONG_MACHINE_RECOVERY_LIMIT} • "
                    f"{exc} • về exact-main rồi lên lại đúng tầng {floor}"
                )
                self.navigation.recover_unknown_to_floor(
                    int(floor),
                    label,
                    reason=f"wrong-production-machine:{label}",
                )

            except InventoryFull as exc:
                warehouse_recovery_round += 1
                self.emit(
                    RecoveryEvent(
                        RecoveryEventKind.INVENTORY_FULL,
                        label=label,
                        floor=int(floor),
                        attempt=warehouse_recovery_round,
                        error=str(exc),
                    )
                )
                self.context.stage("auto-production-warehouse-full-recovery")
                self.context.log(
                    f"AUTO kho đầy • {label} • lần recovery={warehouse_recovery_round} • {exc} • "
                    "xuống quầy bán VP theo Function"
                )

                self.navigation.to_main_from_floor(int(floor), label)
                sale = AutoVpSaleWorkflow(
                    self.auto,
                    function_id=self.spec.function_id,
                    allowed_item_ids=self.spec.sale_item_ids,
                ).run(timeout=120.0)

                if int(sale.sold_listings) <= 0:
                    raise ScreenTimeout(
                        f"Kho đầy khi thu {label} nhưng quầy không treo được VP nào "
                        f"thuộc {self.spec.label}; dừng để tránh lặp vô hạn"
                    ) from exc

                self.context.log(
                    f"AUTO kho đầy • bán VP recovery PASS • {label} • "
                    f"treo={sale.sold_listings} ô • thu_vàng={sale.collected_gold_slots}"
                )
                self.navigation.ensure_main(f"{label}: sau bán VP recovery")
                self.navigation.from_main_to_floor(int(floor), label)
