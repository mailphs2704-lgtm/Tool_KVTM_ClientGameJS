from __future__ import annotations

import json
import time

from ...daily_pirate_chest_counter import record_pirate_chest_opened
from ...daily_sale_counter import record_successful_listings
from ...errors import AutomationStopped, ScreenTimeout
from ...recovery import RecoveryManager
from ..auto_vp_sale import AutoVpSaleWorkflow
from ..pirate_chest import PirateChestWorkflow
from .boundary_delay import AutoMainResult, AutoMainWorkflow as _BoundaryAutoMainWorkflow
from .friend_refresh import FriendRefreshWorkflow


__all__ = ["AutoMainResult", "AutoMainWorkflow"]


class AutoMainWorkflow(_BoundaryAutoMainWorkflow):
    """AUTO Main with optional Pirate Chest maintenance at safe boundaries.

    The first Pirate Chest check is attached to the first completed sale. Only
    OPENED starts a 20-minute deadline. COOLDOWN or any other non-OPENED result
    retries after the next completed VP sale. Timed work still runs only from a
    safe Function boundary and never interrupts a Function in progress.

    Pirate Chest is an overlay maintenance flow, while every production Function
    starts only from exact-main. The scheduler therefore owns an explicit public
    boundary recovery before and after chest maintenance. Recipes keep their
    strict fail-close contract and never hide recovery/navigation internally.
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
        """Read option #1 from the frozen per-run AUTO Main config."""
        marker = self.context.work_dir / "auto-main-config.json"
        try:
            raw = json.loads(marker.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return False
        if not isinstance(raw, dict):
            return False

        if "pirate_chest_enabled" in raw:
            return bool(raw.get("pirate_chest_enabled"))

        # Compatibility only for older DEV run markers. New runs write the
        # explicit pirate_chest_enabled field from Optional Features.
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
        """Only a proven OPENED result owns the 20-minute timer."""
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
        """Explicitly restore the caller contract before/after optional UI work."""
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
        """Force a friend-house round trip before handing control to a Function."""
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
        """Run one sale and emit exactly one concise per-account action summary."""
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
