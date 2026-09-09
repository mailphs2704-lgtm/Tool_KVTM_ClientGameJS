from __future__ import annotations

from typing import TYPE_CHECKING

from ..recovery import RecoveryManager
from .apple_juice import AppleJuiceRecipe
from .dried_apple import DriedAppleRecipe
from .yellow_fabric import YellowFabricRecipe

if TYPE_CHECKING:
    from ..automation import KVAutomation


__all__ = ["RecipeBook"]


class RecipeBook:
    """Per-Function facade that exposes reusable product recipes.

    All recipes share one RecoveryManager instance so typed events, Function-bound
    sale recovery and injected route policies stay consistent across the whole
    Function. A future Function can therefore focus on recipe ordering rather than
    duplicating error/navigation loops.
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
