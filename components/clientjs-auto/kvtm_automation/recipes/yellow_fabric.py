from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..actions.production import ProductionResult
from ..recovery import RecoveryManager
from .apple_juice import AppleJuiceRecipe, AppleJuiceRecipeResult

if TYPE_CHECKING:
    from ..automation import KVAutomation


__all__ = ["YellowFabricRecipe", "YellowFabricRecipeResult"]


@dataclass(frozen=True)
class YellowFabricRecipeResult:
    cotton_planted: int
    production: ProductionResult
    apple_juice: AppleJuiceRecipeResult | None = None

    @property
    def queued_count(self) -> int:
        return int(self.production.queued_count)


class YellowFabricRecipe:
    """Reusable Vải vàng recipe with optional Nước táo dependency.

    ``run_from_main`` can be used independently by a future Function. When
    ``include_apple_juice_dependency=True`` it first runs the reusable Nước táo
    recipe, returns floor 2 -> exact-main, then continues Bông -> tầng 3 -> Vải
    vàng. Function 1 already produces Nước táo earlier, so it uses the dedicated
    ``run_after_floor_2`` entry to avoid duplicate production.
    """

    REQUIRED_COUNT = 9

    def __init__(
        self,
        automation: KVAutomation,
        *,
        recovery: RecoveryManager,
        apple_juice: AppleJuiceRecipe,
    ) -> None:
        self.auto = automation
        self.context = automation.context
        self.recovery = recovery
        self.apple_juice = apple_juice

    def _require_supported_count(self, count: int) -> None:
        if int(count) != self.REQUIRED_COUNT:
            raise ValueError(
                f"Vải vàng recipe hiện khóa đúng {self.REQUIRED_COUNT} sản phẩm; "
                f"requested={count}"
            )

    def _plant_cotton_and_produce(
        self,
        *,
        count: int,
        apple_juice_result: AppleJuiceRecipeResult | None = None,
    ) -> YellowFabricRecipeResult:
        self._require_supported_count(count)
        self.recovery.ensure_main("Vải vàng recipe: trước trồng Bông")
        self.context.stage("auto-recipe-yellow-fabric-cotton")
        cotton = self.auto.cotton_planting.plant_27_cotton()
        self.context.ensure_running()

        # Cotton planting enters from main using its proven goUp(1) and leaves the
        # camera at known floor 1. Never pretend that state is still exact-main.
        self.recovery.from_floor_to_floor(1, 3, "Vải vàng recipe")
        self.context.stage("auto-recipe-yellow-fabric-production")
        produced = self.recovery.run_production(
            floor=3,
            label="Vải vàng",
            producer=lambda: self.auto.yellow_fabric_production.produce_9_yellow_fabrics(
                close_after_success=False
            ),
        )
        self.context.ensure_running()
        self.auto.machine_repair.repair_after_production(produced)
        self.context.ensure_running()
        self.context.stage("auto-recipe-yellow-fabric-pass")
        self.context.log(
            "AUTO recipe Vải vàng • PASS • trồng 27 Bông + SX 9/9 + Sửa máy"
        )
        return YellowFabricRecipeResult(
            cotton_planted=int(cotton),
            production=produced,
            apple_juice=apple_juice_result,
        )

    def run_from_main(
        self,
        *,
        count: int = 9,
        include_apple_juice_dependency: bool = False,
    ) -> YellowFabricRecipeResult:
        """Run Vải vàng from exact-main, optionally producing Nước táo first."""
        self._require_supported_count(count)
        self.recovery.ensure_main("Vải vàng recipe: entry main")
        juice_result: AppleJuiceRecipeResult | None = None

        if include_apple_juice_dependency:
            self.context.log(
                "AUTO recipe Vải vàng • gọi dependency Nước táo trước Bông"
            )
            juice_result = self.apple_juice.run_from_main(count=count)
            self.recovery.to_main_from_floor(
                2,
                "Vải vàng recipe: sau dependency Nước táo",
            )

        return self._plant_cotton_and_produce(
            count=count,
            apple_juice_result=juice_result,
        )

    def run_after_floor_2(self, *, count: int = 9) -> YellowFabricRecipeResult:
        """Function-1 entry: Nước táo already finished and camera is known floor 2."""
        self._require_supported_count(count)
        self.recovery.to_main_from_floor(
            2,
            "Vải vàng recipe: sau Nước táo đã có",
        )
        return self._plant_cotton_and_produce(count=count)
