from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..actions.production import ProductionResult
from ..recovery import RecoveryManager

if TYPE_CHECKING:
    from ..automation import KVAutomation


__all__ = ["DriedAppleRecipe", "DriedAppleRecipeResult"]


@dataclass(frozen=True)
class DriedAppleRecipeResult:
    planted_count: int
    production: ProductionResult

    @property
    def produced_count(self) -> int:
        return int(self.production.queued_count)


class DriedAppleRecipe:
    """Reusable Táo sấy recipe: plant apples, produce x9, then repair.

    This recipe preserves the proven startup behavior: the owning GameSession has
    already normalized the account before the recipe begins, and the planting
    action performs the existing goUp(1) entry to the farm rows. Recovery handles
    only explicit production signals; generic visual failures still fail closed.
    """

    REQUIRED_COUNT = 9

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
                f"Táo sấy recipe hiện khóa đúng {self.REQUIRED_COUNT} sản phẩm; "
                f"requested={count}"
            )

    def run_from_session(self, *, count: int = 9) -> DriedAppleRecipeResult:
        """Run from the same startup state previously consumed by AppleDryerWorkflow."""
        self._require_supported_count(count)
        self.context.stage("auto-recipe-dried-apple-start")
        self.context.log(
            "AUTO recipe Táo sấy • bắt đầu • trồng Táo → SX 9 → Sửa máy"
        )

        planted = self.auto.planting.plant_27_apples()
        self.context.ensure_running()
        self.context.stage("auto-recipe-dried-apple-planted")

        produced = self.recovery.run_production(
            floor=1,
            label="Táo sấy",
            producer=lambda: self.auto.production.produce_9_dried_apples(
                close_after_success=False
            ),
        )
        self.context.ensure_running()
        self.auto.machine_repair.repair_after_production(produced)
        self.context.ensure_running()
        self.context.stage("auto-recipe-dried-apple-pass")
        self.context.log("AUTO recipe Táo sấy • PASS • trồng + SX 9/9 + Sửa máy")
        return DriedAppleRecipeResult(
            planted_count=int(planted),
            production=produced,
        )

    def run_from_main(self, *, count: int = 9) -> DriedAppleRecipeResult:
        """Reusable entry when a future Function explicitly owns exact-main."""
        self.recovery.ensure_main("Táo sấy recipe: trước khi bắt đầu")
        return self.run_from_session(count=count)
