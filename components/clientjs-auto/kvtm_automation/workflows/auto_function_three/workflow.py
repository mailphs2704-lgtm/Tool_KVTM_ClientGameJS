from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation
from ...recipes import RecipeBook


__all__ = [
    "FunctionThreeStepOneResult",
    "FunctionThreeStepTwoResult",
    "FunctionThreeStepsOneTwoResult",
    "FunctionThreeWorkflow",
]


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


@dataclass(frozen=True)
class FunctionThreeStepTwoResult:
    profile_id: str
    harvested_teas: int
    planted_teas: int
    apple_juices: int
    progress_steps: int
    total_steps: int
    end_floor: int
    elapsed_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class FunctionThreeStepsOneTwoResult:
    profile_id: str
    apples_floor_1_to_5: int
    apples_floor_6: int
    dried_teas: int
    harvested_teas: int
    planted_teas: int
    apple_juices: int
    progress_steps: int
    total_steps: int
    end_floor: int
    elapsed_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


class FunctionThreeWorkflow:
    """Function 3 owner with one shared RecipeBook and RecoveryManager.

    Step 1 and Step 2 are operator-defined. Step 1 remains available as its
    already-live-verified isolated boundary. Step 2 starts from that exact floor-1
    boundary and ends on floor 2. Full AUTO Main wiring stays fail-closed until
    the operator finishes defining the remaining Function 3 work.
    """

    TOTAL_DEFINED_STEPS = 2

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context
        self.recipes = RecipeBook(
            automation,
            function_id="function_3",
        )
        self.recovery = self.recipes.recovery
        self.step_one = self.recipes.dried_tea_step_one
        self.step_two = self.recipes.dried_tea_step_two
        if self.step_one is None:
            raise RuntimeError("Function 3 RecipeBook thiếu DriedTeaStepOneRecipe")
        if self.step_two is None:
            raise RuntimeError("Function 3 RecipeBook thiếu DriedTeaStepTwoRecipe")

    def run_step_1(self) -> FunctionThreeStepOneResult:
        started = time.monotonic()
        result = self.step_one.run_from_main()
        return FunctionThreeStepOneResult(
            profile_id=self.context.profile_id,
            apples_floor_1_to_5=int(result.replanted_five_floors),
            apples_floor_6=int(result.replanted_floor_6),
            dried_teas=int(result.produced_count),
            progress_steps=1,
            total_steps=self.TOTAL_DEFINED_STEPS,
            end_floor=1,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )

    def run_step_2_from_floor_1(self) -> FunctionThreeStepTwoResult:
        """Run only Step 2 when the caller already owns the Step 1 end state."""
        started = time.monotonic()
        result = self.step_two.run_from_floor_1()
        return FunctionThreeStepTwoResult(
            profile_id=self.context.profile_id,
            harvested_teas=int(result.harvested_tea),
            planted_teas=int(result.planted_tea),
            apple_juices=int(result.apple_juices),
            progress_steps=2,
            total_steps=self.TOTAL_DEFINED_STEPS,
            end_floor=2,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )

    def run_steps_1_and_2(self) -> FunctionThreeStepsOneTwoResult:
        """Run the currently complete Function 3 definition from exact MAIN."""
        started = time.monotonic()
        step_one = self.step_one.run_from_main()
        step_two = self.step_two.run_from_floor_1()
        return FunctionThreeStepsOneTwoResult(
            profile_id=self.context.profile_id,
            apples_floor_1_to_5=int(step_one.replanted_five_floors),
            apples_floor_6=int(step_one.replanted_floor_6),
            dried_teas=int(step_one.produced_count),
            harvested_teas=int(step_two.harvested_tea),
            planted_teas=int(step_two.planted_tea),
            apple_juices=int(step_two.apple_juices),
            progress_steps=2,
            total_steps=self.TOTAL_DEFINED_STEPS,
            end_floor=2,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )

    def run(self):
        raise RuntimeError(
            "Function 3 chưa được nối vào AUTO chính: Step 1-2 đã được định nghĩa; "
            "chờ operator mô tả phần tiếp theo"
        )
