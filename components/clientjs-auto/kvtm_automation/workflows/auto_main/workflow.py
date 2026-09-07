from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation
from ..auto_function_one import FunctionOneWorkflow
from ..auto_vp_sale import AutoVpSaleWorkflow


__all__ = ["AutoMainResult", "AutoMainWorkflow"]
FILE_FUNCTIONS = (
    "Bán đúng VP thuộc chức năng hiện tại trước khi sản xuất",
    "Chạy chuỗi chức năng 1 đến mốc chín Nước táo",
    "Không tuyên bố hoàn thành trước khi đủ chín Vải vàng",
    "Trả kế toán tiến độ tạm hai trên ba",
)


@dataclass(frozen=True)
class AutoMainResult:
    profile_id: str
    sold_listings: int
    collected_gold_slots: int
    planted_count: int
    produced_count: int
    apple_juice_count: int
    function_progress_steps: int
    function_total_steps: int
    production_ready: bool
    elapsed_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


class AutoMainWorkflow:
    """Function 1 is complete only at 9 dried apples plus 9 yellow fabrics."""

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context

    def run(self) -> AutoMainResult:
        started = time.monotonic()
        self.context.stage("auto-main-pipeline-start")
        sale = AutoVpSaleWorkflow(self.auto).run(timeout=120.0)
        self.context.ensure_running()
        self.context.stage("auto-main-sale-finished")

        function_one = FunctionOneWorkflow(self.auto).run()
        self.context.ensure_running()
        self.context.stage("auto-main-function-1-temp-pass-2-of-3")
        self.context.log(
            "AUTO MULTI DEV • TẠM PASS 2/3 chức năng 1 • "
            "9 Táo sấy + 9 Nước táo; còn bước sản xuất 9 Vải vàng"
        )
        return AutoMainResult(
            profile_id=self.context.profile_id,
            sold_listings=sale.sold_listings,
            collected_gold_slots=sale.collected_gold_slots,
            planted_count=function_one.first_plant_count,
            produced_count=function_one.dried_apples,
            apple_juice_count=function_one.apple_juices,
            function_progress_steps=2,
            function_total_steps=3,
            production_ready=False,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )
