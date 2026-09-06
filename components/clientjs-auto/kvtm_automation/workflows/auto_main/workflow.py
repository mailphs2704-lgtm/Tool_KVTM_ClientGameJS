from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation
from ..auto_apple_dryer import AppleDryerWorkflow
from ..auto_vp_sale import AutoVpSaleWorkflow


__all__ = ["AutoMainResult", "AutoMainWorkflow"]
FILE_FUNCTIONS = (
    "Chạy bán VP đã PASS trước khi trồng",
    "Chạy chức năng đầu tiên: trồng 27 Táo và sản xuất 9 Táo sấy",
    "Dừng toàn bộ chuỗi nếu một giao dịch con thất bại",
    "Trả kế toán tổng hợp cho một nút Bắt đầu AUTO MULTI DEV",
)


@dataclass(frozen=True)
class AutoMainResult:
    profile_id: str
    sold_listings: int
    collected_gold_slots: int
    planted_count: int
    produced_count: int
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

        apple = AppleDryerWorkflow(self.auto).run(timeout=120.0)
        self.context.ensure_running()
        self.context.stage("auto-main-apple-dryer-finished")

        self.context.log(
            "AUTO MULTI DEV • chức năng 1 hoàn tất • "
            "trồng 27 Táo và sản xuất 9 Táo sấy"
        )
        self.context.stage("auto-main-function-1-finished")
        return AutoMainResult(
            profile_id=self.context.profile_id,
            sold_listings=sale.sold_listings,
            collected_gold_slots=sale.collected_gold_slots,
            planted_count=apple.planted_count,
            produced_count=apple.produced_count,
            production_ready=apple.produced_count == 9,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )
