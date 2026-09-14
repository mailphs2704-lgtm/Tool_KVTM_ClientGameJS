from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..errors import ScreenTimeout
from ..recovery import RecoveryManager

if TYPE_CHECKING:
    from ..automation import KVAutomation


__all__ = ["DriedTeaStepTwoRecipe", "DriedTeaStepTwoProgressResult"]


@dataclass(frozen=True)
class DriedTeaStepTwoProgressResult:
    harvested_tea: int
    planted_tea: int
    apple_juices: int
    start_floor: int
    end_floor: int


class DriedTeaStepTwoRecipe:
    """Function 3 Step 2: plant 24 teas, then queue nine apple juices.

    Entry state is the Step 1 live-PASS boundary at floor 1. Step 2 moves once
    with canonical goUp(1), stays on floor 2 for planting + production + repair,
    and deliberately returns while still on floor 2.
    """

    def __init__(
        self,
        automation: KVAutomation,
        *,
        recovery: RecoveryManager,
    ) -> None:
        self.auto = automation
        self.context = automation.context
        self.recovery = recovery

    def run_from_floor_1(self) -> DriedTeaStepTwoProgressResult:
        """Run the complete operator-defined Step 2 from the Step 1 end state."""
        self.context.stage("auto-function-3-step-2-start")
        self.context.log(
            "AUTO Function 3 • Step 2 START • tầng 1 → goUp(1) tầng 2 → "
            "thu/gieo Trà 4 tầng=24 cây → thu VP/mở máy tầng 2 → "
            "Nước táo 9/9 → Sửa máy → giữ nguyên tầng 2"
        )

        self.auto.floors.go_up(
            1,
            label="Function 3 Step 2 • tầng 1 → tầng 2",
        )
        segment = self.auto.planting.harvest_and_replant_current_view(
            seed_template=self.auto.planting.TEA_TEMPLATE,
            item_label="Trà",
            count=24,
            segment_label="Function 3 Step 2 • Trà 4 tầng",
        )
        if int(segment.planted_count) != 24:
            raise ScreenTimeout(
                "Function 3 Step 2 chưa gieo đủ Trà: "
                f"{segment.planted_count}/24"
            )
        self.context.stage("auto-function-3-step-2-tea-24-pass")

        # AppleJuiceProductionActions owns the floor-2 machine interaction. Its
        # verified panel-open path collects ready VP before it queues a new batch,
        # so Step 2 must not add a duplicate/raw machine click here.
        production = self.recovery.run_production(
            floor=2,
            label="Nước táo",
            producer=lambda: self.auto.apple_juice_production.produce_9_apple_juices(
                close_after_success=False
            ),
        )
        self.context.ensure_running()
        self.auto.machine_repair.repair_after_production(production)
        self.context.ensure_running()

        if int(production.queued_count) != 9:
            raise ScreenTimeout(
                "Function 3 Step 2 chưa sản xuất đủ Nước táo: "
                f"{production.queued_count}/9"
            )

        self.context.stage("auto-function-3-step-2-pass")
        self.context.log(
            "AUTO Function 3 • Step 2 PASS • Trà=24/24 • Nước táo=9/9 • "
            "Sửa máy PASS • giữ nguyên vị trí tầng 2"
        )
        return DriedTeaStepTwoProgressResult(
            harvested_tea=int(segment.harvested_count),
            planted_tea=int(segment.planted_count),
            apple_juices=int(production.queued_count),
            start_floor=1,
            end_floor=2,
        )

    def run_defined_prefix_from_floor_1(self) -> DriedTeaStepTwoProgressResult:
        """Compatibility alias kept for the in-progress Step 2 checkpoint commit."""
        return self.run_from_floor_1()
