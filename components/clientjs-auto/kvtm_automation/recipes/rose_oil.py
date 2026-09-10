from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..actions.function_two_planting import (
    FunctionTwoPlantingActions,
    FunctionTwoPlantingResult,
)
from ..actions.production import ProductionResult
from ..actions.rose_oil_production import RoseOilProductionActions
from ..recovery import RecoveryManager

if TYPE_CHECKING:
    from ..automation import KVAutomation


__all__ = ["RoseOilRecipe", "RoseOilRecipeResult"]


@dataclass(frozen=True)
class RoseOilRecipeResult:
    materials: FunctionTwoPlantingResult
    production: ProductionResult

    @property
    def rose_planted(self) -> int:
        return int(self.materials.roses_planted)

    @property
    def snow_planted(self) -> int:
        return int(self.materials.snow_planted)

    @property
    def queued_count(self) -> int:
        return int(self.production.queued_count)


class RoseOilRecipe:
    """Function 2 recipe: 35 Hồng + 28 Tuyết -> floor 5 -> 7 TDHH."""

    REQUIRED_COUNT = 7
    ROSE_REQUIRED = 35
    SNOW_REQUIRED = 28

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context
        self.planting = FunctionTwoPlantingActions(
            automation.context,
            automation.vision,
            automation.wait,
            automation.speed_config,
            floors=automation.floors,
        )
        self.production = RoseOilProductionActions(
            automation.context,
            automation.vision,
            automation.wait,
            automation.speed_config,
        )
        self.recovery = RecoveryManager(
            automation,
            function_id="function_2",
            to_main_routes={5: self._floor_5_to_main},
            from_main_routes={5: self._main_to_floor_5},
            between_floor_routes={(7, 5): self._floor_7_to_floor_5},
        )

    def _require_count(self, count: int) -> None:
        if int(count) != self.REQUIRED_COUNT:
            raise ValueError(
                f"TDHH recipe hiện khóa đúng {self.REQUIRED_COUNT} sản phẩm; "
                f"requested={count}"
            )

    def _floor_7_to_floor_5(self, label: str) -> None:
        self.context.log(
            f"AUTO TDHH route • {label} • candidate tầng 7 → candidate tầng 5"
        )
        self.auto.floors.down(2)

    def _main_to_floor_5(self, label: str) -> None:
        # Reuse the recovered AUTO PRO main->6 sequence, then one proven DOWN.
        self.context.log(
            f"AUTO TDHH recovery route • {label} • main → target6 → down1 → candidate5"
        )
        self.auto.floors.reference_main_to_floor_6()
        self.auto.floors.down(1)

    def _floor_5_to_main(self, label: str) -> None:
        # Machine repair closes only its own modal; the production panel remains
        # open. Close that panel first, then move the known floor-5 camera down.
        self.context.log(
            f"AUTO TDHH recovery route • {label} • đóng panel → tầng 5 → main"
        )
        self.auto.vision.driver.click(*RoseOilProductionActions.CLOSE_POINT)
        self.auto.wait.sleep(0.35)
        self.auto.floors.down(5)

    def run_from_main(self, *, count: int = 7) -> RoseOilRecipeResult:
        self._require_count(count)
        self.recovery.ensure_main("TDHH recipe: entry main")
        self.context.stage("auto-recipe-rose-oil-materials")

        materials = self.planting.harvest_and_replant_materials()
        if (
            int(materials.roses_planted) != self.ROSE_REQUIRED
            or int(materials.snow_planted) != self.SNOW_REQUIRED
            or int(materials.end_floor) != 7
        ):
            raise RuntimeError(
                "TDHH material contract FAIL: "
                f"rose={materials.roses_planted}/{self.ROSE_REQUIRED}, "
                f"snow={materials.snow_planted}/{self.SNOW_REQUIRED}, "
                f"end_floor={materials.end_floor}/7"
            )

        self.context.ensure_running()
        self.recovery.from_floor_to_floor(7, 5, "TDHH recipe")
        self.context.stage("auto-recipe-rose-oil-production")
        produced = self.recovery.run_production(
            floor=5,
            label="Tinh dầu hoa hồng",
            producer=lambda: self.production.produce_7_rose_oils(
                close_after_success=False
            ),
        )
        self.context.ensure_running()
        self.auto.machine_repair.repair_after_production(produced)
        self.context.ensure_running()

        self.recovery.to_main_from_floor(5, "TDHH recipe: cuối production")
        self.context.stage("auto-recipe-rose-oil-pass")
        self.context.log(
            "AUTO recipe TDHH • PASS • 35 Hồng + 28 Tuyết + SX 7/7 + Sửa máy"
        )
        return RoseOilRecipeResult(
            materials=materials,
            production=produced,
        )
