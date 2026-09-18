from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..actions.production import ProductionResult
from ..errors import ScreenTimeout
from ..recovery import RecoveryManager

if TYPE_CHECKING:
    from ..automation import KVAutomation


__all__ = ["DriedTeaStepOneRecipe", "DriedTeaStepOneResult"]


@dataclass(frozen=True)
class DriedTeaStepOneResult:
    replanted_five_floors: int
    replanted_floor_6: int
    production: ProductionResult

    @property
    def produced_count(self) -> int:
        return int(self.production.queued_count)


class DriedTeaStepOneRecipe:
    """Function 3 Step 1: replenish 36 apples, then queue nine dried teas."""

    def __init__(
        self,
        automation: KVAutomation,
        *,
        recovery: RecoveryManager,
    ) -> None:
        self.auto = automation
        self.context = automation.context
        self.recovery = recovery

    def run_from_main(self) -> DriedTeaStepOneResult:
        self.context.stage("auto-function-3-step-1-start")
        self.context.log(
            "AUTO Function 3 • Step 1 START • MAIN → tầng 1 → "
            "thu/gieo 30 Táo → tầng 6 thu/gieo 6 Táo → MAIN → "
            "tầng 1 → 9 Trà sấy → Sửa máy"
        )
        if not self.auto.popup.is_own_exact_main_screen():
            raise ScreenTimeout(
                "Function 3 Step 1 cần exact-main từ lifecycle/test button"
            )

        self.auto.farm_routes.main_to_floor_1()
        five_already_done = self.recovery.cycle.has(
            "function-3-step-1-apple-floor-1-to-5"
        )
        five_floors = self.recovery.cycle.run_once(
            "function-3-step-1-apple-floor-1-to-5",
            label="Function 3 Step 1 • Táo tầng 1-5",
            runner=self.auto.apple_supply.harvest_or_replant_five_floors,
        )
        if int(five_floors) != 30:
            raise ScreenTimeout(
                f"Function 3 Step 1 chưa gieo đủ Táo tầng 1-5: {five_floors}/30"
            )
        self.context.stage("auto-function-3-step-1-apple-floor-1-to-5-pass")

        self.auto.farm_routes.floor_1_to_floor_6()
        six_already_done = self.recovery.cycle.has(
            "function-3-step-1-apple-floor-6"
        )
        floor_6 = self.recovery.cycle.run_once(
            "function-3-step-1-apple-floor-6",
            label="Function 3 Step 1 • Táo tầng 6",
            runner=self.auto.apple_supply.harvest_and_replant_floor_6_row,
        )
        if int(floor_6) != 6:
            raise ScreenTimeout(
                f"Function 3 Step 1 chưa gieo đủ Táo tầng 6: {floor_6}/6"
            )
        self.context.stage("auto-function-3-step-1-apple-floor-6-pass")
        if not (five_already_done and six_already_done):
            self.context.action("Gieo thành công 36 táo")

        self.auto.farm_boundary_routes.known_upper_floor_to_main_via_down_floor(
            "Function 3 Step 1 • tầng 6 về MAIN"
        )
        if not self.auto.popup.is_own_exact_main_screen():
            raise ScreenTimeout(
                "Function 3 Step 1: goDown(1)+nút XUỐNG chưa chứng minh exact-main"
            )

        self.auto.farm_routes.main_to_floor_1()
        production = self.recovery.run_production(
            floor=1,
            label="Trà sấy",
            producer=lambda: self.auto.dried_tea_production.produce_9_dried_teas(
                close_after_success=False
            ),
        )
        self.context.ensure_running()
        self.auto.machine_repair.repair_after_production(production)
        self.context.ensure_running()

        if int(production.queued_count) != 9:
            raise ScreenTimeout(
                f"Function 3 Step 1 chưa sản xuất đủ Trà sấy: "
                f"{production.queued_count}/9"
            )
        self.context.action("Sản xuất 9 trà sấy")
        self.context.stage("auto-function-3-step-1-pass")
        self.context.log(
            "AUTO Function 3 • Step 1 PASS • Táo=30+6 • Trà sấy=9/9 • "
            "Sửa máy PASS • giữ nguyên vị trí tầng 1"
        )
        return DriedTeaStepOneResult(
            replanted_five_floors=int(five_floors),
            replanted_floor_6=int(floor_6),
            production=production,
        )
