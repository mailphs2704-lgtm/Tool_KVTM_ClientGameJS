from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation
from ..auto_builder.catalog import FunctionSpec, get_function_spec
from ..auto_builder.modules import FunctionModule
from ..auto_vp_sale import AutoVpSaleWorkflow
from .friend_refresh import FriendRefreshWorkflow


__all__ = ["AutoMainResult", "AutoMainWorkflow"]
FILE_FUNCTIONS = (
    "Nhận Function đã chọn từ AUTO MULTI DEV và khóa theo Function catalog",
    "Bán đúng VP thuộc Function ngay sau bước vào game/đóng popup",
    "Chạy Function hoàn chỉnh liên tục cho tới khi operator bấm Dừng",
    "Sau lần bán đầu, chỉ bán lại khi đã hoàn thành đủ số vòng cấu hình",
    "Nếu GUI bật, sau mỗi đúng ba vòng Function chạy maintenance qua nhà bạn #1 rồi quay về",
    "Cho phép chờ riêng giữa hai vòng Function; không áp vào thao tác khác",
    "Giữ stop-check trước từng vòng Function, từng lượt bán, maintenance và thời gian chờ",
    "Fail-close nếu Function chưa có runner runtime hoàn chỉnh",
)


@dataclass(frozen=True)
class AutoMainResult:
    profile_id: str
    function_id: str
    function_label: str
    function_loops: int
    sale_calls: int
    sold_listings: int
    collected_gold_slots: int
    elapsed_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


class AutoMainWorkflow:
    """Continuous verified AUTO scheduler for one selected built-in Function.

    GameSessionWorkflow is intentionally owned by the isolated worker and runs
    before this workflow. Therefore the ordering of a normal AUTO MULTI DEV run
    is fixed as:

        enter game + close popup -> sale #1 -> Function loops -> periodic sales
        -> optional every-3-loop friend round trip

    ``sale_every_loops`` controls only sales #2..N. ``friend_refresh_enabled`` is
    a scheduler-wide maintenance switch, not Function business logic: after every
    three completed Function loops it visits the first friend and returns home to
    rebuild the game scene and clear stale/floating item layers.

    ``function_loop_delay_seconds`` is applied only between completed Function
    loops; it never delays the first loop and is skipped after the final loop of a
    bounded run.
    """

    FRIEND_REFRESH_EVERY_LOOPS = 3

    def __init__(
        self,
        automation: KVAutomation,
        *,
        function_id: str = "function_1",
        sale_every_loops: int = 1,
        function_loop_delay_seconds: float = 0.0,
        friend_refresh_enabled: bool = False,
        max_function_loops: int | None = None,
    ) -> None:
        self.auto = automation
        self.context = automation.context
        self.spec: FunctionSpec = get_function_spec(function_id)
        self.sale_every_loops = int(sale_every_loops)
        if not 1 <= self.sale_every_loops <= 999:
            raise ValueError("sale_every_loops phải trong khoảng 1..999")
        self.function_loop_delay_seconds = float(function_loop_delay_seconds)
        if not 0.0 <= self.function_loop_delay_seconds <= 3600.0:
            raise ValueError("function_loop_delay_seconds phải trong khoảng 0..3600")
        self.friend_refresh_enabled = bool(friend_refresh_enabled)
        self.max_function_loops = (
            None if max_function_loops is None else int(max_function_loops)
        )
        if self.max_function_loops is not None and self.max_function_loops < 1:
            raise ValueError("max_function_loops phải >= 1 khi được cấu hình")
        self.function = FunctionModule(automation)
        self.friend_refresh = FriendRefreshWorkflow(
            automation,
            function_id=self.spec.function_id,
        )
        self.function_loops = 0
        self.sale_calls = 0
        self.sold_listings = 0
        self.collected_gold_slots = 0
        self.friend_refresh_calls = 0

    def _validate_function_result(self, payload: dict) -> None:
        """Keep proven Function-specific completion gates at scheduler boundary."""
        if self.spec.runner_key == "function_1":
            if (
                int(payload.get("progress_steps", 0) or 0) != 3
                or int(payload.get("total_steps", 0) or 0) != 3
                or int(payload.get("yellow_fabrics", 0) or 0) != 9
                or int(payload.get("cotton_planted", 0) or 0) != 27
            ):
                raise RuntimeError(
                    "Function 1 trả kết quả không đạt hợp đồng PASS 3/3"
                )
            return
        raise RuntimeError(
            f"Function chưa có completion gate AUTO Main: {self.spec.function_id}"
        )

    def _sale_once(self, *, ordinal: int) -> None:
        self.context.ensure_running()
        self.context.stage(
            f"auto-main-{self.spec.function_id}-sale-{ordinal}-start"
        )
        sale = AutoVpSaleWorkflow(
            self.auto,
            function_id=self.spec.function_id,
            allowed_item_ids=self.spec.sale_item_ids,
        ).run(timeout=120.0)
        self.sale_calls += 1
        self.sold_listings += int(sale.sold_listings)
        self.collected_gold_slots += int(sale.collected_gold_slots)
        self.context.stage(
            f"auto-main-{self.spec.function_id}-sale-{ordinal}-finished"
        )
        self.context.log(
            f"AUTO MULTI DEV • bán VP lần {ordinal} hoàn tất • "
            f"Function={self.spec.label} • treo={sale.sold_listings} ô • "
            f"thu_vàng={sale.collected_gold_slots}"
        )

    def _friend_refresh_if_due(self) -> None:
        """Run common anti-stuck maintenance after loop 3, 6, 9, ... when enabled."""
        if not self.friend_refresh_enabled:
            return
        if self.function_loops <= 0:
            return
        if self.function_loops % self.FRIEND_REFRESH_EVERY_LOOPS != 0:
            return

        self.context.ensure_running()
        ordinal = self.friend_refresh_calls + 1
        self.context.stage(
            f"auto-main-friend-refresh-{ordinal}-due-after-loop-{self.function_loops}"
        )
        self.context.log(
            "AUTO MULTI DEV • maintenance chống item treo đến hạn • "
            f"vòng Function={self.function_loops} • qua nhà bạn #1 rồi quay về"
        )
        passed = self.friend_refresh.run(completed_loops=self.function_loops)
        self.friend_refresh_calls += 1
        self.context.log(
            "AUTO MULTI DEV • maintenance chống item treo hoàn tất • "
            f"lần={self.friend_refresh_calls} • "
            f"trạng_thái={'PASS' if passed else 'RECOVERED'}"
        )

    def _wait_before_next_function_loop(self) -> None:
        delay = self.function_loop_delay_seconds
        if delay <= 0.0:
            return
        self.context.ensure_running()
        self.context.stage(
            f"auto-main-{self.spec.function_id}-between-loop-wait"
        )
        self.context.log(
            f"AUTO MULTI DEV • {self.spec.label} • chờ {delay:.3f}s "
            "trước vòng Function tiếp theo"
        )
        self.auto.wait.sleep(delay)

    def run(self) -> AutoMainResult:
        started = time.monotonic()
        self.context.stage("auto-main-pipeline-start")
        self.context.log(
            "AUTO MULTI DEV • Function đã chọn: "
            f"{self.spec.label} • bán lần 1 ngay sau vào game/đóng popup • "
            f"các lần sau mỗi {self.sale_every_loops} vòng • "
            f"refresh nhà bạn mỗi {self.FRIEND_REFRESH_EVERY_LOOPS} vòng="
            f"{'BẬT' if self.friend_refresh_enabled else 'TẮT'} • "
            f"chờ giữa vòng Function={self.function_loop_delay_seconds:.3f}s"
        )

        self._sale_once(ordinal=1)
        loops_since_sale = 0

        while True:
            self.context.ensure_running()
            next_loop = self.function_loops + 1
            self.context.stage(
                f"auto-main-{self.spec.function_id}-loop-{next_loop}-start"
            )
            self.context.log(
                f"AUTO MULTI DEV • {self.spec.label} • vòng {next_loop} START"
            )
            payload = self.function.run(function_id=self.spec.function_id)
            self._validate_function_result(payload)
            self.context.ensure_running()

            self.function_loops += 1
            loops_since_sale += 1
            self.context.stage(
                f"auto-main-{self.spec.function_id}-loop-{self.function_loops}-finished"
            )
            self.context.log(
                f"AUTO MULTI DEV • {self.spec.label} • vòng {self.function_loops} PASS • "
                f"đã {loops_since_sale}/{self.sale_every_loops} vòng từ lần bán gần nhất"
            )

            # Keep the established sale schedule first. If loop 3/6/9 is also a
            # sale boundary, finish sale/QC before the scene-refresh round trip.
            if loops_since_sale >= self.sale_every_loops:
                self._sale_once(ordinal=self.sale_calls + 1)
                loops_since_sale = 0

            self._friend_refresh_if_due()

            if (
                self.max_function_loops is not None
                and self.function_loops >= self.max_function_loops
            ):
                self.context.stage("auto-main-bounded-run-finished")
                return AutoMainResult(
                    profile_id=self.context.profile_id,
                    function_id=self.spec.function_id,
                    function_label=self.spec.label,
                    function_loops=self.function_loops,
                    sale_calls=self.sale_calls,
                    sold_listings=self.sold_listings,
                    collected_gold_slots=self.collected_gold_slots,
                    elapsed_seconds=round(time.monotonic() - started, 3),
                )

            self._wait_before_next_function_loop()
