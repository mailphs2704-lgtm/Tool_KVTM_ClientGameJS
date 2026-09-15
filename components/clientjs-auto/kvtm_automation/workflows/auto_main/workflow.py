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
    "Bán đúng VP thuộc Function ngay sau bước vào game/popup watch",
    "Chạy Function hoàn chỉnh liên tục cho tới khi operator bấm Dừng",
    "Sau lần bán đầu, bán lại theo số vòng Function cấu hình",
    "Nếu GUI bật, periodic Friend Refresh chạy theo counter riêng sau Function PASS",
    "Scheduled ClientJS restart mặc định mỗi 3 giờ và không cắt ngang Function",
    "Khi 3h đến giữa Function, chờ đúng Function hiện tại PASS rồi mới xử lý boundary",
    "Trước scheduled restart luôn hoàn tất một sale an toàn để resume có thể skip sale đầu đúng một lần",
    "Giữ stop-check trước Function, sale, maintenance và thời gian chờ",
    "Fail-close nếu Function chưa có runner/completion gate runtime hoàn chỉnh",
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
    """Continuous AUTO scheduler for one selected built-in Function.

    Normal ordering is:

        startup/login + popup watch 60s
        -> initial sale
        -> Function loop
        -> periodic sale when due
        -> periodic Friend Refresh when due
        -> next Function

    Scheduled ClientJS restart is scheduler-wide and defaults to three hours.
    A deadline never interrupts an in-progress Function. If the deadline becomes
    due while a Function is running, the scheduler waits for that Function to
    PASS. At that safe boundary it guarantees one sale has just completed, then
    emits ``ClientRestartRequested``. This preserves the existing one-shot
    ``skip_initial_sale_once`` restart handoff without delaying restart for extra
    Function loops merely to reach the normal sale cadence.

    Emergency/recovery restart is intentionally not implemented here yet. It
    requires the separate durable-checkpoint policy that will be wired only when
    the operator identifies/approves the corresponding error branch.
    """

    FRIEND_REFRESH_EVERY_LOOPS = 3
    CLIENT_RESTART_INTERVAL_SECONDS = 10800.0
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

    def _load_runtime_maintenance_config(self) -> dict[str, object]:
        """Read integration-only maintenance fields from this run marker."""
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
        """Keep Function-specific completion gates at scheduler boundary."""
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

        if self.spec.runner_key == "function_2":
            if (
                int(payload.get("progress_steps", 0) or 0) != 4
                or int(payload.get("total_steps", 0) or 0) != 4
            ):
                raise RuntimeError(
                    "Function 2 trả kết quả không đạt hợp đồng PASS 4/4"
                )

            required_counts = {
                "dried_apples": 9,
                "apple_juices": 9,
                "cotton_planted": 27,
                "yellow_fabrics": 9,
                "roses_planted": 35,
                "snow_planted": 28,
                "rose_oils": 7,
            }
            mismatches = [
                f"{name}={int(payload.get(name, 0) or 0)}/{expected}"
                for name, expected in required_counts.items()
                if int(payload.get(name, 0) or 0) != expected
            ]
            if mismatches:
                raise RuntimeError(
                    "Function 2 completion gate FAIL: " + ", ".join(mismatches)
                )
            self.context.log(
                "AUTO Main • Function 2 completion gate PASS • "
                "Táo sấy=9 • Nước táo=9 • Bông=27 • Vải vàng=9 • "
                "Hồng=35 • Tuyết=28 • TDHH=7"
            )
            return

        if self.spec.runner_key == "function_3":
            if (
                int(payload.get("progress_steps", 0) or 0) != 6
                or int(payload.get("total_steps", 0) or 0) != 6
                or int(payload.get("end_floor", -1)) != 0
            ):
                raise RuntimeError(
                    "Function 3 trả kết quả không đạt hợp đồng PASS 6/6 về exact MAIN"
                )

            required_counts = {
                "apples_floor_1_to_5": 30,
                "apples_floor_6": 6,
                "dried_teas": 9,
                "planted_teas": 24,
                "apple_juices": 9,
                "planted_tea_bottom_row": 3,
                "cotton_planted": 27,
                "yellow_fabrics": 9,
                "roses_floor_1_planted": 30,
                "roses_floor_6_planted": 15,
                "tdhh_snow_floor_1_planted": 30,
                "tdhh_snow_floor_6_planted": 6,
                "rose_oils": 9,
                "snow_floor_1_planted": 30,
                "snow_floor_6_planted": 6,
                "iced_teas": 9,
                "final_roses_floor_1_planted": 30,
                "final_roses_floor_6_planted": 6,
                "rose_waters": 9,
            }
            mismatches = [
                f"{name}={int(payload.get(name, 0) or 0)}/{expected}"
                for name, expected in required_counts.items()
                if int(payload.get(name, 0) or 0) != expected
            ]
            if mismatches:
                raise RuntimeError(
                    "Function 3 completion gate FAIL: " + ", ".join(mismatches)
                )
            if not self.auto.popup.is_own_exact_main_screen():
                raise RuntimeError(
                    "Function 3 completion gate FAIL: Step 6 trả end_floor=0 "
                    "nhưng runtime chưa chứng minh exact MAIN"
                )
            self.context.log(
                "AUTO Main • Function 3 completion gate PASS • Step=6/6 • "
                "Trà sấy=9 • Nước táo=9 • Vải vàng=9 • "
                "Hồng TDHH=45 • Tuyết TDHH=36 • TDHH=9 • "
                "Trà đá=9 • Nước hoa hồng=9 • exact MAIN"
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

    def _request_client_restart_at_safe_boundary(self) -> None:
        self.context.ensure_running()
        self.context.stage("auto-main-client-restart-safe-boundary")
        self.context.log(
            "AUTO MULTI DEV • restart ClientJS SAFE • Function hiện tại đã PASS "
            "và sale trước restart đã hoàn tất • "
            f"loops={self.function_loops} • sale_calls={self.sale_calls} • "
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
        """Run common anti-stuck maintenance on its independent loop counter."""
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
            "AUTO MULTI DEV • periodic Friend Refresh đến hạn • "
            f"vòng Function={self.function_loops} • qua nhà bạn #1 rồi quay về"
        )
        passed = self.friend_refresh.run(completed_loops=self.function_loops)
        self.friend_refresh_calls += 1
        self.context.log(
            "AUTO MULTI DEV • periodic Friend Refresh hoàn tất • "
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
            f"{self.spec.label} • bán lần 1 ngay sau startup 60s • "
            f"các lần sau mỗi {self.sale_every_loops} vòng • "
            f"refresh nhà bạn mỗi {self.FRIEND_REFRESH_EVERY_LOOPS} vòng="
            f"{'BẬT' if self.friend_refresh_enabled else 'TẮT'} • "
            f"restart ClientJS={self.client_restart_interval_seconds:.0f}s/3h "
            "(defer đến Function boundary) • "
            f"chờ giữa vòng Function={self.function_loop_delay_seconds:.3f}s"
        )

        if self.skip_initial_sale_once:
            self.context.stage("auto-main-initial-sale-skipped-after-client-restart")
            self.context.log(
                "AUTO MULTI DEV • resume sau scheduled restart • bỏ sale đầu một lần "
                "vì sale an toàn đã hoàn tất ngay trước restart"
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

            sale_completed_at_boundary = False
            if loops_since_sale >= self.sale_every_loops:
                self._sale_once(ordinal=self.sale_calls + 1)
                loops_since_sale = 0
                sale_completed_at_boundary = True

            # 3h reached during the Function: we are now at the first safe
            # Function boundary. Guarantee a sale immediately before restart so
            # the parent can preserve the existing skip_initial_sale_once handoff.
            if self._client_restart_due():
                if not sale_completed_at_boundary:
                    self.context.stage("auto-main-client-restart-pre-sale")
                    self.context.log(
                        "AUTO MULTI DEV • mốc 3h đã đến • Function hiện tại PASS • "
                        "chạy sale an toàn trước scheduled restart"
                    )
                    self._sale_once(ordinal=self.sale_calls + 1)
                    loops_since_sale = 0
                self._request_client_restart_at_safe_boundary()

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
