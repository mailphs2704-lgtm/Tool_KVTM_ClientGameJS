from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..actions.production import ProductionResult
from ..recovery import RecoveryManager

if TYPE_CHECKING:
    from ..automation import KVAutomation


__all__ = ["AppleJuiceRecipe", "AppleJuiceRecipeResult"]


@dataclass(frozen=True)
class AppleJuiceRecipeResult:
    production: ProductionResult
    candidate_verified: bool
    fallback_used: bool

    @property
    def queued_count(self) -> int:
        return int(self.production.queued_count)


class AppleJuiceRecipe:
    """Reusable Nước táo recipe independent from Vải vàng.

    The recipe can start from exact-main, from a floor-2 candidate produced by an
    optimized Function route, or from a known current floor-2 state. The actual
    production action still proves ``nuoc_tao`` and RecoveryManager owns all
    WrongProductionMachine / InventoryFull handling.
    """

    REQUIRED_COUNT = 9
    DIRECT_MAIN_RECOVERY_PASSES = 6

    def __init__(
        self,
        automation: KVAutomation,
        *,
        recovery: RecoveryManager,
    ) -> None:
        self.auto = automation
        self.context = automation.context
        self.recovery = recovery

    def _require_supported_count(self, count: int) -> None:
        if int(count) != self.REQUIRED_COUNT:
            raise ValueError(
                f"Nước táo recipe hiện khóa đúng {self.REQUIRED_COUNT} sản phẩm; "
                f"requested={count}"
            )

    def _produce_and_repair(self, *, count: int) -> ProductionResult:
        self._require_supported_count(count)
        produced = self.recovery.run_production(
            floor=2,
            label="Nước táo",
            producer=lambda: self.auto.apple_juice_production.produce_9_apple_juices(
                close_after_success=False
            ),
        )
        self.context.ensure_running()
        self.auto.machine_repair.repair_after_production(produced)
        self.context.ensure_running()
        self.context.stage("auto-recipe-apple-juice-pass")
        self.context.log("AUTO recipe Nước táo • PASS • SX 9/9 + Sửa máy")
        return produced

    def run_current_floor_2(self, *, count: int = 9) -> AppleJuiceRecipeResult:
        """Produce from a caller-owned known/candidate floor-2 state.

        The caller does not need to pre-prove the machine. The production opener
        itself verifies ``nuoc_tao``; a wrong panel raises the typed signal and is
        centrally recovered by RecoveryManager.
        """
        self.context.stage("auto-recipe-apple-juice-current-floor2")
        produced = self._produce_and_repair(count=count)
        return AppleJuiceRecipeResult(
            production=produced,
            candidate_verified=False,
            fallback_used=False,
        )

    def run_from_main(self, *, count: int = 9) -> AppleJuiceRecipeResult:
        """Standalone Nước táo entry for Functions that begin at exact-main."""
        self._require_supported_count(count)
        self.recovery.from_main_to_floor(2, "Nước táo recipe")
        produced = self._produce_and_repair(count=count)
        return AppleJuiceRecipeResult(
            production=produced,
            candidate_verified=False,
            fallback_used=False,
        )

    def run_from_candidate_floor_2(
        self,
        *,
        count: int = 9,
        verify_candidate: bool = True,
    ) -> AppleJuiceRecipeResult:
        """Consume an optimized candidate such as Function-1 floor6→goDown(4).

        A direct candidate is never trusted from movement alone. The bounded
        ``nuoc_tao`` probe proves it. A miss closes the probe and delegates the
        unknown-camera normalization to RecoveryManager before production.
        """
        self._require_supported_count(count)
        self.context.stage("auto-recipe-apple-juice-candidate-floor2")
        verified = False
        fallback = False

        if verify_candidate:
            verified = bool(self.auto.apple_juice_production.probe_floor_2_machine())
            if not verified:
                fallback = True
                self.context.log(
                    "AUTO recipe Nước táo • candidate tầng 2 MISS • "
                    "RecoveryManager unknown → exact-main → tầng 2"
                )
                self.recovery.recover_unknown_to_floor(
                    2,
                    "Nước táo candidate fallback",
                    reason="apple-juice-recipe-floor2-anchor-miss",
                    max_passes=self.DIRECT_MAIN_RECOVERY_PASSES,
                )
            else:
                self.context.log(
                    "AUTO recipe Nước táo • candidate tầng 2 PASS bằng anchor nuoc_tao"
                )

        produced = self._produce_and_repair(count=count)
        return AppleJuiceRecipeResult(
            production=produced,
            candidate_verified=verified,
            fallback_used=fallback,
        )
