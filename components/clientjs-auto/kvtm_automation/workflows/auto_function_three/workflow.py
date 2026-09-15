from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation
from ...recipes import RecipeBook


__all__ = [
    "FunctionThreeStepOneResult",
    "FunctionThreeStepTwoResult",
    "FunctionThreeStepThreeResult",
    "FunctionThreeStepFourResult",
    "FunctionThreeStepFiveResult",
    "FunctionThreeStepsOneTwoResult",
    "FunctionThreeStepsOneTwoThreeResult",
    "FunctionThreeStepsOneTwoThreeFourResult",
    "FunctionThreeStepsOneTwoThreeFourFiveResult",
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
class FunctionThreeStepThreeResult:
    profile_id: str
    harvested_tea_bottom_row: int
    planted_tea_bottom_row: int
    cotton_planted: int
    yellow_fabrics: int
    progress_steps: int
    total_steps: int
    end_floor: int
    elapsed_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class FunctionThreeStepFourResult:
    profile_id: str
    roses_floor_1_planted: int
    roses_floor_6_planted: int
    roses_harvested: int
    rose_oils: int
    progress_steps: int
    total_steps: int
    end_floor: int
    elapsed_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class FunctionThreeStepFiveResult:
    profile_id: str
    snow_floor_1_planted: int
    snow_floor_6_planted: int
    snow_harvested: int
    iced_teas: int
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


@dataclass(frozen=True)
class FunctionThreeStepsOneTwoThreeResult:
    profile_id: str
    apples_floor_1_to_5: int
    apples_floor_6: int
    dried_teas: int
    harvested_teas: int
    planted_teas: int
    apple_juices: int
    harvested_tea_bottom_row: int
    planted_tea_bottom_row: int
    cotton_planted: int
    yellow_fabrics: int
    progress_steps: int
    total_steps: int
    end_floor: int
    elapsed_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class FunctionThreeStepsOneTwoThreeFourResult:
    profile_id: str
    apples_floor_1_to_5: int
    apples_floor_6: int
    dried_teas: int
    harvested_teas: int
    planted_teas: int
    apple_juices: int
    harvested_tea_bottom_row: int
    planted_tea_bottom_row: int
    cotton_planted: int
    yellow_fabrics: int
    roses_floor_1_planted: int
    roses_floor_6_planted: int
    roses_harvested: int
    rose_oils: int
    progress_steps: int
    total_steps: int
    end_floor: int
    elapsed_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class FunctionThreeStepsOneTwoThreeFourFiveResult:
    profile_id: str
    apples_floor_1_to_5: int
    apples_floor_6: int
    dried_teas: int
    harvested_teas: int
    planted_teas: int
    apple_juices: int
    harvested_tea_bottom_row: int
    planted_tea_bottom_row: int
    cotton_planted: int
    yellow_fabrics: int
    roses_floor_1_planted: int
    roses_floor_6_planted: int
    roses_harvested: int
    rose_oils: int
    snow_floor_1_planted: int
    snow_floor_6_planted: int
    snow_harvested: int
    iced_teas: int
    progress_steps: int
    total_steps: int
    end_floor: int
    elapsed_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


class FunctionThreeWorkflow:
    """Function 3 owner with one shared RecipeBook and RecoveryManager."""

    TOTAL_DEFINED_STEPS = 5

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
        self.step_three = self.recipes.dried_tea_step_three
        self.step_four = self.recipes.dried_tea_step_four
        self.step_five = self.recipes.dried_tea_step_five
        if self.step_one is None:
            raise RuntimeError("Function 3 RecipeBook thiếu DriedTeaStepOneRecipe")
        if self.step_two is None:
            raise RuntimeError("Function 3 RecipeBook thiếu DriedTeaStepTwoRecipe")
        if self.step_three is None:
            raise RuntimeError("Function 3 RecipeBook thiếu DriedTeaStepThreeRecipe")
        if self.step_four is None:
            raise RuntimeError("Function 3 RecipeBook thiếu DriedTeaStepFourRecipe")
        if self.step_five is None:
            raise RuntimeError("Function 3 RecipeBook thiếu DriedTeaStepFiveRecipe")

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

    def run_step_3_from_floor_2(self) -> FunctionThreeStepThreeResult:
        started = time.monotonic()
        result = self.step_three.run_from_floor_2()
        return FunctionThreeStepThreeResult(
            profile_id=self.context.profile_id,
            harvested_tea_bottom_row=int(result.harvested_tea_bottom_row),
            planted_tea_bottom_row=int(result.planted_tea_bottom_row),
            cotton_planted=int(result.cotton_planted),
            yellow_fabrics=int(result.yellow_fabrics),
            progress_steps=3,
            total_steps=self.TOTAL_DEFINED_STEPS,
            end_floor=1,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )

    def run_step_4_from_floor_1(self) -> FunctionThreeStepFourResult:
        started = time.monotonic()
        result = self.step_four.run_from_floor_1()
        return FunctionThreeStepFourResult(
            profile_id=self.context.profile_id,
            roses_floor_1_planted=int(result.roses_floor_1_planted),
            roses_floor_6_planted=int(result.roses_floor_6_planted),
            roses_harvested=int(result.roses_harvested),
            rose_oils=int(result.rose_oils),
            progress_steps=4,
            total_steps=self.TOTAL_DEFINED_STEPS,
            end_floor=1,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )

    def run_step_5_from_floor_1(self) -> FunctionThreeStepFiveResult:
        started = time.monotonic()
        result = self.step_five.run_from_floor_1()
        return FunctionThreeStepFiveResult(
            profile_id=self.context.profile_id,
            snow_floor_1_planted=int(result.snow_floor_1_planted),
            snow_floor_6_planted=int(result.snow_floor_6_planted),
            snow_harvested=int(result.snow_harvested),
            iced_teas=int(result.iced_teas),
            progress_steps=5,
            total_steps=self.TOTAL_DEFINED_STEPS,
            end_floor=1,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )

    def run_steps_1_and_2(self) -> FunctionThreeStepsOneTwoResult:
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

    def run_steps_1_2_3_4_and_5(self) -> FunctionThreeStepsOneTwoThreeFourFiveResult:
        started = time.monotonic()
        step_one = self.step_one.run_from_main()
        step_two = self.step_two.run_from_floor_1()
        step_three = self.step_three.run_from_floor_2()
        step_four = self.step_four.run_from_floor_1()
        step_five = self.step_five.run_from_floor_1()
        return FunctionThreeStepsOneTwoThreeFourFiveResult(
            profile_id=self.context.profile_id,
            apples_floor_1_to_5=int(step_one.replanted_five_floors),
            apples_floor_6=int(step_one.replanted_floor_6),
            dried_teas=int(step_one.produced_count),
            harvested_teas=int(step_two.harvested_tea),
            planted_teas=int(step_two.planted_tea),
            apple_juices=int(step_two.apple_juices),
            harvested_tea_bottom_row=int(step_three.harvested_tea_bottom_row),
            planted_tea_bottom_row=int(step_three.planted_tea_bottom_row),
            cotton_planted=int(step_three.cotton_planted),
            yellow_fabrics=int(step_three.yellow_fabrics),
            roses_floor_1_planted=int(step_four.roses_floor_1_planted),
            roses_floor_6_planted=int(step_four.roses_floor_6_planted),
            roses_harvested=int(step_four.roses_harvested),
            rose_oils=int(step_four.rose_oils),
            snow_floor_1_planted=int(step_five.snow_floor_1_planted),
            snow_floor_6_planted=int(step_five.snow_floor_6_planted),
            snow_harvested=int(step_five.snow_harvested),
            iced_teas=int(step_five.iced_teas),
            progress_steps=5,
            total_steps=self.TOTAL_DEFINED_STEPS,
            end_floor=1,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )

    def run_steps_1_2_3_and_4(self) -> FunctionThreeStepsOneTwoThreeFourFiveResult:
        """Compatibility DEV gate: historical name now runs Step 1→2→3→4→5."""
        return self.run_steps_1_2_3_4_and_5()

    def run_steps_1_2_and_3(self) -> FunctionThreeStepsOneTwoThreeFourFiveResult:
        """Compatibility DEV gate: historical name now runs Step 1→2→3→4→5."""
        return self.run_steps_1_2_3_4_and_5()

    def run(self):
        raise RuntimeError(
            "Function 3 chưa được nối vào AUTO chính: Step 1-5 đã được định nghĩa; "
            "chờ operator mô tả phần tiếp theo"
        )
