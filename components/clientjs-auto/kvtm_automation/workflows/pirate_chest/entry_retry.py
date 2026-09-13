from __future__ import annotations

from typing import Callable

from .workflow import (
    PirateChestResult,
    PirateChestStatus,
    PirateChestWorkflow as _BasePirateChestWorkflow,
)


class PirateChestWorkflow(_BasePirateChestWorkflow):
    """Add one bounded retry only for the non-destructive Pirate Chest entry.

    The retry clicks the exact same operator-confirmed ship-body hitbox. It
    never searches either bubble above the ship, and it does not
    retry MỞ NGAY, chest-open, or reward-claim actions.
    """

    ENTRY_ATTEMPTS = 2

    def _wait_for(
        self,
        predicate: Callable[[object], bool],
        *,
        timeout: float,
        label: str,
        storage_interrupt: bool = False,
    ) -> tuple[str, object | None]:
        status, frame = super()._wait_for(
            predicate,
            timeout=timeout,
            label=label,
            storage_interrupt=storage_interrupt,
        )
        if label != "panel-open" or status == "PASS":
            return status, frame

        # Entry is the only safe action to retry: no chest has been opened and
        # no reward state can have changed yet. Keep the exact ship-body x/y so
        # we never drift upward into either bubble.
        self.context.log(
            "AUTO rương hải tặc • entry lần 1 chưa mở panel • "
            "retry 1 lần tại đúng hitbox thân thuyền, không click bong bóng"
        )
        self._tap(self.ENTRY_POINT, "pirate-chest-open-entry-retry-2")
        status, frame = super()._wait_for(
            predicate,
            timeout=timeout,
            label="panel-open-retry-2",
            storage_interrupt=storage_interrupt,
        )
        if status == "PASS":
            self.context.log(
                "AUTO rương hải tặc • entry lần 2 PASS • panel đã xác nhận"
            )
        return status, frame


__all__ = ["PirateChestResult", "PirateChestStatus", "PirateChestWorkflow"]
