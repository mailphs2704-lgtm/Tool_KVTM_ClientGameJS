from __future__ import annotations

from typing import TYPE_CHECKING

from ..recovery import RecoveryManager
from .apple_juice import AppleJuiceRecipe
from .dried_apple import DriedAppleRecipe
from .rose_oil import RoseOilRecipe
from .yellow_fabric import YellowFabricRecipe

if TYPE_CHECKING:
    from ..automation import KVAutomation


__all__ = ["RecipeBook"]


class RecipeBook:
    """Per-Function facade that exposes reusable product recipes.

    All recipes in one Function share one RecoveryManager instance so typed
    events, Function-bound sale recovery and injected route policies stay
    consistent across the complete Function. Function 2 uses the RoseOilRecipe
    recovery instance as the shared manager because that recipe owns the extra
    verified floor-5/floor-7 route map. Function 1 keeps the original generic
    RecoveryManager path unchanged.
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
        self.rose_oil: RoseOilRecipe | None = None

        if self.function_id == "function_2":
            if recovery is not None:
                raise ValueError(
                    "Function 2 RecipeBook tự sở hữu RecoveryManager có route TDHH; "
                    "không nhận recovery ngoài chưa chứng minh route tầng 5/7"
                )
            self.rose_oil = RoseOilRecipe(automation)
            self.recovery = self.rose_oil.recovery
        else:
            self.recovery = recovery or RecoveryManager(
                automation,
                function_id=self.function_id,
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
