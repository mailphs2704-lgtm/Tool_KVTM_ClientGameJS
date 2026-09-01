from __future__ import annotations

import time
from typing import Callable, TypeVar

from ..context import AutomationContext
from ..errors import ScreenTimeout


T = TypeVar("T")


class Waiter:
    """Stop-aware retry/sleep helper used by every action module."""

    def __init__(self, context: AutomationContext) -> None:
        self.context = context

    def sleep(self, seconds: float, *, slice_seconds: float = 0.05) -> None:
        deadline = time.monotonic() + max(0.0, float(seconds))
        while time.monotonic() < deadline:
            self.context.ensure_running()
            time.sleep(min(slice_seconds, max(0.0, deadline - time.monotonic())))

    def until(
        self,
        probe: Callable[[], T | None | bool],
        *,
        timeout: float,
        interval: float = 0.25,
        description: str,
    ) -> T:
        deadline = time.monotonic() + float(timeout)
        while time.monotonic() < deadline:
            self.context.ensure_running()
            value = probe()
            if value:
                return value  # type: ignore[return-value]
            self.sleep(interval)
        raise ScreenTimeout(f"Hết thời gian chờ: {description}")
