from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation
from ...errors import ScreenTimeout
from ...recipes import RecipeBook


__all__ = ["FunctionOneResult", "FunctionOneWorkflow"]
FILE_FUNCTIONS = (
    "Function chỉ ghép các Recipe nghiệp vụ thay vì tự chứa production/recovery chi tiết",
    "Gọi DriedAppleRecipe cho trồng Táo + SX Táo sấy + Sửa máy",
    "Giữ supply Táo tầng 1-6 riêng của Function 1 rồi bàn giao candidate tầng 2 cho AppleJuiceRecipe",
    "Dùng FarmRouteActions dùng chung; Function không sở hữu primitive điều hướng riêng",
    "AppleJuiceRecipe tự probe nuoc_tao, fallback exact-main, xử lý sai máy/kho đầy và Sửa máy",
    "YellowFabricRecipe nhận trạng thái sau Nước táo, về main, trồng Bông, vào tầng 3, SX và Sửa máy",
    "Function 1 standalone đưa tầng 3 về exact-main trước PASS",
    "Cho phép Function kế thừa inject RecipeBook và nhận handoff sau Vải vàng trước bước kết vòng riêng",
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
    """Function 1 business flow composed from reusable product recipes."""

    def __init__(
        self,
        automation: KVAutomation,
        *,
        recipes: RecipeBook | None = None,
    ) -> None:
        self.auto = automation
        self.context = automation.context
        if recipes is None:
            self.recipes = RecipeBook(
                automation,
                function_id="function_1",
            )
        else:
            self.recipes = recipes
        self.recovery = self.recipes.recovery

    def _require_main_transition(self, label: str) -> None:
        self.context.ensure_running()
        if not self.auto.popup.is_own_exact_main_screen():
            raise ScreenTimeout(
                f"Điều hướng {label} đã kết thúc nhưng chưa xác nhận exact-main; "
                "dừng trước bước Function kế tiếp"
            )
        self.context.log(f"AUTO transition check • {label} • exact main PASS")

    def _normalize_end_of_loop_to_main(self) -> None:
        self.context.stage("auto-function-1-end-loop-main-normalize")
        self.context.ensure_running()
        self.recovery.to_main_from_floor(
            3,
            "cuối vòng Function 1",
        )
        self._require_main_transition("cuối vòng Function 1 tầng 3 → main")
        self.context.stage("auto-function-1-end-loop-main-ready")
        self.context.log(
            "AUTO chức năng 1 • cuối vòng về main PASS qua RecoveryManager"
        )

    def run(
        self,
        *,
        normalize_end_to_main: bool = True,
    ) -> FunctionOneResult:
        started = time.monotonic()
        self.context.stage("auto-function-1-recipe-chain-start")
        self.context.log(
            "AUTO chức năng 1 • bắt đầu Recipe chain • "
            "tùy chọn scheduler đã được xử lý ở safe boundary"
        )

        dried_already_done = self.recovery.cycle.has("function-1-dried-apple")
        dried_recipe = self.recovery.cycle.run_once(
            "function-1-dried-apple",
            label="Function 1 • Táo sấy",
            runner=lambda: self.recipes.dried_apple.run_from_session(count=9),
            on_replay=self.auto.farm_routes.main_to_floor_1,
        )
        self.context.ensure_running()
        self.context.stage("auto-function-1-progress-1-of-3")
        if not dried_already_done:
            self.context.action("Sản xuất 9 táo sấy")
        self.context.log(
            "AUTO chức năng 1 • tiến độ 1/3 • DriedAppleRecipe PASS"
        )

        def replenish_five_floors() -> int:
            self.auto.apple_supply.wait_until_floor_1_ripe()
            return int(self.auto.apple_supply.harvest_and_replant_five_floors())

        apple_five_already_done = self.recovery.cycle.has(
            "function-1-apple-floor-1-to-5"
        )
        five_floors = self.recovery.cycle.run_once(
            "function-1-apple-floor-1-to-5",
            label="Function 1 • Táo tầng 1-5",
            runner=replenish_five_floors,
        )
        self.context.stage("auto-apple-five-floors-replanted")

        self.auto.farm_routes.floor_1_to_floor_6()
        apple_six_already_done = self.recovery.cycle.has(
            "function-1-apple-floor-6"
        )
        floor_6 = self.recovery.cycle.run_once(
            "function-1-apple-floor-6",
            label="Function 1 • Táo tầng 6",
            runner=self.auto.apple_supply.harvest_and_replant_floor_6_row,
        )
        self.context.stage("auto-apple-floor-6-replanted")
        if not (apple_five_already_done and apple_six_already_done):
            self.context.action("Gieo thành công 36 táo")

        self.auto.farm_routes.floor_6_to_floor_2()
        juice_already_done = self.recovery.cycle.has("function-1-apple-juice")
        juice_recipe = self.recovery.cycle.run_once(
            "function-1-apple-juice",
            label="Function 1 • Nước táo",
            runner=lambda: self.recipes.apple_juice.run_from_candidate_floor_2(count=9),
        )
        juice = juice_recipe.production
        self.context.ensure_running()
        self.context.stage("auto-function-1-progress-2-of-3")
        if not juice_already_done:
            self.context.action("Sản xuất 9 nước táo")
        if juice_recipe.candidate_verified:
            route_note = "direct candidate nuoc_tao PASS"
        elif juice_recipe.fallback_used:
            route_note = "candidate MISS → RecoveryManager fallback PASS"
        else:
            route_note = "current floor2 production PASS"
        self.context.log(
            "AUTO chức năng 1 • TẠM PASS 2/3 • AppleJuiceRecipe PASS • "
            f"{route_note}"
        )

        fabric_already_done = self.recovery.cycle.has(
            "function-1-yellow-fabric"
        )
        fabric_recipe = self.recovery.cycle.run_once(
            "function-1-yellow-fabric",
            label="Function 1 • Vải vàng",
            runner=lambda: self.recipes.yellow_fabric.run_after_floor_2(count=9),
            on_replay=lambda: self.recovery.from_floor_to_floor(
                2, 3, "Function 1 replay Vải vàng đã PASS"
            ),
        )
        cotton = fabric_recipe.cotton_planted
        fabric = fabric_recipe.production
        self.context.ensure_running()
        self.context.stage("auto-function-1-progress-3-of-3")
        if not fabric_already_done:
            self.context.action("Gieo thành công 27 bông")
            self.context.action("Sản xuất 9 vải vàng")
        self.context.log(
            "AUTO chức năng 1 • PASS 3/3 • Recipe chain hoàn tất: "
            "Táo sấy + Nước táo + 27 Bông + Vải vàng"
        )

        if normalize_end_to_main:
            self._normalize_end_of_loop_to_main()
        else:
            self.context.stage("auto-function-1-handoff-after-yellow-fabric")
            self.context.log(
                "AUTO chức năng 1 • HANDOFF • giữ candidate sau Vải vàng; "
                "Function kế thừa tự chịu trách nhiệm recovery về exact-main"
            )

        return FunctionOneResult(
            profile_id=self.context.profile_id,
            first_plant_count=dried_recipe.planted_count,
            replanted_five_floors=five_floors,
            replanted_floor_6=floor_6,
            dried_apples=dried_recipe.produced_count,
            apple_juices=juice.queued_count,
            cotton_planted=cotton,
            yellow_fabrics=fabric.queued_count,
            progress_steps=3,
            total_steps=3,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )
