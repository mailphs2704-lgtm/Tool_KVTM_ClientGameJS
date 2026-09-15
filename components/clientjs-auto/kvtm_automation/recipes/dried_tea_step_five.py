from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..errors import ScreenTimeout
from ..recovery import RecoveryManager

if TYPE_CHECKING:
    from ..automation import KVAutomation


__all__ = ["DriedTeaStepFiveRecipe", "DriedTeaStepFiveProgressResult"]


@dataclass(frozen=True)
class DriedTeaStepFiveProgressResult:
    snow_floor_1_planted: int
    snow_floor_6_planted: int
    snow_harvested: int
    iced_teas: int
    start_floor: int
    end_floor: int


class DriedTeaStepFiveRecipe:
    """Function 3 Step 5 from the Step 4 floor-1 boundary back to floor 1."""

    def __init__(self, automation: KVAutomation, *, recovery: RecoveryManager) -> None:
        self.auto = automation
        self.context = automation.context
        self.recovery = recovery

    def run_from_floor_1(self) -> DriedTeaStepFiveProgressResult:
        self.context.stage("auto-function-3-step-5-start")
        self.context.log(
            "AUTO Function 3 • Step 5 START • tầng 1 → Tuyết 30 → "
            "goUp(4)+goUp(1) tầng 6 → Tuyết 6 → Trà đá 9/9 → "
            "Sửa máy → goDown(1) → chờ 1s → XUỐNG MAIN → goUp(1) tầng 1"
        )
        planting = self.auto.planting
        nav = self.auto.farm_routes
        boundary = self.auto.farm_boundary_routes

        snow_floor_1 = planting.harvest_and_replant_current_view(
            seed_template=planting.SNOW_TEMPLATE, item_label="Cây tuyết", count=30,
            segment_label="Function 3 Step 5 • Tuyết 5 hàng tầng 1",
        )
        if int(snow_floor_1.planted_count) != 30:
            raise ScreenTimeout(
                "Function 3 Step 5 chưa gieo đủ Tuyết tầng 1: "
                f"{snow_floor_1.planted_count}/30"
            )
        self.context.stage("auto-function-3-step-5-snow-floor1-30-pass")

        nav.floor_1_to_floor_6()
        snow_floor_6 = planting.harvest_and_replant_current_view(
            seed_template=planting.SNOW_TEMPLATE, item_label="Cây tuyết", count=6,
            segment_label="Function 3 Step 5 • Tuyết hàng cuối tầng 6",
        )
        if int(snow_floor_6.planted_count) != 6:
            raise ScreenTimeout(
                "Function 3 Step 5 chưa gieo đủ Tuyết tầng 6: "
                f"{snow_floor_6.planted_count}/6"
            )
        self.context.stage("auto-function-3-step-5-snow-floor6-6-pass")
        self.context.action("Gieo thành công 36 tuyết")

        production = self.recovery.run_production(
            floor=6, label="Trà đá",
            producer=lambda: self.auto.iced_tea_production.produce_9_iced_teas(
                close_after_success=False
            ),
        )
        self.context.ensure_running()
        self.auto.machine_repair.repair_after_production(production)
        self.context.ensure_running()
        if int(production.queued_count) != 9:
            raise ScreenTimeout(
                "Function 3 Step 5 chưa sản xuất đủ Trà đá: "
                f"{production.queued_count}/9"
            )
        self.context.stage("auto-function-3-step-5-iced-tea-9-pass")
        self.context.action("Sản xuất 9 trà đá")

        boundary.floor_6_to_main_via_down_floor()
        self.context.ensure_running()
        nav.main_to_floor_1()
        self.context.ensure_running()

        harvested = int(snow_floor_1.harvested_count + snow_floor_6.harvested_count)
        self.context.stage("auto-function-3-step-5-pass")
        self.context.log(
            "AUTO Function 3 • Step 5 PASS • Tuyết tầng 1=30/30 • "
            "Tuyết tầng 6=6/6 • Trà đá=9/9 • Sửa máy PASS • kết thúc tầng 1"
        )
        return DriedTeaStepFiveProgressResult(
            snow_floor_1_planted=int(snow_floor_1.planted_count),
            snow_floor_6_planted=int(snow_floor_6.planted_count),
            snow_harvested=harvested,
            iced_teas=int(production.queued_count),
            start_floor=1,
            end_floor=1,
        )
