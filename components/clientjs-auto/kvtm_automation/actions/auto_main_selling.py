from __future__ import annotations

from dataclasses import dataclass

from .item_recognition import AutoVpRecognitionActions
from .selling import SellingActions


__all__ = ["AutoSaleAttempt", "AutoMainSellingActions"]
FILE_FUNCTIONS = (
    "Tìm một ô trống trong view quầy hiện tại",
    "Mở đúng kho thành phẩm số 2",
    "Nhận diện đúng ba VP AUTO được cho phép",
    "Chọn VP có độ tin cậy cao nhất",
    "Dùng cổng xác minh treo bán đã kiểm chứng",
    "Trả trạng thái rõ ràng cho workflow điều phối",
)


@dataclass(frozen=True)
class AutoSaleAttempt:
    status: str
    item_id: str = ""
    label: str = ""
    score: float = 0.0


class AutoMainSellingActions:
    """AUTO Main sale adapter isolated from the clear-stall transaction flow."""

    def __init__(
        self,
        selling: SellingActions,
        recognition: AutoVpRecognitionActions,
    ) -> None:
        self.selling = selling
        self.recognition = recognition
        self.context = selling.context
        self.inventory = selling.inventory

    def sell_next_allowed(self, *, storage_id: int = 2) -> AutoSaleAttempt:
        """Sell one recognized AUTO VP into one empty slot, or report why not."""
        self.context.ensure_running()
        if not self.selling._find_empty_slot():
            return AutoSaleAttempt(status="NO_EMPTY_SLOT")

        self.inventory.select_storage(storage_id)
        recognized = tuple(
            item for item in self.recognition.scan_samples(log_prefix="AUTO SELL VP")
            if item.found and item.center is not None
        )
        if not recognized:
            self.selling.close_inventory_read_only()
            return AutoSaleAttempt(status="NO_ALLOWED_ITEM")

        selected = max(recognized, key=lambda item: float(item.score))
        self.context.log(
            f"AUTO bán VP • chọn {selected.label} • score={selected.score:.3f}"
        )
        self.selling._finish_batch_from_match(
            selected.center,
            float(selected.score),
        )
        return AutoSaleAttempt(
            status="SOLD",
            item_id=selected.item_id,
            label=selected.label,
            score=float(selected.score),
        )
