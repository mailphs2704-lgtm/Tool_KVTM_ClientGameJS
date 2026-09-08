from __future__ import annotations

from dataclasses import dataclass

from ..context import AutomationContext
from ..errors import ScreenTimeout
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter
from .production import ProductionResult


__all__ = ["MachineRepairActions", "MachineRepairHandoff"]
FILE_FUNCTIONS = (
    "Nhận bàn giao từ panel máy đang mở sau khi đã kéo đủ số lượng VP",
    "Chỉ cho phép vào luồng Sửa máy khi hậu kiểm production đã đủ chính xác",
    "Giữ panel máy mở để bước Sửa máy tiếp theo không phải mở lại máy",
    "Fail-close về logic nếu số lượng/hậu kiểm không khớp, không thao tác mù",
)


@dataclass(frozen=True)
class MachineRepairHandoff:
    item_id: str
    queued_count: int
    panel_open: bool


class MachineRepairActions:
    """Safe handoff from a verified production panel into the repair flow.

    The actual repair-button gesture is intentionally not hard-coded here yet.
    Function 2 will provide the proven repair-screen entry once its exact UI
    sequence/template has been captured. Until then this module only accepts a
    production result that is already fully verified and keeps the panel open.
    """

    def __init__(
        self,
        context: AutomationContext,
        vision: VisionEngine,
        waiter: Waiter,
    ) -> None:
        self.context = context
        self.vision = vision
        self.waiter = waiter

    def begin_from_open_panel(self, result: ProductionResult) -> MachineRepairHandoff:
        self.context.ensure_running()
        consumed = max(0, int(result.empty_before) - int(result.empty_after))
        requested = int(result.requested_count)
        queued = int(result.queued_count)
        if requested <= 0 or queued != requested or consumed != requested:
            raise ScreenTimeout(
                "Không bàn giao sang Sửa máy vì hậu kiểm production chưa đủ: "
                f"item={result.item_id}, requested={requested}, queued={queued}, "
                f"slot_delta={consumed}"
            )

        self.context.stage("auto-machine-repair-handoff-ready")
        self.context.log(
            "AUTO Sửa máy • production đã đủ và panel vẫn mở • "
            f"item={result.item_id} • số lượng={queued} • chờ bước vào Sửa máy"
        )
        return MachineRepairHandoff(
            item_id=str(result.item_id),
            queued_count=queued,
            panel_open=True,
        )
