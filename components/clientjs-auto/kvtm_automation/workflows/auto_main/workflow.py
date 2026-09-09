from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import time

from ...automation import KVAutomation
from ...errors import ClientRestartRequested
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
    "Theo dõi lịch restart ClientJS chung cho mọi Function nhưng chỉ phát yêu cầu restart sau sale boundary an toàn",
    "Nếu giờ restart đến giữa vòng Function thì chờ Function đủ vòng và bán VP xong mới restart",
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

    ClientJS restart is also scheduler-wide. The production interval is 7200
    seconds (2 hours). Reaching the deadline never interrupts an in-progress
    Function or a sale. The request is emitted only after a periodic sale has
    completed, so the parent Multi process can close/reopen ClientJS and attach a
    fresh worker without cutting a transactional Function in half.

    ``function_loop_delay_seconds`` is applied only between completed Function
    loops; it never delays the first loop and is skipped after the final loop of a
    bounded run.
    """

    FRIEND_REFRESH_EVERY_LOOPS = 3
    CLIENT_RESTART_INTERVAL_SECONDS = 7200.0
    CLIENT_RESTART_REQUEST_PREFIX = "CLIENT_RESTART_REQUESTED"

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

        maintenance = self._load_runtime_maintenance_config()
        self.client_restart_interval_seconds = float(
            maintenance["client_restart_interval_seconds"]
        )
        self.skip_initial_sale_once = bool(maintenance["skip_initial_sale_once"])
        if not 0.0 <= self.client_restart_interval_seconds <= 86400.0:
            raise ValueError(
                "client_restart_interval_seconds phải trong khoảng 0..86400"
            )

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
        self._client_restart_due_at = 0.0
        self._client_restart_due_announced = False

    def _load_runtime_maintenance_config(self) -> dict[str, object]:
        """Read integration-only maintenance fields from this run marker.

        The isolated worker intentionally ignores these extra keys. Keeping the
        handoff in the existing per-run marker lets the scheduler support a
        one-shot resume flag after ClientJS restart without expanding worker CLI
        or Bridge ownership.
        """
        config: dict[str, object] = {
            "client_restart_interval_seconds": self.CLIENT_RESTART_INTERVAL_SECONDS,
            "skip_initial_sale_once": False,
        }
        marker = self.context.work_dir / "auto-main-config.json"
        try:
            raw = json.loads(marker.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return config
        if not isinstance(raw, dict):
            return config
        try:
            config["client_restart_interval_seconds"] = float(
                raw.get(
                    "client_restart_interval_seconds",
                    self.CLIENT_RESTART_INTERVAL_SECONDS,
                )
            )
        except (TypeError, ValueError):
            config["client_restart_interval_seconds"] = (
                self.CLIENT_RESTART_INTERVAL_SECONDS
            )
        config["skip_initial_sale_once"] = bool(
            raw.get("skip_initial_sale_once", False)
        )
        return config

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

    def _client_restart_due(self) -> bool:
        return bool(
            self.client_restart_interval_seconds > 0.0
            and self._client_restart_due_at > 0.0
            and time.monotonic() >= self._client_restart_due_at
        )

    def _announce_client_restart_deferred(self, *, loops_since_sale: int) -> None:
        if not self._client_restart_due() or self._client_restart_due_announced:
            return
        self._client_restart_due_announced = True
        self.context.stage("auto-main-client-restart-due-deferred")
        self.context.log(
            "AUTO MULTI DEV • đến giờ restart ClientJS nhưng chưa ở safe boundary • "
            f"Function đã hoàn tất={self.function_loops} vòng • "
            f"đã {int(loops_since_sale)}/{self.sale_every_loops} vòng từ lần bán gần nhất • "
            "tiếp tục đủ vòng và bán VP xong mới restart"
        )

    def _request_client_restart_after_sale(self) -> None:
        self.context.ensure_running()
        self.context.stage("auto-main-client-restart-safe-boundary")
        self.context.log(
            "AUTO MULTI DEV • restart ClientJS SAFE • đã hoàn tất Function boundary "
            f"và bán VP xong • loops={self.function_loops} • sale_calls={self.sale_calls} • "
            f"interval={self.client_restart_interval_seconds:.0f}s"
        )
        raise ClientRestartRequested(
            f"{self.CLIENT_RESTART_REQUEST_PREFIX}|"
            f"function_id={self.spec.function_id}|"
            f"function_loops={self.function_loops}|"
            f"sale_calls={self.sale_calls}|"
            f"interval_seconds={self.client_restart_interval_seconds:.0f}"
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
        self._client_restart_due_at = (
            started + self.client_restart_interval_seconds
            if self.client_restart_interval_seconds > 0.0
            else 0.0
        )
        self.context.stage("auto-main-pipeline-start")
        self.context.log(
            "AUTO MULTI DEV • Function đã chọn: "
            f"{self.spec.label} • bán lần 1 ngay sau vào game/đóng popup • "
            f"các lần sau mỗi {self.sale_every_loops} vòng • "
            f"refresh nhà bạn mỗi {self.FRIEND_REFRESH_EVERY_LOOPS} vòng="
            f"{'BẬT' if self.friend_refresh_enabled else 'TẮT'} • "
            f"restart ClientJS={self.client_restart_interval_seconds:.0f}s/2h "
            "(chỉ sau sale boundary) • "
            f"chờ giữa vòng Function={self.function_loop_delay_seconds:.3f}s"
        )

        if self.skip_initial_sale_once:
            self.context.stage("auto-main-initial-sale-skipped-after-client-restart")
            self.context.log(
                "AUTO MULTI DEV • resume sau restart ClientJS • bỏ sale đầu một lần "
                "vì sale an toàn đã hoàn tất ngay trước khi restart"
            )
        else:
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

            self._announce_client_restart_deferred(
                loops_since_sale=loops_since_sale
            )

            # Keep the established sale schedule first. Restart is permitted only
            # after this sale returns, never merely because the timer expired.
            if loops_since_sale >= self.sale_every_loops:
                self._sale_once(ordinal=self.sale_calls + 1)
                loops_since_sale = 0
                if self._client_restart_due():
                    # A full ClientJS restart supersedes same-boundary friend
                    # refresh; the fresh client scene is already a stronger reset.
                    self._request_client_restart_after_sale()

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
