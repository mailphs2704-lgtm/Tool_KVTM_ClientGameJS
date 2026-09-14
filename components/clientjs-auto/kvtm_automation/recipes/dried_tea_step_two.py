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
    start_floor: int
    end_floor: int


class DriedTeaStepTwoRecipe:
    """Function 3 Step 2 work-in-progress.

    Only the operator-described prefix is implemented here. It is intentionally
    not wired into the Function 3 public run/test entry until the operator says
    ``step 2 done``.
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

    def run_defined_prefix_from_floor_1(self) -> DriedTeaStepTwoProgressResult:
        """Run the currently-defined Step 2 prefix from the Step 1 end state."""
        self.context.stage("auto-function-3-step-2-prefix-start")
        self.context.log(
            "AUTO Function 3 • Step 2 IN_PROGRESS • tầng 1 → goUp(1) tầng 2 → "
            "thu/gieo Trà 4 tầng trên màn hình = 24 cây"
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
                "Function 3 Step 2 prefix chưa gieo đủ Trà: "
                f"{segment.planted_count}/24"
            )

        self.context.stage("auto-function-3-step-2-prefix-tea-24-pass")
        self.context.log(
            "AUTO Function 3 • Step 2 prefix READY • Trà=24/24 • "
            "seed dùng template động + chuyển trang phải đến khi tìm thấy • "
            "Step 2 vẫn IN_PROGRESS"
        )
        return DriedTeaStepTwoProgressResult(
            harvested_tea=int(segment.harvested_count),
            planted_tea=int(segment.planted_count),
            start_floor=1,
            end_floor=2,
        )
