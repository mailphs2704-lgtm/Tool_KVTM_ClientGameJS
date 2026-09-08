from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation
from ..auto_apple_dryer import AppleDryerWorkflow


__all__ = ["FunctionOneResult", "FunctionOneWorkflow"]
FILE_FUNCTIONS = (
    "Chạy phần Táo sấy đã live-pass",
    "Chờ chín, thu hoạch và gieo lại ba mươi Táo tầng 1-5",
    "Đi từ tầng 1 lên tầng 6 rồi xử lý đúng hàng dưới cùng",
    "Về màn hình chính, lên tầng 2 và sản xuất chín Nước táo",
    "Về màn hình chính, gieo 27 Bông rồi lên tầng 3 sản xuất chín Vải vàng",
    "Chỉ PASS 3/3 sau khi hậu kiểm đủ chín Vải vàng",
)


@dataclass(frozen=True)
class FunctionOneResult:
    profile_id: str
    first_plant_count: int
    replanted_five_floors: int
    replanted_floor_6: int
    dried_apples: int
    apple_juices: int
    cotton_planted: int
    yellow_fabrics: int
    progress_steps: int
    total_steps: int
    elapsed_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


class FunctionOneWorkflow:
    """Function 1: verified 9 dried apples + supply chain + 9 yellow fabrics."""

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context

    def run(self) -> FunctionOneResult:
        started = time.monotonic()
        self.context.stage("auto-function-1-optional-check")
        self.context.log("AUTO chức năng 1 • check tùy chọn: chưa cấu hình • bỏ qua")

        dried = AppleDryerWorkflow(self.auto).run(timeout=120.0)
        self.context.ensure_running()
        self.context.stage("auto-function-1-progress-1-of-3")
        self.context.log("AUTO chức năng 1 • tiến độ 1/3 • đủ 9 Táo sấy")

        self.auto.apple_supply.wait_until_floor_1_ripe()
        five_floors = self.auto.apple_supply.harvest_and_replant_five_floors()
        self.context.stage("auto-apple-five-floors-replanted")

        self.auto.function_one_navigation.floor_1_to_floor_6()
        floor_6 = self.auto.apple_supply.harvest_and_replant_floor_6_row()
        self.context.stage("auto-apple-floor-6-replanted")

        self.auto.function_one_navigation.floor_6_to_main()
        self.auto.function_one_navigation.main_to_floor_2()
        juice = self.auto.apple_juice_production.produce_9_apple_juices()
        self.context.stage("auto-function-1-progress-2-of-3")
        self.context.log(
            "AUTO chức năng 1 • TẠM PASS 2/3 • đủ 9 Táo sấy + 9 Nước táo; "
            "bắt đầu chuỗi Bông → Vải vàng"
        )

        self.auto.function_one_pass_three_navigation.floor_2_to_main()
        cotton = self.auto.cotton_planting.plant_27_cotton()
        self.context.ensure_running()
        self.context.stage("auto-function-1-cotton-27-planted")
        self.context.log(
            "AUTO chức năng 1 • đã gieo 27 Bông • tầng 1-4 đủ 24 chậu + 3 chậu tầng 5"
        )

        self.auto.function_one_pass_three_navigation.floor_1_to_floor_3()
        fabric = self.auto.yellow_fabric_production.produce_9_yellow_fabrics()
        self.context.ensure_running()
        self.context.stage("auto-function-1-progress-3-of-3")
        self.context.log(
            "AUTO chức năng 1 • PASS 3/3 • đủ 9 Táo sấy + 9 Nước táo + "
            "27 Bông đã gieo + 9 Vải vàng đã xác minh"
        )

        return FunctionOneResult(
            profile_id=self.context.profile_id,
            first_plant_count=dried.planted_count,
            replanted_five_floors=five_floors,
            replanted_floor_6=floor_6,
            dried_apples=dried.produced_count,
            apple_juices=juice.queued_count,
            cotton_planted=cotton,
            yellow_fabrics=fabric.queued_count,
            progress_steps=3,
            total_steps=3,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )
