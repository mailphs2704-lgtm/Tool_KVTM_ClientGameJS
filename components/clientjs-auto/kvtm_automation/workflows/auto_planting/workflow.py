from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation


__all__ = ["RosePlantingResult", "RosePlantingWorkflow"]
FILE_FUNCTIONS = (
    "Đưa clone về đúng màn hình farm",
    "Gọi module trồng đúng 27 cây Hoa hồng",
    "Trả kết quả và thời gian cho GUI/log",
)


@dataclass(frozen=True)
class RosePlantingResult:
    profile_id: str
    item_id: str
    planted_count: int
    requested_count: int
    elapsed_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


class RosePlantingWorkflow:
    """Isolated first planting layer for the clean AUTO Main."""

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context

    def run(self, timeout: float = 90.0) -> RosePlantingResult:
        started = time.monotonic()
        self.context.stage("auto-rose-plant-start")
        self.auto.ensure_main_screen(timeout=timeout)
        planted = self.auto.planting.plant_27_roses()
        self.context.ensure_running()
        self.context.stage("auto-rose-plant-finished")
        return RosePlantingResult(
            profile_id=self.context.profile_id,
            item_id="cay_hong",
            planted_count=planted,
            requested_count=27,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )
