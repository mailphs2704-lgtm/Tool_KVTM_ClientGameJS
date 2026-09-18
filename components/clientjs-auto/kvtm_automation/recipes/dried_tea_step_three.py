from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..errors import ScreenTimeout
from ..recovery import RecoveryManager

if TYPE_CHECKING:
    from ..automation import KVAutomation


__all__ = ["DriedTeaStepThreeRecipe", "DriedTeaStepThreeProgressResult"]


@dataclass(frozen=True)
class DriedTeaStepThreeProgressResult:
    harvested_tea_bottom_row: int
    planted_tea_bottom_row: int
    cotton_planted: int
    yellow_fabrics: int
    start_floor: int
    end_floor: int


class DriedTeaStepThreeRecipe:
    """Function 3 Step 3 from the Step 2 floor-2 boundary to floor 1."""

    def __init__(
        self,
        automation: KVAutomation,
        *,
        recovery: RecoveryManager,
    ) -> None:
        self.auto = automation
        self.context = automation.context
        self.recovery = recovery

    def run_from_floor_2(self) -> DriedTeaStepThreeProgressResult:
        self.context.stage("auto-function-3-step-3-start")
        self.context.log(
            "AUTO Function 3 • Step 3 START • giữ tầng 2 → thu 6 chậu hàng dưới "
            "→ gieo lại 3 Trà → goUp(1) tầng 3 → thu/gieo 27 Bông → "
            "Vải vàng 9/9 → Sửa máy → goDown(1)+XUỐNG MAIN → goUp(1) tầng 1"
        )

        tea_row = self.recovery.cycle.run_once(
            "function-3-step-3-tea-bottom-row",
            label="Function 3 Step 3 • Trà hàng dưới tầng 2",
            runner=lambda: self.auto.planting.harvest_and_replant_current_view(
                seed_template=self.auto.planting.TEA_TEMPLATE,
                item_label="Trà",
                count=6,
                plant_count=3,
                segment_label="Function 3 Step 3 • hàng dưới tầng 2 • thu 6 / gieo 3 Trà",
            ),
        )
        if int(tea_row.planted_count) != 3:
            raise ScreenTimeout(
                "Function 3 Step 3 chưa gieo đúng 3 Trà hàng dưới tầng 2: "
                f"{tea_row.planted_count}/3"
            )
        self.context.stage("auto-function-3-step-3-tea-bottom-3-pass")
        self.context.action("Gieo thành công 3 trà")

        self.auto.floors.go_up(
            1,
            label="Function 3 Step 3 • tầng 2 → tầng 3",
        )
        cotton = self.recovery.cycle.run_once(
            "function-3-step-3-cotton-27",
            label="Function 3 Step 3 • Bông 27",
            runner=lambda: self.auto.cotton_planting.plant_27_cotton(),
        )
        if int(cotton) != 27:
            raise ScreenTimeout(
                f"Function 3 Step 3 chưa gieo đủ Bông: {cotton}/27"
            )
        self.context.stage("auto-function-3-step-3-cotton-27-pass")
        self.context.action("Gieo thành công 27 bông")

        production = self.recovery.run_production(
            floor=3,
            label="Vải vàng",
            producer=lambda: self.auto.yellow_fabric_production.produce_9_yellow_fabrics(
                close_after_success=False
            ),
        )
        self.context.ensure_running()
        self.auto.machine_repair.repair_after_production(production)
        self.context.ensure_running()
        if int(production.queued_count) != 9:
            raise ScreenTimeout(
                "Function 3 Step 3 chưa sản xuất đủ Vải vàng: "
                f"{production.queued_count}/9"
            )
        self.context.stage("auto-function-3-step-3-yellow-fabric-9-pass")
        self.context.action("Sản xuất 9 vải vàng")

        self.auto.farm_boundary_routes.floor_3_to_main_via_down_floor()
        self.context.ensure_running()
        self.auto.floors.go_up(
            1,
            label="Function 3 Step 3 • MAIN → tầng 1 kết thúc Step 3",
        )
        self.context.ensure_running()

        self.context.stage("auto-function-3-step-3-pass")
        self.context.log(
            "AUTO Function 3 • Step 3 PASS • hàng dưới tầng 2 thu="
            f"{tea_row.harvested_count}/6 • gieo Trà=3/3 • Bông=27/27 • "
            "Vải vàng=9/9 • Sửa máy PASS • kết thúc tầng 1"
        )
        return DriedTeaStepThreeProgressResult(
            harvested_tea_bottom_row=int(tea_row.harvested_count),
            planted_tea_bottom_row=int(tea_row.planted_count),
            cotton_planted=int(cotton),
            yellow_fabrics=int(production.queued_count),
            start_floor=2,
            end_floor=1,
        )
