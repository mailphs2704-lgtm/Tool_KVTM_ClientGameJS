from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation
from ...errors import ScreenTimeout


__all__ = ["RosePlantingResult", "RosePlantingWorkflow"]
FILE_FUNCTIONS = (
    "Yêu cầu exact-main từ caller, không tự normalize camera ẩn",
    "Gọi Navigation Action goUp(1) riêng",
    "Gọi Planting Action trồng/thu hoạch 27 Hoa hồng trên view hiện tại",
    "Trả result tương thích GUI/log",
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
    """Isolated planting adapter composed from shared Navigation + Planting Actions."""

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context

    def run(self, timeout: float = 90.0) -> RosePlantingResult:
        del timeout
        started = time.monotonic()
        self.context.stage("auto-rose-plant-start")
        if not self.auto.popup.is_own_exact_main_screen():
            raise ScreenTimeout(
                "Module trồng Hoa hồng cần exact-main từ bước trước; "
                "không tự goDown/normalize camera"
            )
        self.auto.floors.go_up(1, label="rose-plant-main-to-floor1")
        planted = self.auto.planting.plant_current_view(
            seed_template=self.auto.planting.ROSE_TEMPLATE,
            item_label="Hoa hồng",
            count=27,
        )
        self.context.ensure_running()
        self.context.stage("auto-rose-plant-finished")
        return RosePlantingResult(
            profile_id=self.context.profile_id,
            item_id="cay_hong",
            planted_count=int(planted),
            requested_count=27,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )
