from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from ..errors import ScreenTimeout
from ..material_shortage import MaterialShortage
from .events import RecoveryEvent, RecoveryEventKind
from .manager import RecoveryManager as BaseRecoveryManager
from .production import ProductionRecovery as BaseProductionRecovery


_T = TypeVar("_T")

__all__ = [
    "MaterialAwareProductionRecovery",
    "MaterialAwareRecoveryManager",
]

FILE_FUNCTIONS = (
    "Bắt MaterialShortage ở lớp recovery thay vì để ScreenTimeout dừng Function",
    "Về exact-main rồi bổ sung đúng loại cây theo material_template",
    "Táo: main→tầng1, chờ chín, cào+gieo lại 5 tầng theo routine hiện có, lặp 3 lượt",
    "Bông: main→tầng1, chờ đủ một batch chín, thu 27 rồi gieo lại cay_bong",
    "Sau bổ sung normalize lại exact-main, quay đúng tầng máy và gọi lại producer",
    "Producer giữ progress nên chỉ sản xuất phần còn thiếu, không replay sản phẩm đã xếp",
)


class MaterialAwareProductionRecovery(BaseProductionRecovery):
    """Adds crop replenishment to the existing wrong-machine/full-warehouse policy."""

    MATERIAL_RECOVERY_LIMIT = 3
    APPLE_FIVE_FLOOR_ROUNDS = 3
    MATERIAL_MAIN_RECOVERY_PASSES = 8

    def _emit_material_event(
        self,
        *,
        label: str,
        floor: int,
        attempt: int,
        exc: MaterialShortage,
    ) -> None:
        self.emit(
            RecoveryEvent(
                RecoveryEventKind.MATERIAL_SHORTAGE,
                label=label,
                floor=int(floor),
                attempt=int(attempt),
                error=str(exc),
                details={
                    "material_template": exc.material_template,
                    "material_label": exc.material_label,
                    "production_item_id": exc.production_item_id,
                    "completed_count": exc.completed_count,
                    "target_count": exc.target_count,
                    "remaining_count": exc.remaining_count,
                    "shortage_kind": exc.evidence.shortage_kind,
                    "drag_consumed_slot": exc.evidence.drag_consumed_slot,
                },
            )
        )

    def _normalize_to_main_from_material_floor(self, label: str, reason: str) -> None:
        self.navigation.recover_unknown_to_main(
            label,
            reason=reason,
            max_passes=self.MATERIAL_MAIN_RECOVERY_PASSES,
        )

    def _replenish_apples(self, *, label: str, recovery_round: int) -> int:
        """Harvest/replant the existing five-floor apple route three times."""
        total = 0

        # The shortage handler entered here at proven exact-main.
        self.navigation.from_main_to_floor(
            1,
            f"{label}: bổ sung Táo vòng {recovery_round}",
        )

        for harvest_round in range(1, self.APPLE_FIVE_FLOOR_ROUNDS + 1):
            self.context.ensure_running()
            self.context.stage(
                f"auto-material-apple-harvest-{harvest_round}-of-"
                f"{self.APPLE_FIVE_FLOOR_ROUNDS}"
            )
            self.context.log(
                f"AUTO bổ sung Táo • lượt {harvest_round}/"
                f"{self.APPLE_FIVE_FLOOR_ROUNDS} • chờ tầng 1 chín trước khi cào"
            )
            self.auto.apple_supply.wait_until_floor_1_ripe()
            harvested = int(
                self.auto.apple_supply.harvest_and_replant_five_floors()
            )
            total += harvested
            self.context.log(
                f"AUTO bổ sung Táo • cào+gieo lại 5 tầng PASS • "
                f"lượt={harvest_round}/{self.APPLE_FIVE_FLOOR_ROUNDS} • "
                f"routine_count={harvested} • tổng routine_count={total}"
            )

            # Crop-path gestures can leave the camera at an unknown vertical
            # position. Before a second/third harvest, re-prove exact-main and
            # enter floor 1 again instead of assuming camera state.
            if harvest_round < self.APPLE_FIVE_FLOOR_ROUNDS:
                self._normalize_to_main_from_material_floor(
                    f"{label}: giữa các lượt bổ sung Táo",
                    reason=(
                        f"material-shortage-apple-between-rounds-"
                        f"{recovery_round}-{harvest_round}"
                    ),
                )
                self.navigation.from_main_to_floor(
                    1,
                    f"{label}: bổ sung Táo lượt {harvest_round + 1}",
                )

        self._normalize_to_main_from_material_floor(
            f"{label}: sau bổ sung Táo",
            reason=f"material-shortage-apple-finished-{recovery_round}",
        )
        return total

    def _replenish_cotton(self, *, label: str, recovery_round: int) -> int:
        self.navigation.from_main_to_floor(
            1,
            f"{label}: bổ sung Bông vòng {recovery_round}",
        )
        harvested = int(
            self.auto.cotton_planting.replenish_27_cotton_from_floor_1()
        )
        self.context.log(
            f"AUTO bổ sung Bông • đã thu và gieo lại cay_bong • "
            f"routine_count={harvested}"
        )
        self._normalize_to_main_from_material_floor(
            f"{label}: sau bổ sung Bông",
            reason=f"material-shortage-cotton-finished-{recovery_round}",
        )
        return harvested

    def _replenish_material(
        self,
        *,
        label: str,
        exc: MaterialShortage,
        recovery_round: int,
    ) -> int:
        material = str(exc.material_template).strip().lower()
        if material == "cay_tao":
            return self._replenish_apples(
                label=label,
                recovery_round=recovery_round,
            )
        if material == "cay_bong":
            return self._replenish_cotton(
                label=label,
                recovery_round=recovery_round,
            )
        raise ScreenTimeout(
            f"{label}: đã bắt lỗi thiếu cây nhưng chưa có replenisher cho "
            f"material_template={exc.material_template!r}; dừng fail-close"
        )

    def run_production(
        self,
        *,
        floor: int,
        label: str,
        producer: Callable[[], _T],
    ) -> _T:
        material_recovery_round = 0

        while True:
            self.context.ensure_running()
            try:
                # Keep the already-proven WrongProductionMachine/InventoryFull
                # policy intact. MaterialShortage is not caught by the base class
                # and therefore reaches this outer recovery boundary.
                return super().run_production(
                    floor=int(floor),
                    label=label,
                    producer=producer,
                )

            except MaterialShortage as exc:
                material_recovery_round += 1
                self._emit_material_event(
                    label=label,
                    floor=int(floor),
                    attempt=material_recovery_round,
                    exc=exc,
                )
                if material_recovery_round > self.MATERIAL_RECOVERY_LIMIT:
                    self.emit(
                        RecoveryEvent(
                            RecoveryEventKind.RECOVERY_EXHAUSTED,
                            label=label,
                            floor=int(floor),
                            attempt=material_recovery_round,
                            error=str(exc),
                            details={
                                "kind": "material_shortage",
                                "material_template": exc.material_template,
                            },
                        )
                    )
                    raise ScreenTimeout(
                        f"{label}: thiếu {exc.material_label} lặp quá "
                        f"{self.MATERIAL_RECOVERY_LIMIT} lần; dừng tránh vòng lặp"
                    ) from exc

                self.context.stage("auto-production-material-shortage-recovery")
                self.context.log(
                    f"AUTO {label} • MATERIAL RECOVERY "
                    f"{material_recovery_round}/{self.MATERIAL_RECOVERY_LIMIT} • "
                    f"cây={exc.material_label} ({exc.material_template}) • "
                    f"đã_xếp={exc.completed_count}/{exc.target_count} • "
                    f"còn={exc.remaining_count} • về Main → bổ sung đúng cây"
                )

                # The production action already closed the shortage popup and
                # production panel, so the camera is still on the known machine
                # floor and can take the deterministic floor->main route.
                self.navigation.to_main_from_floor(
                    int(floor),
                    f"{label}: thiếu {exc.material_label}",
                )

                supplied = self._replenish_material(
                    label=label,
                    exc=exc,
                    recovery_round=material_recovery_round,
                )
                self.context.log(
                    f"AUTO {label} • bổ sung {exc.material_label} PASS • "
                    f"routine_count={supplied} • exact-main READY • "
                    f"quay lại tầng {floor}"
                )

                self.navigation.from_main_to_floor(
                    int(floor),
                    f"{label}: resume sau bổ sung {exc.material_label}",
                )
                self.context.stage("auto-production-material-shortage-resume")
                self.context.log(
                    f"AUTO {label} • RESUME máy SX • "
                    f"giữ progress={exc.completed_count}/{exc.target_count} • "
                    f"chỉ xếp tiếp còn={exc.remaining_count}"
                )


class MaterialAwareRecoveryManager(BaseRecoveryManager):
    """Recovery facade whose production policy understands MaterialShortage."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.production = MaterialAwareProductionRecovery(
            self.auto,
            navigation=self.navigation,
            emit=self._emit,
            function_id=self.function_id,
        )
        self.spec = self.production.spec
