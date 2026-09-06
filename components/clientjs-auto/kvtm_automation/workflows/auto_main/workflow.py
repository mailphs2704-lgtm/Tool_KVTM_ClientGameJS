from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation
from ..auto_planting import RosePlantingWorkflow
from ..auto_vp_sale import AutoVpSaleWorkflow


__all__ = ["AutoMainResult", "AutoMainWorkflow"]
FILE_FUNCTIONS = (
    "Chạy bán VP đã PASS trước khi trồng",
    "Chạy trồng đúng 27 Hoa hồng sau khi bán",
    "Dừng toàn bộ chuỗi nếu một giao dịch con thất bại",
    "Trả kế toán tổng hợp cho một nút Bắt đầu AUTO MULTI DEV",
)


@dataclass(frozen=True)
class AutoMainResult:
    profile_id: str
    sold_listings: int
    collected_gold_slots: int
    planted_count: int
    production_ready: bool
    elapsed_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


class AutoMainWorkflow:
    """One deterministic pipeline behind the consolidated Multi DEV start button."""

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context

    def run(self) -> AutoMainResult:
        started = time.monotonic()
        self.context.stage("auto-main-pipeline-start")

        sale = AutoVpSaleWorkflow(self.auto).run(timeout=120.0)
        self.context.ensure_running()
        self.context.stage("auto-main-sale-finished")

        planting = RosePlantingWorkflow(self.auto).run(timeout=90.0)
        self.context.ensure_running()
        self.context.stage("auto-main-planting-finished")

        self.context.log(
            "AUTO MULTI DEV • bán và trồng hoàn tất • "
            "READY cho quét tầng/máy sản xuất"
        )
        self.context.stage("auto-main-production-ready")
        return AutoMainResult(
            profile_id=self.context.profile_id,
            sold_listings=sale.sold_listings,
            collected_gold_slots=sale.collected_gold_slots,
            planted_count=planting.planted_count,
            production_ready=True,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )
