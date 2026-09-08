from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation


__all__ = ["AppleDryerResult", "AppleDryerWorkflow"]
FILE_FUNCTIONS = (
    "Nhận camera startup đã được GameSession bàn giao, không gate main lần hai",
    "Trồng đúng 27 cây Táo bằng action mới",
    "Giữ mốc tầng 1 và xác minh đúng máy sấy",
    "Xếp đúng chín Táo sấy rồi trả kế toán",
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
    """First end-to-end clean production function for AUTO MULTI DEV."""

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context

    def run(self, timeout: float = 120.0) -> AppleDryerResult:
        started = time.monotonic()
        self.context.stage("auto-apple-dryer-start")
        # Startup state classification belongs to GameSession. Do not re-run an
        # exact-main gate here: the current contract checks exact state only
        # after explicit inter-stage floor transitions.
        self.context.log(
            "AUTO Táo sấy • nhận startup route từ session • không check main lặp lại"
        )
        planted = self.auto.planting.plant_27_apples()
        self.context.ensure_running()
        self.context.stage("auto-apple-plant-finished")

        produced = self.auto.production.produce_9_dried_apples()
        self.context.ensure_running()
        self.context.stage("auto-dried-apple-production-finished")
        return AppleDryerResult(
            profile_id=self.context.profile_id,
            planted_count=planted,
            produced_count=produced.queued_count,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )
