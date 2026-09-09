from __future__ import annotations

from typing import Callable, TypeVar

from ..automation import KVAutomation
from ..recovery import RecoveryManager


__all__ = ["ProductionWarehouseRecovery"]
FILE_FUNCTIONS = (
    "Compatibility facade cho workflow cũ; policy thật nằm trong recovery/",
    "Sai máy/sai tầng do ProductionRecovery xử lý qua exact-main recovery",
    "Kho đầy do ProductionRecovery xử lý qua sale rồi quay lại đúng tầng",
    "Không chứa business recovery loop riêng để Function không phải copy logic lỗi",
)

_T = TypeVar("_T")


class ProductionWarehouseRecovery:
    """Backward-compatible facade over the standardized RecoveryManager.

    Existing workflows may keep importing this class while new Functions/Recipes
    should depend on ``RecoveryManager`` directly. No recovery policy lives here.
    """

    WRONG_MACHINE_RECOVERY_LIMIT = 3
    UNKNOWN_FLOOR_MAIN_RECOVERY_PASSES = 6

    def __init__(self, automation: KVAutomation, *, function_id: str = "function_1") -> None:
        self.auto = automation
        self.context = automation.context
        self.manager = RecoveryManager(
            automation,
            function_id=function_id,
        )
        self.spec = self.manager.spec

    def _require_main(self, label: str) -> None:
        # Keep the compatibility predicate visible for older main-boundary tooling;
        # authoritative validation is delegated to NavigationRecovery.ensure_main.
        if self.auto.popup.is_own_exact_main_screen():
            return
        self.manager.ensure_main(label)

    def _to_main(self, floor: int, label: str) -> None:
        self.manager.to_main_from_floor(floor, label)

    def _unknown_floor_to_main(self, label: str) -> None:
        self.manager.recover_unknown_to_main(
            label,
            reason=f"legacy-production-recovery:{label}",
            max_passes=self.UNKNOWN_FLOOR_MAIN_RECOVERY_PASSES,
        )

    def _back_to_floor(self, floor: int, label: str) -> None:
        self.manager.from_main_to_floor(floor, label)

    def run_production(
        self,
        *,
        floor: int,
        label: str,
        producer: Callable[[], _T],
    ) -> _T:
        return self.manager.run_production(
            floor=floor,
            label=label,
            producer=producer,
        )
