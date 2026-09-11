from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

from ..errors import InventoryFull, ScreenTimeout, WrongProductionMachine
from ..workflows.auto_builder.catalog import get_function_spec
from ..workflows.auto_vp_sale import AutoVpSaleWorkflow
from .events import RecoveryEvent, RecoveryEventKind
from .module_execution import ModuleCheckpoint, ModuleRecoveryExecutor
from .navigation import EventSink, NavigationRecovery

if TYPE_CHECKING:
    from ..automation import KVAutomation


_T = TypeVar("_T")


class ProductionRecovery:
    """Central policy for recoverable production events.

    Production is executed as one checkpointed module. InventoryFull and
    WrongProductionMachine may temporarily move away from the production floor,
    but the executor does not return to the Function/scheduler until this same
    module succeeds. Generic ScreenTimeout is intentionally not registered as a
    recoverable signal because production gestures can have side effects.
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
        self.function_id = str(function_id)
        self.spec = get_function_spec(function_id)
        self.executor = ModuleRecoveryExecutor(
            automation,
            function_id=self.function_id,
            emit=emit,
        )

    def run_production(
        self,
        *,
        floor: int,
        label: str,
        producer: Callable[[], _T],
    ) -> _T:
        warehouse_recovery_round = 0
        wrong_machine_recovery_round = 0
        work_floor = int(floor)

        def recover_wrong_machine(
            checkpoint: ModuleCheckpoint,
            error: Exception,
        ) -> None:
            nonlocal wrong_machine_recovery_round
            exc = error
            if not isinstance(exc, WrongProductionMachine):
                raise TypeError("wrong-machine handler received unexpected error")

            wrong_machine_recovery_round += 1
            self.emit(
                RecoveryEvent(
                    RecoveryEventKind.WRONG_PRODUCTION_MACHINE,
                    label=label,
                    floor=work_floor,
                    attempt=wrong_machine_recovery_round,
                    error=str(exc),
                    details={
                        "module_id": checkpoint.module_id,
                        "checkpoint": checkpoint.key,
                    },
                )
            )
            if wrong_machine_recovery_round > self.WRONG_MACHINE_RECOVERY_LIMIT:
                self.emit(
                    RecoveryEvent(
                        RecoveryEventKind.RECOVERY_EXHAUSTED,
                        label=label,
                        floor=work_floor,
                        attempt=wrong_machine_recovery_round,
                        error=str(exc),
                        details={
                            "kind": "wrong_machine",
                            "module_id": checkpoint.module_id,
                            "checkpoint": checkpoint.key,
                        },
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
                f"{exc} • checkpoint={checkpoint.key} • "
                f"về exact-main rồi lên lại đúng tầng {work_floor}"
            )
            self.navigation.recover_unknown_to_floor(
                work_floor,
                label,
                reason=f"wrong-production-machine:{label}",
            )

        def recover_inventory_full(
            checkpoint: ModuleCheckpoint,
            error: Exception,
        ) -> None:
            nonlocal warehouse_recovery_round
            exc = error
            if not isinstance(exc, InventoryFull):
                raise TypeError("inventory-full handler received unexpected error")

            warehouse_recovery_round += 1
            self.emit(
                RecoveryEvent(
                    RecoveryEventKind.INVENTORY_FULL,
                    label=label,
                    floor=work_floor,
                    attempt=warehouse_recovery_round,
                    error=str(exc),
                    details={
                        "module_id": checkpoint.module_id,
                        "checkpoint": checkpoint.key,
                    },
                )
            )
            self.context.stage("auto-production-warehouse-full-recovery")
            self.context.log(
                f"AUTO kho đầy • {label} • recovery={warehouse_recovery_round} • "
                f"checkpoint={checkpoint.key} • {exc} • "
                "tạm rời module xuống quầy; KHÔNG kết thúc Function loop"
            )

            self.navigation.to_main_from_floor(work_floor, label)
            sale = AutoVpSaleWorkflow(
                self.auto,
                function_id=self.spec.function_id,
                allowed_item_ids=self.spec.sale_item_ids,
            ).run(timeout=120.0)

            sold = int(sale.sold_listings)
            collected = int(sale.collected_gold_slots)
            if sold <= 0 and collected <= 0:
                raise ScreenTimeout(
                    f"Kho đầy khi thu {label} nhưng lượt bán recovery không tạo tiến triển "
                    f"(treo={sold}, thu_vàng={collected}); dừng để tránh lặp vô hạn"
                ) from exc

            self.context.log(
                f"AUTO kho đầy • bán VP recovery có tiến triển • {label} • "
                f"treo={sold} ô • thu_vàng={collected} • "
                f"checkpoint={checkpoint.key} • quay lại đúng tầng {work_floor}"
            )
            self.navigation.ensure_main(f"{label}: sau bán VP recovery")
            self.navigation.from_main_to_floor(work_floor, label)

        return self.executor.run(
            module_id=f"production:{work_floor}:{label}",
            label=label,
            floor=work_floor,
            runner=producer,
            handlers=(
                (WrongProductionMachine, recover_wrong_machine),
                (InventoryFull, recover_inventory_full),
            ),
        )
