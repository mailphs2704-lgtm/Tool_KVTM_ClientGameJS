from __future__ import annotations

import time
from typing import Callable, TypeVar

from ..context import AutomationContext
from ..errors import ScreenTimeout


T = TypeVar("T")


class Waiter:
    """Cancellation-aware waits plus bounded transaction-settle windows."""

    def __init__(self, context: AutomationContext) -> None:
        self.context = context

    def sleep(self, seconds: float, *, slice_seconds: float = 0.05) -> None:
        """Ordinary cooperative wait: stop requests interrupt immediately."""
        deadline = time.monotonic() + max(0.0, float(seconds))
        while time.monotonic() < deadline:
            self.context.ensure_running()
            time.sleep(min(slice_seconds, max(0.0, deadline - time.monotonic())))

    def settle(self, seconds: float, *, slice_seconds: float = 0.05) -> None:
        """Finish a short post-click verification window before honoring stop.

        A destructive click may already have reached the game. Aborting between
        that click and its manifest update would lose accounting. `settle` is
        therefore only for short, bounded transaction windows; the caller must
        call `ensure_running()` before starting the next destructive action.
        """
        deadline = time.monotonic() + max(0.0, float(seconds))
        while time.monotonic() < deadline:
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
