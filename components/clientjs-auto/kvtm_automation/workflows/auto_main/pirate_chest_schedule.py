from __future__ import annotations

import json
import time
import traceback

from ...daily_pirate_chest_counter import record_pirate_chest_opened
from ...daily_sale_counter import record_successful_listings
from ...error_journal import explain_error_vi, record_auto_error
from ...errors import AutomationStopped, ClientRestartRequested, ScreenTimeout
from ...recovery import RecoveryManager
from ..auto_vp_sale import AutoVpSaleWorkflow
from ..pirate_chest import PirateChestWorkflow
from .boundary_delay import AutoMainResult, AutoMainWorkflow as _BoundaryAutoMainWorkflow
from .friend_refresh import FriendRefreshWorkflow


__all__ = ["AutoMainResult", "AutoMainWorkflow"]


class AutoMainWorkflow(_BoundaryAutoMainWorkflow):
    """AUTO Main with safe optional maintenance and global runtime recovery.

    Registered typed recovery remains closest to the failing module. Any runtime
    exception that escapes those policies is treated as an unhandled AUTO error:
    persist diagnostics, recover exact MAIN, force friend #1 -> own home, then
    restart the selected AUTO Function instead of terminating the worker.
    """

    PIRATE_CHEST_INTERVAL_SECONDS = 1200.0
    _SALE_LABELS = {
        "tao_say": "táo sấy",
        "vai_vang": "vải vàng",
        "tinh_dau_hh": "tinh dầu hoa hồng",
        "nuoc_hoa_hong": "nước hoa hồng",
        "tra_da": "trà đá",
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.pirate_chest_enabled = self._load_pirate_chest_enabled()
        self.pirate_chest_calls = 0
        startup_opened_at = getattr(
            self.context,
            "pirate_chest_opened_at_monotonic",
            None,
        )
        self._pirate_chest_initialized = bool(
            self.pirate_chest_enabled and startup_opened_at is not None
        )
        self._pirate_chest_next_check_at = (
            float(startup_opened_at) + self.PIRATE_CHEST_INTERVAL_SECONDS
            if self._pirate_chest_initialized
            else 0.0
        )
        self._pirate_chest_retry_after_sale = False
        self._pirate_chest_boundary_recovery = RecoveryManager(
            self.auto,
            function_id=self.spec.function_id,
        )
        self.context.log(
            "AUTO tùy chọn • Mở rương hải tặc="
            + ("BẬT" if self.pirate_chest_enabled else "TẮT")
            + " • nguồn=auto-main-config.json"
            + (
                " • startup đã OPENED=tiếp tục chờ đủ 20 phút"
                if self._pirate_chest_initialized
                else " • check đầu sau sale đầu"
            )
            + " • OPENED=20 phút • chưa mở=retry sau sale VP kế tiếp"
        )

    def _load_pirate_chest_enabled(self) -> bool:
        marker = self.context.work_dir / "auto-main-config.json"
        try:
            raw = json.loads(marker.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return False
        if not isinstance(raw, dict):
            return False
        if "pirate_chest_enabled" in raw:
            return bool(raw.get("pirate_chest_enabled"))
        for key in ("option_flags", "options", "auto_options"):
            flags = raw.get(key)
            if isinstance(flags, (list, tuple)) and flags:
                return bool(flags[0])
            if isinstance(flags, dict):
                if 0 in flags:
                    return bool(flags[0])
                if "0" in flags:
                    return bool(flags["0"])
        return False

    def _pirate_chest_due(self) -> bool:
        return bool(
            self.pirate_chest_enabled
            and self._pirate_chest_initialized
            and self._pirate_chest_next_check_at > 0.0
            and time.monotonic() >= self._pirate_chest_next_check_at
        )

    def _schedule_next_pirate_chest_check(self, *, status: str) -> None:
        self._pirate_chest_initialized = True
        if str(status) == "OPENED":
            self._pirate_chest_retry_after_sale = False
            opened_at = getattr(
                self.context,
                "pirate_chest_opened_at_monotonic",
                None,
            )
            if opened_at is None:
                opened_at = time.monotonic()
            self._pirate_chest_next_check_at = (
                float(opened_at) + self.PIRATE_CHEST_INTERVAL_SECONDS
            )
            return
        self._pirate_chest_retry_after_sale = True
        self._pirate_chest_next_check_at = 0.0

    def _prove_exact_main_boundary(self, *, reason: str) -> None:
        self.context.ensure_running()
        if self.auto.popup.is_own_exact_main_screen():
            self.context.detail(
                "AUTO rương hải tặc | exact-main boundary already proven | "
                f"reason={reason}"
            )
            return
        self.context.stage("auto-main-pirate-chest-exact-main-recovery")
        self.context.log(
            "AUTO rương hải tặc • boundary chưa có exact-main • "
            f"recovery công khai trước Function • reason={reason}"
        )
        self.auto.ensure_main_screen(timeout=12.0)
        if not self.auto.popup.is_own_exact_main_screen():
            self._pirate_chest_boundary_recovery.recover_unknown_to_main(
                f"rương hải tặc boundary {reason}",
                reason=f"pirate-chest-boundary-{reason}",
            )
        self._pirate_chest_boundary_recovery.ensure_main(
            f"rương hải tặc boundary {reason}"
        )
        self.context.stage("auto-main-pirate-chest-exact-main-ready")
        self.context.log(
            "AUTO rương hải tặc • boundary exact-main PASS • "
            f"reason={reason}"
        )

    def _reset_scene_after_pirate_chest_abort(self, *, reason: str) -> None:
        self.context.stage("auto-main-pirate-chest-safe-abort-scene-reset")
        self.context.log(
            "AUTO rương hải tặc • SAFE_ABORT • bắt buộc qua nhà bạn #1 "
            "rồi về nhà để reset scene trước Function kế tiếp • "
            f"reason={reason}"
        )
        refreshed = FriendRefreshWorkflow(
            self.auto,
            function_id=self.spec.function_id,
        ).run(completed_loops=0)
        if not refreshed:
            raise ScreenTimeout(
                "Rương hải tặc SAFE_ABORT nhưng chưa chứng minh được vòng "
                "nhà bạn #1 → nhà mình; dừng trước Function kế tiếp"
            )
        self.context.log(
            "AUTO rương hải tặc • scene reset PASS • "
            "nhà bạn #1 → nhà mình → exact-main"
        )

    def _run_pirate_chest(self, *, reason: str) -> None:
        if not self.pirate_chest_enabled:
            return
        self.context.ensure_running()
        ordinal = self.pirate_chest_calls + 1
        self.context.stage(f"auto-main-pirate-chest-{ordinal}-start")
        self.context.log(
            "AUTO rương hải tặc • bắt đầu check hậu Function • "
            f"lần={ordinal} • reason={reason}"
        )
        self._prove_exact_main_boundary(reason=f"{reason}-before-chest")

        status = "ERROR"
        detail = ""
        try:
            result = PirateChestWorkflow(self.auto).run()
            status = str(result.status)
            detail = str(result.detail)
            if status == "OPENED":
                opened_today = record_pirate_chest_opened(self.context)
                self.context.action(
                    f"Mở rương thành công {opened_today} lần hôm nay"
                )
        except AutomationStopped:
            raise
        except Exception as exc:
            status = "SAFE_ABORT"
            detail = f"{type(exc).__name__}: {exc}"
            self.context.detail(
                "AUTO rương hải tặc | non-blocking error | " + detail
            )
        finally:
            self.pirate_chest_calls += 1
            self._schedule_next_pirate_chest_check(status=status)

        if status == "SAFE_ABORT":
            self._reset_scene_after_pirate_chest_abort(reason=detail or reason)
        self._prove_exact_main_boundary(reason=f"{reason}-after-chest")
        self.context.stage(f"auto-main-pirate-chest-{ordinal}-finished")
        next_check = (
            f"{self.PIRATE_CHEST_INTERVAL_SECONDS:.0f}s"
            if status == "OPENED"
            else "sau-lần-bán-VP-kế-tiếp"
        )
        self.context.log(
            "AUTO rương hải tặc • kết thúc lượt check • "
            f"lần={ordinal} • status={status} • detail={detail} • "
            f"exact-main=PASS • check_lại={next_check}"
        )

    def _sale_once(self, *, ordinal: int) -> None:
        self._mark_boundary_activity_started()
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
        daily_turns = record_successful_listings(
            self.context,
            sold_listings=int(sale.sold_listings),
        )
        self.context.stage(
            f"auto-main-{self.spec.function_id}-sale-{ordinal}-finished"
        )

        parts = []
        for item_id in self.spec.sale_item_ids:
            listings = int(sale.sold_by_item.get(item_id, 0) or 0)
            if listings <= 0:
                continue
            label = self._SALE_LABELS.get(item_id, item_id)
            parts.append(f"{listings * 10} {label}")
        daily_units = int(daily_turns) * 10
        if parts:
            self.context.action(
                f"Đã bán {', '.join(parts)}, tổng số VP bán trong ngày {daily_units}"
            )
        else:
            self.context.action(
                f"Không có VP đủ x10 để bán, tổng số VP bán trong ngày {daily_units}"
            )
        self.context.log(
            f"AUTO MULTI DEV • bán VP lần {ordinal} hoàn tất • "
            f"Function={self.spec.label} • treo={sale.sold_listings} ô • "
            f"thu_vàng={sale.collected_gold_slots} • daily_turns={daily_turns}"
        )

        if self.pirate_chest_enabled and (
            not self._pirate_chest_initialized
            or self._pirate_chest_retry_after_sale
        ):
            reason = (
                f"first-completed-sale-{ordinal}"
                if not self._pirate_chest_initialized
                else f"retry-after-completed-sale-{ordinal}"
            )
            self._run_pirate_chest(reason=reason)

    def _pirate_chest_checkpoint(self, *, reason: str) -> None:
        if not self._pirate_chest_due():
            return
        self._mark_boundary_activity_started()
        self._run_pirate_chest(reason=reason)

    def _request_client_restart_at_safe_boundary(self) -> None:
        self._pirate_chest_checkpoint(reason="pre-client-restart-boundary")
        super()._request_client_restart_at_safe_boundary()

    def _wait_before_next_function_loop(self) -> None:
        self._pirate_chest_checkpoint(reason="post-function-boundary")
        super()._wait_before_next_function_loop()

    def _recover_unhandled_runtime_error(
        self,
        error: BaseException,
        *,
        traceback_text: str,
    ) -> None:
        """Never stop AUTO for an unregistered runtime error; normalize and retry."""
        explanation = explain_error_vi(error)
        record_auto_error(
            self.context,
            error,
            traceback_text=traceback_text,
            phase="AUTO Main runtime",
            recovery_state="bắt đầu exact MAIN → nhà bạn #1 → nhà mình",
        )
        self.context.action(
            f"Lỗi {type(error).__name__}: {explanation} Chuyển trạng thái xử lí"
        )
        self.context.detail(
            "AUTO global recovery | escaped_exception | "
            f"type={type(error).__name__} | message={error} | policy="
            "exact-main->friend1->own-home->restart-auto"
        )

        recovery_round = 0
        while True:
            self.context.ensure_running()
            recovery_round += 1
            try:
                self._pirate_chest_boundary_recovery.recover_unknown_to_main(
                    "lỗi chưa có policy",
                    reason=f"unhandled-runtime-error-round-{recovery_round}",
                )
                refreshed = FriendRefreshWorkflow(
                    self.auto,
                    function_id=self.spec.function_id,
                ).run(completed_loops=0)
                if not refreshed:
                    raise ScreenTimeout(
                        "Global recovery chưa hoàn tất vòng nhà bạn #1 → nhà mình"
                    )
                if not self.auto.popup.is_own_exact_main_screen():
                    raise ScreenTimeout(
                        "Global recovery quay về nhà nhưng chưa chứng minh exact MAIN"
                    )
                self.context.action(
                    "Đã xử lí lỗi • exact MAIN → nhà bạn #1 → nhà mình • bắt đầu lại AUTO"
                )
                self.context.detail(
                    "AUTO global recovery PASS | "
                    f"round={recovery_round} | exact_main=true | restart_auto=true"
                )
                return
            except (ClientRestartRequested, AutomationStopped):
                raise
            except Exception as recovery_error:
                record_auto_error(
                    self.context,
                    recovery_error,
                    traceback_text=traceback.format_exc(),
                    phase="global recovery",
                    recovery_state=f"thử lại recovery round={recovery_round + 1}",
                )
                self.context.detail(
                    "AUTO global recovery RETRY | "
                    f"round={recovery_round} | {type(recovery_error).__name__}: "
                    f"{recovery_error}"
                )
                self.auto.wait.sleep(1.0)

    def run(self) -> AutoMainResult:
        """Run forever across recoverable unhandled errors until operator/lifecycle stop."""
        while True:
            try:
                return super().run()
            except ClientRestartRequested:
                raise
            except AutomationStopped:
                raise
            except Exception as exc:
                self._recover_unhandled_runtime_error(
                    exc,
                    traceback_text=traceback.format_exc(),
                )
                self.context.detail(
                    "AUTO global recovery handoff • restarting selected AUTO Main workflow"
                )
