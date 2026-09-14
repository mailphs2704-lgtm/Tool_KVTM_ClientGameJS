from __future__ import annotations

from typing import TYPE_CHECKING

from ..recovery import RecoveryManager
from .apple_juice import AppleJuiceRecipe
from .dried_apple import DriedAppleRecipe
from .dried_tea_step_one import DriedTeaStepOneRecipe
from .dried_tea_step_two import DriedTeaStepTwoRecipe
from .rose_oil import RoseOilRecipe
from .yellow_fabric import YellowFabricRecipe

if TYPE_CHECKING:
    from ..automation import KVAutomation


__all__ = ["RecipeBook"]


class RecipeBook:
    """Per-Function facade with exactly one shared RecoveryManager.

    Product Recipes may register additional deterministic floor routes on that
    manager, but no Recipe creates a parallel manager. This keeps typed events,
    checkpoint lifecycle and Function-bound recovery policy in one place.
    """

    def __init__(
        self,
        automation: KVAutomation,
        *,
        function_id: str,
        recovery: RecoveryManager | None = None,
    ) -> None:
        self.auto = automation
        self.function_id = str(function_id)
        self.recovery = recovery or RecoveryManager(
            automation,
            function_id=self.function_id,
        )
        if self.recovery.function_id != self.function_id:
            raise ValueError(
                "RecipeBook nhận RecoveryManager sai function_id: "
                f"book={self.function_id}, recovery={self.recovery.function_id}"
            )

        self.dried_apple = DriedAppleRecipe(
            automation,
            recovery=self.recovery,
        )
        self.apple_juice = AppleJuiceRecipe(
            automation,
            recovery=self.recovery,
        )
        self.yellow_fabric = YellowFabricRecipe(
            automation,
            recovery=self.recovery,
            apple_juice=self.apple_juice,
        )
        self.rose_oil: RoseOilRecipe | None = None
        if self.function_id == "function_2":
            self.rose_oil = RoseOilRecipe(
                automation,
                recovery=self.recovery,
            )
        self.dried_tea_step_one: DriedTeaStepOneRecipe | None = None
        self.dried_tea_step_two: DriedTeaStepTwoRecipe | None = None
        if self.function_id == "function_3":
            self.dried_tea_step_one = DriedTeaStepOneRecipe(
                automation,
                recovery=self.recovery,
            )
            self.dried_tea_step_two = DriedTeaStepTwoRecipe(
                automation,
                recovery=self.recovery,
            )
