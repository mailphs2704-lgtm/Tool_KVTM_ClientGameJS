from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation
from ...recipes import RecipeBook


__all__ = ["FunctionThreeStepOneResult", "FunctionThreeWorkflow"]


@dataclass(frozen=True)
class FunctionThreeStepOneResult:
    profile_id: str
    apples_floor_1_to_5: int
    apples_floor_6: int
    dried_teas: int
    progress_steps: int
    total_steps: int
    end_floor: int
    elapsed_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


class FunctionThreeWorkflow:
    """Function 3 owner with one shared RecipeBook and RecoveryManager.

    Only Step 1 is operator-defined. The full run entry is intentionally
    fail-closed before any input until the remaining steps are described.
    """

    TOTAL_STEPS_PENDING = 3

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context
        self.recipes = RecipeBook(
            automation,
            function_id="function_3",
        )
        self.recovery = self.recipes.recovery
        self.step_one = self.recipes.dried_tea_step_one
        if self.step_one is None:
            raise RuntimeError("Function 3 RecipeBook thiếu DriedTeaStepOneRecipe")

    def run_step_1(self) -> FunctionThreeStepOneResult:
        started = time.monotonic()
        result = self.step_one.run_from_main()
        return FunctionThreeStepOneResult(
            profile_id=self.context.profile_id,
            apples_floor_1_to_5=int(result.replanted_five_floors),
            apples_floor_6=int(result.replanted_floor_6),
            dried_teas=int(result.produced_count),
            progress_steps=1,
            total_steps=self.TOTAL_STEPS_PENDING,
            end_floor=1,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )

    def run(self):
        raise RuntimeError(
            "Function 3 chưa được nối vào AUTO chính: mới hoàn tất Step 1; "
            "chờ operator mô tả các Step còn lại"
        )
