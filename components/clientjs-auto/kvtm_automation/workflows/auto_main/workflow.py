from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation
from ..auto_function_one import FunctionOneWorkflow
from ..auto_vp_sale import AutoVpSaleWorkflow


__all__ = ["AutoMainResult", "AutoMainWorkflow"]
FILE_FUNCTIONS = (
    "Bán đúng VP thuộc chức năng hiện tại trước khi sản xuất",
    "Chạy chuỗi chức năng 1 đủ ba pass kế tiếp nhau",
    "Không tuyên bố hoàn thành trước khi đủ chín Vải vàng",
    "Trả kế toán đầy đủ Táo sấy, Nước táo, Bông và Vải vàng",
)


@dataclass(frozen=True)
class AutoMainResult:
    profile_id: str
    sold_listings: int
    collected_gold_slots: int
    planted_count: int
    produced_count: int
    apple_juice_count: int
    cotton_planted_count: int
    yellow_fabric_count: int
    function_progress_steps: int
    function_total_steps: int
    production_ready: bool
    elapsed_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


class AutoMainWorkflow:
    """Function 1 is complete only after all three verified passes succeed."""

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
        if (
            function_one.progress_steps != 3
            or function_one.total_steps != 3
            or function_one.yellow_fabrics != 9
            or function_one.cotton_planted != 27
        ):
            raise RuntimeError(
                "Function 1 trả kết quả không đạt hợp đồng PASS 3/3"
            )

        self.context.stage("auto-main-function-1-pass-3-of-3")
        self.context.log(
            "AUTO MULTI DEV • PASS 3/3 chức năng 1 • "
            "9 Táo sấy + 9 Nước táo + 27 Bông + 9 Vải vàng"
        )
        return AutoMainResult(
            profile_id=self.context.profile_id,
            sold_listings=sale.sold_listings,
            collected_gold_slots=sale.collected_gold_slots,
            planted_count=function_one.first_plant_count,
            produced_count=function_one.dried_apples,
            apple_juice_count=function_one.apple_juices,
            cotton_planted_count=function_one.cotton_planted,
            yellow_fabric_count=function_one.yellow_fabrics,
            function_progress_steps=function_one.progress_steps,
            function_total_steps=function_one.total_steps,
            production_ready=True,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )
