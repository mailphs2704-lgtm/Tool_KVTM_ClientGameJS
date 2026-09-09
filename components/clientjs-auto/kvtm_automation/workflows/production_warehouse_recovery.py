from __future__ import annotations

from typing import Callable, TypeVar

from ..automation import KVAutomation
from ..errors import InventoryFull, ScreenTimeout, WrongProductionMachine
from .auto_builder.catalog import get_function_spec
from .auto_vp_sale import AutoVpSaleWorkflow


__all__ = ["ProductionWarehouseRecovery"]
FILE_FUNCTIONS = (
    "Bắt riêng InventoryFull từ production và không nuốt các lỗi ScreenTimeout khác",
    "Bắt WrongProductionMachine khi panel mở đúng kiểu nhưng VP thuộc máy/tầng khác",
    "Sai máy: đóng panel, recovery camera không rõ tầng về exact-main rồi lên lại tầng đích",
    "Từ tầng sản xuất đã biết đưa Client về exact main trước khi mở quầy",
    "Bán đúng VP thuộc Function hiện tại bằng AutoVpSaleWorkflow đã có",
    "Nếu không bán được ô VP nào thì fail-close để tránh vòng recovery vô hạn",
    "Sau recovery xác nhận main rồi quay lại đúng tầng 1/2/3 và retry đúng production",
    "Mọi nhánh đều giữ stop-check của worker",
)

_T = TypeVar("_T")


class ProductionWarehouseRecovery:
    """Recover full warehouse or wrong production floor without restarting Function."""

    WRONG_MACHINE_RECOVERY_LIMIT = 3
    UNKNOWN_FLOOR_MAIN_RECOVERY_PASSES = 6

    def __init__(self, automation: KVAutomation, *, function_id: str = "function_1") -> None:
        self.auto = automation
        self.context = automation.context
        self.spec = get_function_spec(function_id)

    def _require_main(self, label: str) -> None:
        self.context.ensure_running()
        if not self.auto.popup.is_own_exact_main_screen():
            raise ScreenTimeout(
                f"Recovery production: {label} chưa xác nhận exact-main; "
                "dừng trước khi bán/quay lại máy"
            )
        self.context.log(f"AUTO recovery SX • {label} • exact main PASS")

    def _to_main(self, floor: int, label: str) -> None:
        self.context.stage(f"auto-warehouse-full-floor-{floor}-to-main")
        if floor == 1:
            self.auto.function_one_navigation.floor_1_to_main()
        elif floor == 2:
            self.auto.function_one_pass_three_navigation.floor_2_to_main()
        elif floor == 3:
            self.auto.function_one_pass_three_navigation.floor_3_to_main_via_down_floor()
        else:
            raise ValueError(f"Recovery kho đầy chưa hỗ trợ tầng {floor}")
        self._require_main(f"{label}: tầng {floor} → main")

    def _unknown_floor_to_main(self, label: str) -> None:
        """Normalize a wrong-machine camera without trusting the intended floor."""
        self.context.stage("auto-production-wrong-machine-to-main")
        self.context.invalidate_camera_main(f"wrong-production-machine:{label}")
        for attempt in range(1, self.UNKNOWN_FLOOR_MAIN_RECOVERY_PASSES + 1):
            self.context.ensure_running()
            if self.auto.popup.is_own_exact_main_screen():
                break
            self.auto.function_one_pass_three_navigation.go_down_one_toward_main(
                f"wrong-machine-{label}-{attempt}-of-"
                f"{self.UNKNOWN_FLOOR_MAIN_RECOVERY_PASSES}"
            )
            if self.auto.popup.is_own_exact_main_screen():
                break
        else:
            raise ScreenTimeout(
                f"Sai máy {label}: không chứng minh được exact-main sau "
                f"{self.UNKNOWN_FLOOR_MAIN_RECOVERY_PASSES} lượt recovery"
            )
        self._require_main(f"{label}: sai máy → main")

    def _back_to_floor(self, floor: int, label: str) -> None:
        self.context.stage(f"auto-production-recovery-main-to-floor-{floor}")
        if floor == 1:
            self.auto.function_one_navigation.main_to_floor_1()
        elif floor == 2:
            self.auto.function_one_navigation.main_to_floor_2()
        elif floor == 3:
            self.auto.function_one_navigation.main_to_floor_1()
            self.auto.function_one_pass_three_navigation.floor_1_to_floor_3()
        else:
            raise ValueError(f"Recovery production chưa hỗ trợ tầng {floor}")
        self.context.log(
            f"AUTO recovery SX • đã quay lại candidate tầng {floor} cho {label} • "
            "production sẽ xác minh đúng VP trước khi thao tác"
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
        while True:
            self.context.ensure_running()
            try:
                return producer()
            except WrongProductionMachine as exc:
                wrong_machine_recovery_round += 1
                if wrong_machine_recovery_round > self.WRONG_MACHINE_RECOVERY_LIMIT:
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
                self._unknown_floor_to_main(label)
                self._back_to_floor(floor, label)

            except InventoryFull as exc:
                warehouse_recovery_round += 1
                self.context.stage("auto-production-warehouse-full-recovery")
                self.context.log(
                    f"AUTO kho đầy • {label} • lần recovery={warehouse_recovery_round} • {exc} • "
                    "xuống quầy bán VP theo Function"
                )

                self._to_main(floor, label)
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
                self._require_main(f"{label}: sau bán VP recovery")
                self._back_to_floor(floor, label)
