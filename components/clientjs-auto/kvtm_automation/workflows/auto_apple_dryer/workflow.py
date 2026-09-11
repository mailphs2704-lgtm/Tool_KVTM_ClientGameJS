from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation
from ...recipes import RecipeBook


__all__ = ["AppleDryerResult", "AppleDryerWorkflow"]
FILE_FUNCTIONS = (
    "Legacy/Builder adapter mỏng cho DriedAppleRecipe chuẩn",
    "Không copy planting, production, repair hoặc warehouse recovery trong Workflow",
    "Giữ result shape cũ cho GUI/caller tương thích",
)


@dataclass(frozen=True)
class AppleDryerResult:
    profile_id: str
    planted_count: int
    produced_count: int
    elapsed_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


class AppleDryerWorkflow:
    """Compatibility workflow delegating all business logic to DriedAppleRecipe."""

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context
        self.recipes = RecipeBook(automation, function_id="function_1")

    def run(self, timeout: float = 120.0) -> AppleDryerResult:
        del timeout  # Recipe/action timeouts own their own verified contracts.
        started = time.monotonic()
        self.context.stage("auto-apple-dryer-adapter-start")
        result = self.recipes.dried_apple.run_from_session(count=9)
        self.context.ensure_running()
        self.context.stage("auto-apple-dryer-adapter-finished")
        return AppleDryerResult(
            profile_id=self.context.profile_id,
            planted_count=int(result.planted_count),
            produced_count=int(result.produced_count),
            elapsed_seconds=round(time.monotonic() - started, 3),
        )
