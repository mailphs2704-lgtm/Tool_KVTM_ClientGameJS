from __future__ import annotations

import time

from .workflow import AutoMainResult, AutoMainWorkflow as _BaseAutoMainWorkflow


__all__ = ["AutoMainResult", "AutoMainWorkflow"]


class AutoMainWorkflow(_BaseAutoMainWorkflow):
    """AUTO Main scheduler with boundary-aware Function loop delay.

    ``function_loop_delay_seconds`` is the total minimum boundary time between
    two Function loops. Sale/Friend Refresh time counts toward that boundary;
    it must not be followed by another full sleep of the configured delay.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._function_boundary_started_at: float | None = None

    def _mark_boundary_activity_started(self) -> None:
        if self.function_loops <= 0:
            return
        if self._function_boundary_started_at is None:
            self._function_boundary_started_at = time.monotonic()

    def _sale_once(self, *, ordinal: int) -> None:
        # Initial startup sale happens before Function loop 1 and therefore is
        # not part of a between-Function boundary.
        self._mark_boundary_activity_started()
        super()._sale_once(ordinal=ordinal)

    def _friend_refresh_if_due(self) -> None:
        due = bool(
            self.friend_refresh_enabled
            and self.function_loops > 0
            and self.function_loops % self.FRIEND_REFRESH_EVERY_LOOPS == 0
        )
        if due:
            self._mark_boundary_activity_started()
        super()._friend_refresh_if_due()

    def _wait_before_next_function_loop(self) -> None:
        delay = float(self.function_loop_delay_seconds)
        if delay <= 0.0:
            self._function_boundary_started_at = None
            return

        started = self._function_boundary_started_at
        elapsed = 0.0 if started is None else max(0.0, time.monotonic() - started)
        remaining = max(0.0, delay - elapsed)

        self.context.ensure_running()
        try:
            if remaining <= 0.0:
                self.context.log(
                    f"AUTO MULTI DEV • {self.spec.label} • boundary đã dùng "
                    f"{elapsed:.3f}s/{delay:.3f}s • Sale/maintenance đã đủ "
                    "thời gian chờ • bắt đầu Function tiếp theo ngay"
                )
                return

            self.context.stage(
                f"auto-main-{self.spec.function_id}-between-loop-wait"
            )
            self.context.log(
                f"AUTO MULTI DEV • {self.spec.label} • boundary đã dùng "
                f"{elapsed:.3f}s/{delay:.3f}s • chỉ chờ thêm {remaining:.3f}s "
                "trước vòng Function tiếp theo"
            )
            self.auto.wait.sleep(remaining)
        finally:
            self._function_boundary_started_at = None
