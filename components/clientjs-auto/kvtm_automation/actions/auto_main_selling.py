from __future__ import annotations

from dataclasses import dataclass
import time

from ..errors import ScreenTimeout, TransactionError
from .item_recognition import AutoVpRecognitionActions, VpRecognition
from .selling import SellingActions, _mean_difference


__all__ = ["AutoSaleAttempt", "AutoMainSellingActions"]
FILE_FUNCTIONS = (
    "Tìm một ô trống trong view quầy hiện tại",
    "Bấm chính xác nút kho thành phẩm có biểu tượng giỏ hàng",
    "Chờ và quét lại nhiều frame trước khi kết luận hết VP",
    "Chọn luân phiên Táo sấy, Vải vàng và Tinh dầu hoa hồng",
    "Bắt buộc xác nhận số lượng x10 trước khi đặt bán",
    "Bỏ qua loại còn dưới x10 và chuyển sang loại kế tiếp",
    "Xác minh màn hình thay đổi trước khi ghi nhận đã treo",
    "Trả trạng thái rõ ràng cho workflow điều phối",
)


@dataclass(frozen=True)
class AutoSaleAttempt:
    status: str
    item_id: str = ""
    label: str = ""
    score: float = 0.0


class AutoMainSellingActions:
    """Balanced exact-x10 AUTO sale, isolated from clear-stall accounting."""

    ITEM_ORDER = ("tao_say", "vai_vang", "tinh_dau_hh")
    SELECTED_ITEM_TEMPLATES = {
        "tao_say": "tao_say",
        "vai_vang": "vai_vang",
        "tinh_dau_hh": "tinh_dau_hh",
    }
    SELECTED_ITEM_ZONE = (680, 240, 180, 180)

    def __init__(
        self,
        selling: SellingActions,
        recognition: AutoVpRecognitionActions,
    ) -> None:
        self.selling = selling
        self.recognition = recognition
        self.context = selling.context
        self._next_item_index = 0
        self._insufficient_item_ids: set[str] = set()
        self._unsafe_item_ids: set[str] = set()

    def _open_and_scan_finished_goods(self) -> tuple[VpRecognition, ...]:
        """Click the basket tab and require repeated fresh-frame recognition."""
        basket_button = (450, 442)
        best_by_id: dict[str, VpRecognition] = {}
        for attempt in range(1, 4):
            self.context.ensure_running()
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

    def _next_candidate(
        self,
        recognized: tuple[VpRecognition, ...],
    ) -> VpRecognition | None:
        by_id = {item.item_id: item for item in recognized}
        for offset in range(len(self.ITEM_ORDER)):
            index = (self._next_item_index + offset) % len(self.ITEM_ORDER)
            item_id = self.ITEM_ORDER[index]
            if (
                item_id in self._insufficient_item_ids
                or item_id in self._unsafe_item_ids
            ):
                continue
            item = by_id.get(item_id)
            if item is None:
                continue
            self._next_item_index = index
            return item
        return None

    def _place_exact_ten(self, item: VpRecognition) -> str:
        """Return SOLD, BELOW_TEN or WRONG_ITEM without unsafe placement."""
        assert item.center is not None
        self.selling.vision.driver.click(*item.center)
        self.selling.waiter.sleep(0.30)
        try:
            self.selling.waiter.until(
                lambda: self.selling.vision.find(
                    "dat_ban",
                    threshold=0.78,
                    zone=self.selling.DAT_BAN_ZONE,
                ),
                timeout=4.0,
                interval=0.20,
                description="màn hình đặt bán AUTO",
            )
        except ScreenTimeout as exc:
            self.selling._cancel_dialog()
            raise TransactionError(
                f"{item.label} không mở được màn hình đặt bán"
            ) from exc

        selected_template = self.SELECTED_ITEM_TEMPLATES[item.item_id]
        selected_match = self.selling.vision.find(
            selected_template,
            threshold=0.78,
            zone=self.SELECTED_ITEM_ZONE,
            scales=(0.85, 1.0, 1.15, 1.30, 1.45),
        )
        if selected_match is None:
            self.context.log(
                f"AUTO bán VP • CHẶN SAI VP: dialog không đúng {item.label} • "
                "hủy và chuyển VP kế tiếp"
            )
            self.selling._cancel_dialog()
            return "WRONG_ITEM"

        quantity_passes = 0
        for quantity_attempt in range(1, 4):
            quantity_marker = self.selling.vision.find(
                "sl10",
                threshold=0.95,
                zone=self.selling.SL10_ZONE,
            )
            quantity_passes = (
                quantity_passes + 1 if quantity_marker is not None else 0
            )
            if quantity_passes >= 2:
                break
            if quantity_attempt < 3:
                self.selling.waiter.sleep(0.20)
        if quantity_passes < 2:
            self.context.log(
                f"AUTO bán VP • {item.label} còn dưới x10 • "
                "hủy và chuyển VP kế tiếp"
            )
            self.selling._cancel_dialog()
            return "BELOW_TEN"

        before = self.selling.vision.frame()[330:760, 180:820].copy()
        self.selling.vision.driver.click(*self.selling.PLACE_BUTTON)
        self.selling.waiter.settle(0.20)
        self.selling.vision.find(
            "dong_y",
            threshold=0.74,
            zone=self.selling.CONFIRM_ZONE,
            click=True,
        )

        best_change = 0.0
        deadline = time.monotonic() + 6.0
        while time.monotonic() < deadline:
            after = self.selling.vision.frame()[330:760, 180:820].copy()
            best_change = max(best_change, _mean_difference(before, after))
            if best_change >= self.selling.minimum_screen_change:
                self.context.log(
                    f"AUTO MAIN đã treo {item.label} x10 "
                    f"(match={item.score:.3f}, change={best_change:.2f})"
                )
                return "SOLD"
            self.selling.waiter.settle(0.20)
        self.selling._cancel_dialog(cancelable=False)
        raise TransactionError(
            f"Không xác nhận được thay đổi sau khi treo {item.label}"
        )

    def sell_next_allowed(self, *, storage_id: int = 2) -> AutoSaleAttempt:
        """Sell the next round-robin x10 item, skipping each insufficient type."""
        self.context.ensure_running()
        if int(storage_id) != 2:
            raise ValueError("AUTO Main chỉ bán VP từ kho thành phẩm số 2")

        for _candidate_attempt in range(len(self.ITEM_ORDER)):
            blocked_item_ids = (
                self._insufficient_item_ids | self._unsafe_item_ids
            )
            if len(blocked_item_ids) == len(self.ITEM_ORDER):
                return AutoSaleAttempt(status="NO_SAFE_EXACT_TEN_ITEMS")
            if not self.selling._find_empty_slot():
                return AutoSaleAttempt(status="NO_EMPTY_SLOT")

            recognized = self._open_and_scan_finished_goods()
            if not recognized:
                self.selling.close_inventory_read_only()
                return AutoSaleAttempt(status="NO_ALLOWED_ITEM")

            selected = self._next_candidate(recognized)
            if selected is None:
                self.selling.close_inventory_read_only()
                return AutoSaleAttempt(status="NO_SAFE_EXACT_TEN_ITEMS")

            self.context.log(
                f"AUTO bán VP • lượt cân bằng chọn {selected.label} • "
                f"score={selected.score:.3f}"
            )
            placement = self._place_exact_ten(selected)
            if placement != "SOLD":
                if placement == "BELOW_TEN":
                    self._insufficient_item_ids.add(selected.item_id)
                else:
                    self._unsafe_item_ids.add(selected.item_id)
                self._next_item_index = (
                    self.ITEM_ORDER.index(selected.item_id) + 1
                ) % len(self.ITEM_ORDER)
                continue

            self._next_item_index = (
                self.ITEM_ORDER.index(selected.item_id) + 1
            ) % len(self.ITEM_ORDER)
            return AutoSaleAttempt(
                status="SOLD",
                item_id=selected.item_id,
                label=selected.label,
                score=float(selected.score),
            )

        return AutoSaleAttempt(status="NO_EXACT_TEN_ITEMS")
