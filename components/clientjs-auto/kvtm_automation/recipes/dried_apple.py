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
    """Reusable Táo sấy recipe composed from shared Actions.

    Navigation and planting are deliberately separate: the Recipe decides that
    it needs floor 1, then calls the generic crop/count Action. ``PlantingActions``
    no longer needs to know that this crop belongs to Táo sấy Function logic.
    """

    REQUIRED_COUNT = 9
    PLANT_COUNT = 27

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
        """Run from the exact-main state handed off by startup/sale boundary."""
        self._require_supported_count(count)
        self.context.stage("auto-recipe-dried-apple-start")
        self.context.log(
            "AUTO recipe Táo sấy • MAIN → goUp(1) → trồng 27 Táo → SX 9 → Sửa máy"
        )

        if not self.auto.popup.is_own_exact_main_screen():
            raise RuntimeError(
                "Táo sấy recipe cần exact-main từ caller; không tự recovery/navigation ẩn"
            )

        self.auto.floors.go_up(1, label="dried-apple-main-to-floor1")
        planted = self.auto.planting.plant_current_view(
            seed_template=self.auto.planting.APPLE_TEMPLATE,
            item_label="Táo",
            count=self.PLANT_COUNT,
        )
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
        self.context.log("AUTO recipe Táo sấy • PASS • trồng 27 + SX 9/9 + Sửa máy")
        return DriedAppleRecipeResult(
            planted_count=int(planted),
            production=produced,
        )

    def run_from_main(self, *, count: int = 9) -> DriedAppleRecipeResult:
        self.recovery.ensure_main("Táo sấy recipe: trước khi bắt đầu")
        return self.run_from_session(count=count)
