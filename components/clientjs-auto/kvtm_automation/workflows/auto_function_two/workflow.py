from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation
from ...errors import ScreenTimeout
from ...recipes import RecipeBook
from ..auto_function_one import FunctionOneWorkflow


__all__ = ["FunctionTwoResult", "FunctionTwoWorkflow"]
FILE_FUNCTIONS = (
    "Kế thừa phần lõi Function 1 qua composition, không copy business actions",
    "Yêu cầu Function 1 core PASS 3/3 trước nhánh TDHH",
    "Dùng một RecipeBook function_2 để chia sẻ RecoveryManager",
    "Nhận handoff known floor 3 sau Vải vàng rồi đi deterministic floor3 → MAIN",
    "RoseOilRecipe ghép 35 Hồng + 28 Tuyết bằng PlantingActions dùng chung",
    "Tuyết kết thúc tại floor1 rồi goUp(4) thẳng candidate floor5; không có floor7 giả",
    "Sản xuất đúng 7 TDHH, sửa máy và trở về exact-main trước PASS",
    "Function 2 materials khóa native 1000x1000 tại Recipe boundary",
)


@dataclass(frozen=True)
class FunctionTwoResult:
    profile_id: str
    dried_apples: int
    apple_juices: int
    cotton_planted: int
    yellow_fabrics: int
    roses_planted: int
    snow_planted: int
    rose_oils: int
    progress_steps: int
    total_steps: int
    elapsed_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


class FunctionTwoWorkflow:
    """Function 2 = Function 1 core + RoseOilRecipe, with explicit handoff states."""

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context
        self.recipes = RecipeBook(
            automation,
            function_id="function_2",
        )
        self.base = FunctionOneWorkflow(
            automation,
            recipes=self.recipes,
        )
        self.recovery = self.recipes.recovery
        self.rose_oil = self.recipes.rose_oil
        if self.rose_oil is None:
            raise RuntimeError("Function 2 RecipeBook thiếu RoseOilRecipe")

    @staticmethod
    def _validate_base(result) -> None:
        if (
            int(result.progress_steps) != 3
            or int(result.total_steps) != 3
            or int(result.dried_apples) != 9
            or int(result.apple_juices) != 9
            or int(result.cotton_planted) != 27
            or int(result.yellow_fabrics) != 9
        ):
            raise RuntimeError(
                "Function 2 từ chối kế thừa vì Function 1 chưa đạt contract PASS"
            )

    def _base_handoff_to_main(self) -> None:
        self.context.stage("auto-function-2-base-handoff-main")
        self.context.ensure_running()
        self.recovery.to_main_from_floor(
            3,
            "Function 2 handoff sau Vải vàng",
        )
        self.context.ensure_running()
        if not self.auto.popup.is_own_exact_main_screen():
            raise ScreenTimeout(
                "Function 2 handoff floor3 → MAIN chưa chứng minh exact-main"
            )
        self.context.stage("auto-function-2-base-handoff-main-ready")
        self.context.log(
            "AUTO Function 2 • HANDOFF PASS • known floor3 sau Vải vàng → exact-main"
        )

    def run(self) -> FunctionTwoResult:
        started = time.monotonic()
        self.context.stage("auto-function-2-start")
        self.context.log(
            "AUTO Function 2 • START • Function 1 core → "
            "35 Hồng + 28 Tuyết + 7 Tinh dầu hoa hồng"
        )

        base = self.base.run(normalize_end_to_main=False)
        self._validate_base(base)
        self.context.ensure_running()
        self.context.stage("auto-function-2-progress-3-of-4")
        self.context.log(
            "AUTO Function 2 • base PASS 3/4 • handoff known floor3 sau Vải vàng"
        )

        self._base_handoff_to_main()

        extra = self.rose_oil.run_from_main(count=7)
        if (
            int(extra.rose_planted) != 35
            or int(extra.snow_planted) != 28
            or int(extra.queued_count) != 7
        ):
            raise RuntimeError(
                "Function 2 TDHH contract FAIL: "
                f"Hồng={extra.rose_planted}/35, "
                f"Tuyết={extra.snow_planted}/28, TDHH={extra.queued_count}/7"
            )
        self.context.action("Gieo thành công 35 hồng")
        self.context.action("Gieo thành công 28 tuyết")
        self.context.action("Sản xuất 7 tinh dầu hoa hồng")
        self.context.ensure_running()
        if not self.auto.popup.is_own_exact_main_screen():
            raise ScreenTimeout(
                "Function 2 TDHH đã xong nhưng chưa trở về exact-main"
            )

        self.context.stage("auto-function-2-progress-4-of-4")
        self.context.log(
            "AUTO Function 2 • PASS 4/4 • 9 Táo sấy + 9 Nước táo + "
            "9 Vải vàng + 35 Hồng + 28 Tuyết + 7 TDHH"
        )
        return FunctionTwoResult(
            profile_id=self.context.profile_id,
            dried_apples=int(base.dried_apples),
            apple_juices=int(base.apple_juices),
            cotton_planted=int(base.cotton_planted),
            yellow_fabrics=int(base.yellow_fabrics),
            roses_planted=int(extra.rose_planted),
            snow_planted=int(extra.snow_planted),
            rose_oils=int(extra.queued_count),
            progress_steps=4,
            total_steps=4,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )
