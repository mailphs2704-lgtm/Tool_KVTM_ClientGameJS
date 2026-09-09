from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation
from ..production_warehouse_recovery import ProductionWarehouseRecovery


__all__ = ["AppleDryerResult", "AppleDryerWorkflow"]
FILE_FUNCTIONS = (
    "Nhận camera startup đã được GameSession bàn giao, không gate main lần hai",
    "Trồng đúng 27 cây Táo bằng action mới",
    "Giữ mốc tầng 1 và xác minh đúng máy sấy",
    "Nếu kho đầy khi thu VP: xuống quầy bán VP rồi quay lại đúng tầng 1, không trồng lại",
    "Xếp đúng chín Táo sấy rồi giữ panel mở",
    "Sau hậu kiểm 9/9, gọi module Sửa máy live-pass trước khi rời máy",
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
        self.warehouse_recovery = ProductionWarehouseRecovery(
            automation, function_id="function_1"
        )

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

        produced = self.warehouse_recovery.run_production(
            floor=1,
            label="Táo sấy",
            producer=lambda: self.auto.production.produce_9_dried_apples(
                close_after_success=False
            ),
        )
        self.context.ensure_running()
        self.context.stage("auto-dried-apple-production-finished")
        self.auto.machine_repair.repair_after_production(produced)
        self.context.ensure_running()
        self.context.stage("auto-dried-apple-machine-repaired")
        self.context.log(
            "AUTO Táo sấy • sản xuất 9/9 + Sửa máy PASS"
        )
        return AppleDryerResult(
            profile_id=self.context.profile_id,
            planted_count=planted,
            produced_count=produced.queued_count,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )
