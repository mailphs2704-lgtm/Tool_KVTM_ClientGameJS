from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation
from ...errors import ScreenTimeout
from ..auto_apple_dryer import AppleDryerWorkflow


__all__ = ["FunctionOneResult", "FunctionOneWorkflow"]
FILE_FUNCTIONS = (
    "Chạy phần Táo sấy đã live-pass",
    "Chờ chín, thu hoạch và gieo lại ba mươi Táo tầng 1-5",
    "Đi từ tầng 1 lên tầng 6 rồi xử lý đúng hàng dưới cùng",
    "Chỉ exact-check main sau transition giữa lượt trồng/sản xuất",
    "Về màn hình chính, lên tầng 2 và sản xuất chín Nước táo",
    "Về màn hình chính, gieo 27 Bông rồi lên tầng 3 sản xuất chín Vải vàng",
    "Chỉ PASS 3/3 sau khi hậu kiểm đủ chín Vải vàng",
    "Sau PASS 3/3, normalize tầng 3 về main bằng từng nhịp goDown + exact-main gate",
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

    END_LOOP_MAIN_MAX_SWIPES = 6

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context

    def _require_main_transition(self, label: str) -> None:
        """Exact main gate only after an explicit business floor transition."""
        self.context.ensure_running()
        if not self.auto.popup.is_own_main_screen():
            raise ScreenTimeout(
                f"Điều hướng {label} đã kết thúc nhưng chưa xác nhận màn hình chính; "
                "dừng trước lượt trồng/sản xuất kế tiếp"
            )
        self.context.log(
            f"AUTO transition check • {label} • exact main PASS"
        )

    def _normalize_end_of_loop_to_main(self) -> None:
        """Return a completed Function 1 loop to a repeatable main-screen state.

        The route does not assume a fixed number of down swipes. After every
        single gesture it asks the proven exact own-main classifier. Six gestures
        are only a safety bound; if the classifier never passes we stop rather
        than starting the next Function loop from an unknown floor.
        """
        self.context.stage("auto-function-1-end-loop-main-normalize")
        self.context.ensure_running()
        if self.auto.popup.is_own_main_screen():
            self.context.log(
                "AUTO chức năng 1 • cuối vòng đã ở main • không cần goDown"
            )
            return

        for ordinal in range(1, self.END_LOOP_MAIN_MAX_SWIPES + 1):
            self.context.ensure_running()
            self.auto.function_one_pass_three_navigation.go_down_one_toward_main(
                f"function1-end-loop-goDown(1)-{ordinal}"
            )
            if self.auto.popup.is_own_main_screen():
                self.context.stage("auto-function-1-end-loop-main-ready")
                self.context.log(
                    "AUTO chức năng 1 • cuối vòng về main PASS • "
                    f"goDown={ordinal}"
                )
                return

        raise ScreenTimeout(
            "Function 1 đã PASS sản xuất nhưng không xác nhận được main sau "
            f"{self.END_LOOP_MAIN_MAX_SWIPES} nhịp goDown; "
            "dừng trước vòng Function tiếp theo/bán VP"
        )

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
        self._require_main_transition("sau trồng Táo tầng 6 → trước SX Nước táo")
        self.auto.function_one_navigation.main_to_floor_2()
        juice = self.auto.apple_juice_production.produce_9_apple_juices()
        self.context.stage("auto-function-1-progress-2-of-3")
        self.context.log(
            "AUTO chức năng 1 • TẠM PASS 2/3 • đủ 9 Táo sấy + 9 Nước táo; "
            "bắt đầu chuỗi Bông → Vải vàng"
        )

        self.auto.function_one_pass_three_navigation.floor_2_to_main()
        self._require_main_transition("sau SX Nước táo → trước trồng Bông")
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

        # A Function is repeatable only after it returns to the stable main state.
        self._normalize_end_of_loop_to_main()

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
