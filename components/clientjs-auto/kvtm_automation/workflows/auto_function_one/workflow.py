from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation
from ...errors import ScreenTimeout
from ..auto_apple_dryer import AppleDryerWorkflow
from ..production_warehouse_recovery import ProductionWarehouseRecovery


__all__ = ["FunctionOneResult", "FunctionOneWorkflow"]
FILE_FUNCTIONS = (
    "Chạy phần Táo sấy đã live-pass và Sửa máy ngay sau production",
    "Chờ chín, thu hoạch và gieo lại ba mươi Táo tầng 1-5",
    "Đi từ tầng 1 lên tầng 6 rồi xử lý đúng hàng dưới cùng",
    "Sau tầng 6 đi thẳng goDown(4) tới candidate tầng 2 và xác minh bằng anchor Nước táo",
    "Nếu direct tầng 2 lệch: đóng panel, recovery exact-main rồi goUp(1)x2 và retry",
    "Nếu kho đầy trong production: xuống quầy bán VP, quay lại đúng tầng và retry đúng máy",
    "Sau Nước táo về main, gieo 27 Bông rồi dùng true goUp(2) lên tầng 3",
    "Chỉ PASS 3/3 sau khi hậu kiểm đủ chín Vải vàng và Sửa máy",
    "Sau mỗi vòng: tầng 3 → goDown(1) → click xuống tầng → exact-main PASS",
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

    DIRECT_JUICE_MAIN_RECOVERY_PASSES = 6

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context
        self.warehouse_recovery = ProductionWarehouseRecovery(
            automation, function_id="function_1"
        )

    def _require_main_transition(self, label: str) -> None:
        """Exact main gate only after an explicit business floor transition."""
        self.context.ensure_running()
        if not self.auto.popup.is_own_exact_main_screen():
            raise ScreenTimeout(
                f"Điều hướng {label} đã kết thúc nhưng chưa xác nhận exact-main; "
                "dừng trước lượt trồng/sản xuất kế tiếp"
            )
        self.context.log(
            f"AUTO transition check • {label} • exact main PASS"
        )

    def _recover_direct_juice_miss_to_floor_2(self) -> None:
        """Fail-safe for a floor6->floor2 direct route that misses nuoc_tao.

        The failed probe has already closed its panel. Normalize the unknown
        camera with the existing background-independent goDown/XUỐNG/boundary
        recovery, require exact main, then use the stable two x goUp(1) route to
        floor 2. Only then may the normal production transaction retry.
        """
        self.context.stage("auto-function-1-direct-juice-floor-fallback")
        self.context.invalidate_camera_main("direct-juice-floor-anchor-miss")
        self.context.log(
            "AUTO Nước táo • direct goDown(4) chưa chứng minh được tầng 2 • "
            "fallback: exact-main runtime recovery → goUp(1)x2"
        )

        for attempt in range(1, self.DIRECT_JUICE_MAIN_RECOVERY_PASSES + 1):
            self.context.ensure_running()
            if self.auto.popup.is_own_exact_main_screen():
                break
            self.auto.function_one_pass_three_navigation.go_down_one_toward_main(
                f"function1-direct-juice-fallback-{attempt}-of-"
                f"{self.DIRECT_JUICE_MAIN_RECOVERY_PASSES}"
            )
            if self.auto.popup.is_own_exact_main_screen():
                break
        else:
            raise ScreenTimeout(
                "Fallback Nước táo không chứng minh được exact-main sau "
                f"{self.DIRECT_JUICE_MAIN_RECOVERY_PASSES} lượt recovery; "
                "dừng trước khi chọn máy"
            )

        self._require_main_transition("fallback direct Nước táo → exact-main")
        self.auto.function_one_navigation.main_to_floor_2()
        self.context.stage("auto-function-1-direct-juice-floor2-recovered")
        self.context.log(
            "AUTO Nước táo • fallback PASS • exact-main → goUp(1)x2 → tầng 2 candidate "
            "• bàn giao production xác minh nuoc_tao lần nữa"
        )

    def _normalize_end_of_loop_to_main(self) -> None:
        """Return the completed floor-3 loop to exact own-main state.

        Operator-confirmed route: exactly one goDown(1), then click the down-floor
        button recovered from AUTO PRO goDownLast. Navigation requires fresh-frame
        response and this workflow immediately requires exact own-main before the
        Scheduler can count the loop or start the next Function/sale cycle.
        """
        self.context.stage("auto-function-1-end-loop-main-normalize")
        self.context.ensure_running()
        self.auto.function_one_pass_three_navigation.floor_3_to_main_via_down_floor()
        self._require_main_transition("cuối vòng Function 1 tầng 3 → main")
        self.context.stage("auto-function-1-end-loop-main-ready")
        self.context.log(
            "AUTO chức năng 1 • cuối vòng về main PASS • "
            "goDown(1) → click xuống tầng → exact main"
        )

    def run(self) -> FunctionOneResult:
        started = time.monotonic()
        self.context.stage("auto-function-1-optional-check")
        self.context.log("AUTO chức năng 1 • check tùy chọn: chưa cấu hình • bỏ qua")

        dried = AppleDryerWorkflow(self.auto).run(timeout=120.0)
        self.context.ensure_running()
        self.context.stage("auto-function-1-progress-1-of-3")
        self.context.log(
            "AUTO chức năng 1 • tiến độ 1/3 • đủ 9 Táo sấy + Sửa máy PASS"
        )

        self.auto.apple_supply.wait_until_floor_1_ripe()
        five_floors = self.auto.apple_supply.harvest_and_replant_five_floors()
        self.context.stage("auto-apple-five-floors-replanted")

        self.auto.function_one_navigation.floor_1_to_floor_6()
        floor_6 = self.auto.apple_supply.harvest_and_replant_floor_6_row()
        self.context.stage("auto-apple-floor-6-replanted")

        # Fast path: one goDown(4) should land directly at the floor-2 juice
        # machine. The route is accepted only after a bounded machine probe sees
        # the exact nuoc_tao product anchor. A miss never loops clicks forever;
        # it closes the panel and normalizes to exact main before retrying floor 2.
        self.auto.function_one_navigation.floor_6_to_floor_2()
        direct_floor_2 = self.auto.apple_juice_production.probe_floor_2_machine()
        if not direct_floor_2:
            self._recover_direct_juice_miss_to_floor_2()
        else:
            self.context.stage("auto-function-1-direct-juice-floor2-verified")
            self.context.log(
                "AUTO chức năng 1 • đường nhanh tầng 6 → tầng 2 PASS bằng anchor nuoc_tao "
                "• bỏ vòng main không cần thiết"
            )

        juice = self.warehouse_recovery.run_production(
            floor=2,
            label="Nước táo",
            producer=lambda: self.auto.apple_juice_production.produce_9_apple_juices(
                close_after_success=False
            ),
        )
        self.auto.machine_repair.repair_after_production(juice)
        self.context.ensure_running()
        self.context.stage("auto-function-1-apple-juice-machine-repaired")
        self.context.stage("auto-function-1-progress-2-of-3")
        self.context.log(
            "AUTO chức năng 1 • TẠM PASS 2/3 • đủ 9 Táo sấy + 9 Nước táo; "
            "Nước táo đã Sửa máy • bắt đầu chuỗi Bông → Vải vàng"
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
        fabric = self.warehouse_recovery.run_production(
            floor=3,
            label="Vải vàng",
            producer=lambda: self.auto.yellow_fabric_production.produce_9_yellow_fabrics(
                close_after_success=False
            ),
        )
        self.auto.machine_repair.repair_after_production(fabric)
        self.context.ensure_running()
        self.context.stage("auto-function-1-yellow-fabric-machine-repaired")
        self.context.stage("auto-function-1-progress-3-of-3")
        self.context.log(
            "AUTO chức năng 1 • PASS 3/3 • đủ 9 Táo sấy + 9 Nước táo + "
            "27 Bông đã gieo + 9 Vải vàng; cả 3 máy đã Sửa máy PASS"
        )

        # A Function loop is complete only after it returns to exact main.
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
