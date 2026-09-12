from __future__ import annotations

from ...daily_sale_counter import record_successful_listings
from .workflow import AutoVpSaleResult, AutoVpSaleWorkflow as _AutoVpSaleWorkflow


class AutoVpSaleWorkflow(_AutoVpSaleWorkflow):
    """VP sale workflow with a non-blocking persistent per-listing counter."""

    def run(self, timeout: float = 120.0) -> AutoVpSaleResult:
        result = super().run(timeout=timeout)
        sold = int(result.sold_listings)
        if sold <= 0:
            return result
        try:
            count = record_successful_listings(
                self.context,
                sold_listings=sold,
            )
            self.context.log(
                "AUTO bộ đếm bán • "
                f"profile={self.context.profile_id} • hôm_nay={count}/1000 • "
                f"lượt_này=+{sold} • mỗi ô=x10 VP"
            )
        except Exception as exc:
            # Counter telemetry must never turn a proven sale into a business
            # failure or disturb warehouse-full checkpoint recovery.
            self.context.detail(
                "AUTO bộ đếm bán | non-blocking write failed | "
                f"{type(exc).__name__}: {exc}"
            )
        return result


__all__ = ["AutoVpSaleResult", "AutoVpSaleWorkflow"]
