from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation
from ...errors import ScreenTimeout
from ...recipes.rose_oil import RoseOilRecipe
from ..auto_function_one import FunctionOneWorkflow


__all__ = ["FunctionTwoResult", "FunctionTwoWorkflow"]
FILE_FUNCTIONS = (
    "Kế thừa nguyên vòng Function 1 đã xác minh",
    "Yêu cầu Function 1 PASS đầy đủ trước khi thêm nhánh TDHH",
    "Từ exact-main trồng/thu hồi đủ 35 Hồng + 28 Tuyết",
    "Đi candidate tầng 7 về tầng 5 và sản xuất đúng 7 TDHH",
    "Sửa máy TDHH rồi trả camera về exact-main trước PASS",
    "Khóa Function 2 ở 1000x1000 trong planting action để không mở lại nhánh 500x500",
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
    """Function 2 = proven Function 1 + 35 Hồng + 28 Tuyết + 7 TDHH."""

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context
        self.base = FunctionOneWorkflow(automation)
        self.rose_oil = RoseOilRecipe(automation)

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

    def run(self) -> FunctionTwoResult:
        started = time.monotonic()
        self.context.stage("auto-function-2-start")
        self.context.log(
            "AUTO Function 2 • START • kế thừa Function 1 rồi thêm "
            "35 Hồng + 28 Tuyết + 7 Tinh dầu hoa hồng"
        )

        base = self.base.run()
        self._validate_base(base)
        self.context.ensure_running()
        self.context.stage("auto-function-2-progress-3-of-4")
        self.context.log(
            "AUTO Function 2 • base PASS 3/4 • Function 1 hoàn tất và đang exact-main"
        )

        if not self.auto.popup.is_own_exact_main_screen():
            raise ScreenTimeout(
                "Function 2 base đã trả về nhưng chưa chứng minh exact-main trước TDHH"
            )

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
