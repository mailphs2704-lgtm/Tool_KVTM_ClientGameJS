from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..errors import ScreenTimeout
from ..recovery import RecoveryManager

if TYPE_CHECKING:
    from ..automation import KVAutomation


__all__ = ["DriedTeaStepSixRecipe", "DriedTeaStepSixProgressResult"]


@dataclass(frozen=True)
class DriedTeaStepSixProgressResult:
    roses_floor_1_planted: int
    roses_floor_6_planted: int
    roses_harvested: int
    rose_waters: int
    start_floor: int
    end_floor: int


class DriedTeaStepSixRecipe:
    """Final Function 3 step: roses on floors 1/6, then rose water on floor 8."""

    def __init__(self, automation: KVAutomation, *, recovery: RecoveryManager) -> None:
        self.auto = automation
        self.context = automation.context
        self.recovery = recovery
        self.recovery.register_navigation_routes(
            to_main_routes={8: self._floor_8_to_main},
            from_main_routes={8: self._main_to_floor_8},
        )

    def _main_to_floor_8(self, label: str) -> None:
        self.context.log(
            f"AUTO Step 6 recovery • {label} • MAIN → tầng 1 → tầng 6 → goUp(2) tầng 8"
        )
        self.auto.farm_routes.main_to_floor_1()
        self.auto.farm_routes.floor_1_to_floor_6()
        self.auto.floors.go_up(
            2,
            label="Function 3 Step 6 recovery • tầng 6 → tầng 8 • click chậu đầu hàng 4",
        )

    def _floor_8_to_main(self, label: str) -> None:
        self.context.log(
            f"AUTO Step 6 recovery • {label} • tầng 8 → goDown(1) → chờ 1s → XUỐNG MAIN"
        )
        self.auto.farm_boundary_routes.known_upper_floor_to_main_via_down_floor(
            "Function 3 Step 6 recovery tầng 8 → MAIN"
        )

    def run_from_floor_1(self) -> DriedTeaStepSixProgressResult:
        self.context.stage("auto-function-3-step-6-start")
        self.context.log(
            "AUTO Function 3 • Step 6 START • tầng 1 → Hồng 30 → "
            "goUp(4)+goUp(1) tầng 6 → Hồng 6 → goUp(2) click chậu đầu hàng 4 "
            "lên tầng 8 → Nước hoa hồng 9/9 → Sửa máy → "
            "goDown(1) → chờ 1s → XUỐNG exact MAIN → Function 3 DONE"
        )

        planting = self.auto.planting
        nav = self.auto.farm_routes
        boundary = self.auto.farm_boundary_routes

        roses_floor_1 = self.recovery.cycle.run_once(
            "function-3-step-6-rose-floor-1",
            label="Function 3 Step 6 • Hồng 30 tầng 1",
            runner=lambda: planting.harvest_and_replant_current_view(
                seed_template=planting.ROSE_TEMPLATE,
                item_label="Hoa hồng",
                count=30,
                segment_label="Function 3 Step 6 • Hồng 5 hàng tầng 1",
            ),
        )
        if int(roses_floor_1.planted_count) != 30:
            raise ScreenTimeout(
                "Function 3 Step 6 chưa gieo đủ Hồng tầng 1: "
                f"{roses_floor_1.planted_count}/30"
            )
        self.context.stage("auto-function-3-step-6-rose-floor1-30-pass")

        nav.floor_1_to_floor_6()
        roses_floor_6 = self.recovery.cycle.run_once(
            "function-3-step-6-rose-floor-6",
            label="Function 3 Step 6 • Hồng 6 tầng 6",
            runner=lambda: planting.harvest_and_replant_current_view(
                seed_template=planting.ROSE_TEMPLATE,
                item_label="Hoa hồng",
                count=6,
                segment_label="Function 3 Step 6 • Hồng hàng cuối tầng 6",
            ),
        )
        if int(roses_floor_6.planted_count) != 6:
            raise ScreenTimeout(
                "Function 3 Step 6 chưa gieo đủ Hồng tầng 6: "
                f"{roses_floor_6.planted_count}/6"
            )
        self.context.stage("auto-function-3-step-6-rose-floor6-6-pass")
        self.context.action("Gieo thành công 36 hồng")

        self.auto.floors.go_up(
            2,
            label=(
                "Function 3 Step 6 • tầng 6 → tầng 8 • "
                "click chậu đầu hàng 4"
            ),
        )
        self.context.stage("auto-function-3-step-6-floor8-production")

        production = self.recovery.run_production(
            floor=8,
            label="Nước hoa hồng",
            producer=lambda: self.auto.rose_water_production.produce_9_rose_waters(
                close_after_success=False
            ),
        )
        self.context.ensure_running()
        self.auto.machine_repair.repair_after_production(production)
        self.context.ensure_running()
        if int(production.queued_count) != 9:
            raise ScreenTimeout(
                "Function 3 Step 6 chưa sản xuất đủ Nước hoa hồng: "
                f"{production.queued_count}/9"
            )
        self.context.stage("auto-function-3-step-6-rose-water-9-pass")
        self.context.action("Sản xuất 9 nước hoa hồng")

        boundary.known_upper_floor_to_main_via_down_floor(
            "Function 3 Step 6 tầng 8 → MAIN"
        )
        self.context.ensure_running()
        if not self.auto.popup.is_own_exact_main_screen():
            raise ScreenTimeout(
                "Function 3 Step 6 đã goDown(1)+XUỐNG nhưng chưa chứng minh exact MAIN"
            )

        harvested = int(roses_floor_1.harvested_count + roses_floor_6.harvested_count)
        self.context.stage("auto-function-3-step-6-pass")
        self.context.log(
            "AUTO Function 3 • Step 6 PASS • Hồng tầng 1=30/30 • "
            "Hồng tầng 6=6/6 • Nước hoa hồng=9/9 • Sửa máy PASS • "
            "kết thúc exact MAIN • Function 3 DONE"
        )
        return DriedTeaStepSixProgressResult(
            roses_floor_1_planted=int(roses_floor_1.planted_count),
            roses_floor_6_planted=int(roses_floor_6.planted_count),
            roses_harvested=harvested,
            rose_waters=int(production.queued_count),
            start_floor=1,
            end_floor=0,
        )
