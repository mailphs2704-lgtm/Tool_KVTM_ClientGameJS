from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..errors import ScreenTimeout
from ..recovery import RecoveryManager

if TYPE_CHECKING:
    from ..automation import KVAutomation


__all__ = ["DriedTeaStepFourRecipe", "DriedTeaStepFourProgressResult"]


@dataclass(frozen=True)
class DriedTeaStepFourProgressResult:
    roses_floor_1_planted: int
    roses_floor_6_planted: int
    roses_harvested: int
    tdhh_snow_floor_1_planted: int
    tdhh_snow_floor_6_planted: int
    rose_oils: int
    start_floor: int
    end_floor: int


class DriedTeaStepFourRecipe:
    """Function 3 Step 4 from the Step 3 floor-1 boundary back to floor 1."""

    def __init__(
        self,
        automation: KVAutomation,
        *,
        recovery: RecoveryManager,
    ) -> None:
        self.auto = automation
        self.context = automation.context
        self.recovery = recovery

    def run_from_floor_1(self) -> DriedTeaStepFourProgressResult:
        """Run the corrected TDHH material sequence from the Step 3 end state."""
        self.context.stage("auto-function-3-step-4-start")
        self.context.log(
            "AUTO Function 3 • Step 4 START • tầng 1 Hồng 30 → "
            "goUp(4)+goUp(1) tầng 6 Hồng 15 → về MAIN → goUp(1) tầng 1 → "
            "Tuyết 30 → goUp(4)+goUp(1) tầng 6 Tuyết 6 → "
            "goDown(1) tầng 5 → TDHH 9/9 → Sửa máy → "
            "goDown(1)+chờ 1s+XUỐNG MAIN → goUp(1) tầng 1"
        )

        planting = self.auto.planting
        nav = self.auto.farm_routes
        boundary = self.auto.farm_boundary_routes

        roses_floor_1 = planting.harvest_and_replant_current_view(
            seed_template=planting.ROSE_TEMPLATE,
            item_label="Hoa hồng",
            count=30,
            segment_label="Function 3 Step 4 • Hồng 5 hàng tầng 1",
        )
        if int(roses_floor_1.planted_count) != 30:
            raise ScreenTimeout(
                "Function 3 Step 4 chưa gieo đủ Hồng tầng 1: "
                f"{roses_floor_1.planted_count}/30"
            )
        self.context.stage("auto-function-3-step-4-rose-floor1-30-pass")

        nav.floor_1_to_floor_6()
        roses_floor_6 = planting.harvest_and_replant_current_view(
            seed_template=planting.ROSE_TEMPLATE,
            item_label="Hoa hồng",
            count=15,
            segment_label=(
                "Function 3 Step 4 • Hồng tầng 6 • 2 hàng đủ + 3 chậu đầu hàng 3"
            ),
        )
        if int(roses_floor_6.planted_count) != 15:
            raise ScreenTimeout(
                "Function 3 Step 4 chưa gieo đủ Hồng tầng 6: "
                f"{roses_floor_6.planted_count}/15"
            )
        self.context.stage("auto-function-3-step-4-rose-floor6-15-pass")

        # TDHH needs both Hồng and Tuyết. After the full 45-Hồng pass, return to
        # floor 1 and prepare the missing 36 Tuyết before entering the machine.
        boundary.floor_6_to_main_via_down_floor()
        self.context.ensure_running()
        nav.main_to_floor_1()
        self.context.ensure_running()

        snow_floor_1 = planting.harvest_and_replant_current_view(
            seed_template=planting.SNOW_TEMPLATE,
            item_label="Cây tuyết",
            count=30,
            segment_label="Function 3 Step 4 • TDHH material • Tuyết 5 hàng tầng 1",
        )
        if int(snow_floor_1.planted_count) != 30:
            raise ScreenTimeout(
                "Function 3 Step 4 chưa gieo đủ Tuyết tầng 1 trước TDHH: "
                f"{snow_floor_1.planted_count}/30"
            )
        self.context.stage("auto-function-3-step-4-snow-floor1-30-pass")

        nav.floor_1_to_floor_6()
        snow_floor_6 = planting.harvest_and_replant_current_view(
            seed_template=planting.SNOW_TEMPLATE,
            item_label="Cây tuyết",
            count=6,
            segment_label="Function 3 Step 4 • TDHH material • Tuyết hàng cuối tầng 6",
        )
        if int(snow_floor_6.planted_count) != 6:
            raise ScreenTimeout(
                "Function 3 Step 4 chưa gieo đủ Tuyết tầng 6 trước TDHH: "
                f"{snow_floor_6.planted_count}/6"
            )
        self.context.stage("auto-function-3-step-4-snow-floor6-6-pass")

        # Once the sixth-floor Tuyết row is done, the TDHH machine is directly
        # one floor below. Do not go MAIN and climb back up; use one goDown(1).
        nav.go_down(
            1,
            label="Function 3 Step 4 • tầng 6 → tầng 5 sau Tuyết 36",
        )
        self.context.stage("auto-function-3-step-4-floor5-production")

        production = self.recovery.run_production(
            floor=5,
            label="Tinh dầu hoa hồng",
            producer=lambda: self.auto.rose_oil_production.produce_9_rose_oils(
                close_after_success=False
            ),
        )
        self.context.ensure_running()
        self.auto.machine_repair.repair_after_production(production)
        self.context.ensure_running()
        if int(production.queued_count) != 9:
            raise ScreenTimeout(
                "Function 3 Step 4 chưa sản xuất đủ TDHH: "
                f"{production.queued_count}/9"
            )
        self.context.stage("auto-function-3-step-4-rose-oil-9-pass")

        boundary.floor_5_to_main_via_down_floor()
        self.context.ensure_running()
        nav.main_to_floor_1()
        self.context.ensure_running()

        harvested = int(
            roses_floor_1.harvested_count + roses_floor_6.harvested_count
        )
        self.context.stage("auto-function-3-step-4-pass")
        self.context.log(
            "AUTO Function 3 • Step 4 PASS • Hồng=45/45 • Tuyết=36/36 • "
            "TDHH=9/9 • Sửa máy PASS • kết thúc tầng 1"
        )
        return DriedTeaStepFourProgressResult(
            roses_floor_1_planted=int(roses_floor_1.planted_count),
            roses_floor_6_planted=int(roses_floor_6.planted_count),
            roses_harvested=harvested,
            tdhh_snow_floor_1_planted=int(snow_floor_1.planted_count),
            tdhh_snow_floor_6_planted=int(snow_floor_6.planted_count),
            rose_oils=int(production.queued_count),
            start_floor=1,
            end_floor=1,
        )