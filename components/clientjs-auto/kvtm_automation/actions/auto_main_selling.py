from __future__ import annotations

from dataclasses import dataclass

from .item_recognition import AutoVpRecognitionActions
from .selling import SellingActions


__all__ = ["AutoSaleAttempt", "AutoMainSellingActions"]
FILE_FUNCTIONS = (
    "Tìm một ô trống trong view quầy hiện tại",
    "Mở đúng kho thành phẩm số 2",
    "Bấm chính xác nút kho thành phẩm có biểu tượng giỏ hàng",
    "Chờ và quét lại nhiều frame trước khi kết luận hết VP",
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

    def _open_and_scan_finished_goods(self):
        """Click the basket tab and require repeated fresh-frame recognition."""
        basket_button = (450, 442)
        best_by_id = {}
        for attempt in range(1, 4):
            self.context.ensure_running()
            # AUTO PRO 1000x1000: the second storage tab is the basket icon.
            self.selling.vision.driver.click(*basket_button)
            self.context.log(
                f"AUTO bán VP • đã bấm nút kho thành phẩm 2 • lần {attempt}/3"
            )
            self.selling.waiter.sleep(0.60 if attempt == 1 else 0.40)
            for item in self.recognition.scan_samples(log_prefix="AUTO SELL VP"):
                if not item.found or item.center is None:
                    continue
                previous = best_by_id.get(item.item_id)
                if previous is None or item.score > previous.score:
                    best_by_id[item.item_id] = item
            if best_by_id:
                return tuple(best_by_id.values())
        return ()

    def sell_next_allowed(self, *, storage_id: int = 2) -> AutoSaleAttempt:
        """Sell one recognized AUTO VP into one empty slot, or report why not."""
        self.context.ensure_running()
        if not self.selling._find_empty_slot():
            return AutoSaleAttempt(status="NO_EMPTY_SLOT")

        if int(storage_id) != 2:
            raise ValueError("AUTO Main chỉ bán VP từ kho thành phẩm số 2")
        recognized = self._open_and_scan_finished_goods()
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
