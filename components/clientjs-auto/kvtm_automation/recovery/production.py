from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

from ..error_journal import record_auto_error
from ..errors import (
    FunctionRestartRequested,
    InventoryFull,
    ProductSearchExhausted,
    ScreenTimeout,
    WrongProductionMachine,
)
from ..workflows.auto_builder.catalog import get_function_spec
from ..workflows.auto_vp_sale import AutoVpSaleWorkflow
from .events import RecoveryEvent, RecoveryEventKind
from .module_execution import ModuleCheckpoint, ModuleRecoveryExecutor
from .navigation import EventSink, NavigationRecovery

if TYPE_CHECKING:
    from ..automation import KVAutomation


_T = TypeVar("_T")


class ProductionRecovery:
    """Central policy for recoverable production events."""

    WRONG_MACHINE_RECOVERY_LIMIT = 3
    CANONICAL_PRODUCTION_FLOORS = {
        "Táo sấy": 1,
        "Trà sấy": 1,
        "Nước táo": 2,
        "Vải vàng": 3,
        "Tinh dầu hoa hồng": 5,
        "Trà đá": 6,
        "Nước hoa hồng": 8,
    }

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
        if label not in self.CANONICAL_PRODUCTION_FLOORS:
            raise ValueError(f"Chưa khai báo tầng sản xuất chuẩn cho {label!r}")
        work_floor = self.CANONICAL_PRODUCTION_FLOORS[label]
        if int(floor) != work_floor:
            raise ValueError(
                f"Sai hợp đồng tầng sản xuất: {label} phải ở tầng {work_floor}, "
                f"caller truyền tầng {floor}"
            )
        self.context.log(
            f"AUTO {label} • floor contract VERIFIED • tầng chuẩn={work_floor} • "
            "mọi recovery sẽ exact-main → đúng tầng chuẩn"
        )

        def recover_wrong_machine(
            checkpoint: ModuleCheckpoint,
            error: Exception,
        ) -> None:
            nonlocal wrong_machine_recovery_round
            exc = error
            if not isinstance(exc, WrongProductionMachine):
                raise TypeError("wrong-machine handler received unexpected error")

            wrong_machine_recovery_round += 1
            record_auto_error(
                self.context,
                exc,
                phase=f"production:{label}:wrong-machine",
                recovery_state=(
                    f"policy sai máy đang xử lý lần {wrong_machine_recovery_round}"
                ),
            )
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
            if isinstance(exc, ProductSearchExhausted):
                self.context.action("Không tìm thấy VP sản xuất, chuyển trạng thái xử lí")
                self.context.stage("auto-production-product-search-recovery")
                self.context.log(
                    f"AUTO {label} • hết 2 vòng tìm VP • "
                    f"recovery={wrong_machine_recovery_round}/2 • ESC x3"
                )
                self.auto.popup.escape_three_then_stay(
                    label=f"{label}: product-search-{wrong_machine_recovery_round}"
                )
                if wrong_machine_recovery_round == 1:
                    self.navigation.recover_unknown_to_floor(
                        work_floor,
                        label,
                        reason=f"product-search-exhausted:{label}:retry-production",
                    )
                    return
                self.navigation.recover_unknown_to_main(
                    label,
                    reason=f"product-search-exhausted:{label}:restart-function",
                )
                raise FunctionRestartRequested(
                    f"{label}: không tìm thấy VP sau 2 lần vào lại đúng tầng"
                ) from exc

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

            self.context.action("Lỗi sai máy/sai tầng, chuyển trạng thái xử lí")
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
            record_auto_error(
                self.context,
                exc,
                phase=f"production:{label}:inventory-full",
                recovery_state=(
                    f"policy đầy kho đang xử lý lần {warehouse_recovery_round}"
                ),
            )
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
            self.context.action("Lỗi đầy kho, chuyển trạng thái xử lí")
            self.context.stage("auto-production-warehouse-full-recovery")
            self.context.log(
                f"AUTO kho đầy • {label} • recovery={warehouse_recovery_round} • "
                f"checkpoint={checkpoint.key} • {exc} • "
                "tạm rời module xuống quầy; KHÔNG kết thúc Function loop"
            )

            self.navigation.to_main_from_floor(work_floor, label)

            sale_wait_round = 0
            while True:
                self.context.ensure_running()
                sale_wait_round += 1
                sale = AutoVpSaleWorkflow(
                    self.auto,
                    function_id=self.spec.function_id,
                    allowed_item_ids=self.spec.sale_item_ids,
                ).run(timeout=120.0)

                sold = int(sale.sold_listings)
                collected = int(sale.collected_gold_slots)
                if sold > 0:
                    self.context.log(
                        f"AUTO kho đầy • bán VP recovery có chỗ thật • {label} • "
                        f"wait_round={sale_wait_round} • treo={sold} ô • "
                        f"thu_vàng={collected} • checkpoint={checkpoint.key} • "
                        f"quay lại đúng tầng {work_floor}"
                    )
                    break

                self.context.log(
                    f"AUTO kho đầy • chưa treo được VP x10 • {label} • "
                    f"wait_round={sale_wait_round} • treo={sold} • "
                    f"thu_vàng={collected} • giữ checkpoint tại MAIN • "
                    "tiếp tục quét 5 View + QC cho tới khi người mua tạo ô trống"
                )
                self.navigation.ensure_main(
                    f"{label}: chờ quầy có ô trống sau sale recovery"
                )
                self.auto.wait.sleep(1.0)

            self.navigation.ensure_main(f"{label}: sau bán VP recovery")
            self.navigation.from_main_to_floor(work_floor, label)
            self.context.action("Đã xử lí đầy kho, quay lại bước sản xuất")

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
