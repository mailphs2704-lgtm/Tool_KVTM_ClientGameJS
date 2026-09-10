from __future__ import annotations

from dataclasses import dataclass
import time

from ..errors import ScreenTimeout, TransactionError
from .item_recognition import AutoVpRecognitionActions, VpRecognition
from .selling import SellingActions, _mean_difference


__all__ = ["AutoSaleAttempt", "AutoMainSellingActions"]
FILE_FUNCTIONS = (
    "Tìm một ô trống trong view quầy hiện tại",
    "Chờ bảng Kho READY rồi chọn chính xác Kho thành phẩm storage2",
    "Hậu kiểm thay đổi vùng hàng hóa sau click storage2 và retry có giới hạn",
    "Quét lại ba fresh frame mà không toggle bảng kho",
    "Chỉ chọn VP được Function hiện tại cho phép",
    "Bắt buộc xác nhận số lượng x10 bằng template đa scale trên hai frame trước khi đặt bán",
    "Bỏ qua loại còn dưới x10 và chuyển sang loại kế tiếp trong cùng bảng kho",
    "Hủy dialog có xác minh rồi tiếp tục trong cùng kho đang mở",
    "Xác minh màn hình đặt bán bằng dat_ban hoặc nút cam native-500 rồi mới click",
    "Xác minh màn hình thay đổi trước khi ghi nhận đã treo",
    "Nếu không có VP hợp lệ thì đóng kho một lần và trả quyền về scheduler",
)


@dataclass(frozen=True)
class AutoSaleAttempt:
    status: str
    item_id: str = ""
    label: str = ""
    score: float = 0.0


class AutoMainSellingActions:
    """Balanced exact-x10 AUTO sale, isolated from clear-stall accounting.

    ``ITEM_ORDER`` remains the proven Function-1 default. AUTO Builder may pass
    an explicit order from the Function catalog, but it cannot introduce an item
    that this action does not know how to post-verify in the sale dialog.
    """

    ITEM_ORDER = ("tao_say", "vai_vang")
    SELECTED_ITEM_TEMPLATES = {
        "tao_say": "tao_say",
        "vai_vang": "vai_vang",
    }
    SELECTED_ITEM_ZONE = (680, 240, 180, 180)
    SALE_CHANGE_ZONE = (180, 330, 640, 430)

    # sl10 is a small reference asset. At native 500 the exact 0.95 single-scale
    # gate was too brittle even when the live quantity field visibly showed 10.
    # Keep it fail-closed by requiring two consecutive matches, but permit the
    # expected native scaling/antialiasing range.
    EXACT_TEN_THRESHOLD = 0.78
    EXACT_TEN_SCALES = (0.75, 0.90, 1.00, 1.10, 1.25, 1.40, 1.55)
    EXACT_TEN_REQUIRED_PASSES = 2
    FINISHED_GOODS_SCAN_ATTEMPTS = 3

    def __init__(
        self,
        selling: SellingActions,
        recognition: AutoVpRecognitionActions,
        *,
        item_order: tuple[str, ...] | None = None,
    ) -> None:
        self.selling = selling
        self.recognition = recognition
        self.context = selling.context
        requested = tuple(item_order or type(self).ITEM_ORDER)
        if not requested:
            raise ValueError("AUTO bán VP cần ít nhất một VP được Function cho phép")
        unsupported = [
            item_id for item_id in requested
            if item_id not in self.SELECTED_ITEM_TEMPLATES
        ]
        if unsupported:
            raise ValueError(
                "AUTO bán VP chưa có hậu kiểm an toàn cho: " + ", ".join(unsupported)
            )
        self.ITEM_ORDER = requested
        self._next_item_index = 0
        self._insufficient_item_ids: set[str] = set()
        self._unsafe_item_ids: set[str] = set()

    def _sale_change_crop(self):
        """Capture the destructive-sale verification ROI in logical 1000 units."""
        frame = self.selling.vision.frame()
        x, y, width, height = self.selling.vision.logical_zone_to_frame(
            self.SALE_CHANGE_ZONE, frame
        )
        return frame[y : y + height, x : x + width].copy()

    def _open_and_scan_finished_goods(self) -> tuple[VpRecognition, ...]:
        """Wait for the picker, select storage2, then retry recognition frames.

        ``_find_empty_slot()`` opens the inventory picker asynchronously.  The old
        implementation immediately clicked logical (450,442), so on native 500
        that click could be consumed while the picker was still opening and the UI
        remained on its default warehouse.  The shared inventory action now proves
        the picker first, targets kho_thanh_pham, and retries the same idempotent tab
        click with content-change evidence before this scan begins.
        """
        # Legacy verifier migration marker only; runtime no longer blind-clicks it:
        # basket_button = (450, 442)
        self.context.ensure_running()
        change = self.selling.inventory.select_storage_after_picker_ready(2)
        self.context.log(
            "AUTO bán VP • Kho thành phẩm storage2 READY • "
            f"content_change={change:.2f} • "
            f"scan_fresh_frames={self.FINISHED_GOODS_SCAN_ATTEMPTS}"
        )
        self.selling.waiter.sleep(0.20)

        best_by_id: dict[str, VpRecognition] = {}
        for attempt in range(1, self.FINISHED_GOODS_SCAN_ATTEMPTS + 1):
            self.context.ensure_running()
            if attempt > 1:
                self.selling.waiter.sleep(0.40)
            for item in self.recognition.scan_samples(log_prefix="AUTO SELL VP"):
                if not item.found or item.center is None:
                    continue
                previous = best_by_id.get(item.item_id)
                if previous is None or item.score > previous.score:
                    best_by_id[item.item_id] = item
            if best_by_id:
                self.context.log(
                    f"AUTO bán VP • Kho thành phẩm scan PASS • "
                    f"frame={attempt}/{self.FINISHED_GOODS_SCAN_ATTEMPTS} • "
                    f"candidates={len(best_by_id)}"
                )
                return tuple(best_by_id.values())
            self.context.detail(
                "AUTO bán VP • Kho thành phẩm fresh-frame MISS • "
                f"frame={attempt}/{self.FINISHED_GOODS_SCAN_ATTEMPTS} • "
                "không toggle bảng kho"
            )

        self.context.log(
            "AUTO bán VP • Kho thành phẩm không có VP Function hợp lệ sau "
            f"{self.FINISHED_GOODS_SCAN_ATTEMPTS} fresh frame • đóng kho và tiếp tục AUTO"
        )
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

    def _cancel_selected_item(self) -> None:
        """Close the sale dialog safely and restore the inventory picker."""
        for attempt in range(1, 4):
            self.context.ensure_running()
            close_match = self.selling.vision.find_any(
                ("close_game", "close", "x_popup_event"),
                threshold=0.72,
                zone=(930, 0, 70, 70),
                click=True,
            )
            if close_match is None:
                self.selling.vision.driver.click(968, 28)
            self.selling.waiter.sleep(0.45)

            if self.selling.is_sale_dialog_ready():
                continue

            inventory_open = self.selling.vision.find(
                "kho_thanh_pham",
                threshold=0.72,
                zone=self.selling.inventory.STORAGE_ZONE,
            )
            if inventory_open is None:
                if not self.selling._find_empty_slot():
                    continue
                self.selling.waiter.sleep(0.35)
                self.selling.inventory.select_storage_after_picker_ready(2)

            self.context.log(
                f"AUTO bán VP • đã hủy dialog và khôi phục kho • "
                f"lần {attempt}/3"
            )
            return
        raise ScreenTimeout(
            "Không hủy và khôi phục được kho bán VP; dừng trước khi thao tác tiếp"
        )

    def _place_exact_ten(self, item: VpRecognition) -> str:
        """Return SOLD, BELOW_TEN or WRONG_ITEM without unsafe placement."""
        assert item.center is not None
        self.selling.vision.driver.click(*item.center)
        self.selling.waiter.sleep(0.30)
        try:
            self.selling.wait_sale_dialog_ready(
                timeout=4.0,
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
            self._cancel_selected_item()
            return "WRONG_ITEM"

        quantity_passes = 0
        best_quantity_score = 0.0
        for quantity_attempt in range(1, 4):
            quantity_marker = self.selling.vision.find(
                "sl10",
                threshold=self.EXACT_TEN_THRESHOLD,
                zone=self.selling.SL10_ZONE,
                scales=self.EXACT_TEN_SCALES,
                click=False,
            )
            if quantity_marker is not None:
                quantity_passes += 1
                best_quantity_score = max(
                    best_quantity_score,
                    float(quantity_marker.score),
                )
                self.context.detail(
                    "AUTO sale x10 proof | "
                    f"attempt={quantity_attempt}/3 | "
                    f"passes={quantity_passes}/{self.EXACT_TEN_REQUIRED_PASSES} | "
                    f"score={quantity_marker.score:.3f}"
                )
            else:
                quantity_passes = 0
                self.context.detail(
                    "AUTO sale x10 proof | "
                    f"attempt={quantity_attempt}/3 | passes reset=0 | marker=MISS"
                )
            if quantity_passes >= self.EXACT_TEN_REQUIRED_PASSES:
                break
            if quantity_attempt < 3:
                self.selling.waiter.sleep(0.20)
        if quantity_passes < self.EXACT_TEN_REQUIRED_PASSES:
            self.context.log(
                f"AUTO bán VP • {item.label} chưa chứng minh được x10 • "
                f"best_score={best_quantity_score:.3f} • "
                f"threshold={self.EXACT_TEN_THRESHOLD:.2f} • "
                "hủy và chuyển VP kế tiếp"
            )
            self._cancel_selected_item()
            return "BELOW_TEN"

        self.context.log(
            f"AUTO bán VP • {item.label} • sale dialog READY + x10 PASS • "
            f"quantity_score={best_quantity_score:.3f} • click Đặt bán"
        )
        before = self._sale_change_crop()
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
            after = self._sale_change_crop()
            best_change = max(best_change, _mean_difference(before, after))
            if best_change >= self.selling.minimum_screen_change:
                self.context.log(
                    f"AUTO MAIN đã treo {item.label} x10 "
                    f"(match={item.score:.3f}, quantity={best_quantity_score:.3f}, "
                    f"change={best_change:.2f})"
                )
                return "SOLD"
            self.selling.waiter.settle(0.20)
        self.selling._cancel_dialog(cancelable=False)
        raise TransactionError(
            f"Không xác nhận được thay đổi sau khi treo {item.label}"
        )

    def sell_next_allowed(self, *, storage_id: int = 2) -> AutoSaleAttempt:
        """Open finished-goods once and check every allowed type in that picker."""
        self.context.ensure_running()
        if int(storage_id) != 2:
            raise ValueError("AUTO Main chỉ bán VP từ kho thành phẩm số 2")
        if not self.selling._find_empty_slot():
            return AutoSaleAttempt(status="NO_EMPTY_SLOT")

        recognized = self._open_and_scan_finished_goods()
        if not recognized:
            self.selling.close_inventory_read_only()
            return AutoSaleAttempt(status="NO_ALLOWED_ITEM")

        for checked_count in range(1, len(self.ITEM_ORDER) + 1):
            blocked_item_ids = (
                self._insufficient_item_ids | self._unsafe_item_ids
            )
            if len(blocked_item_ids) == len(self.ITEM_ORDER):
                self.selling.close_inventory_read_only()
                return AutoSaleAttempt(status="NO_SAFE_EXACT_TEN_ITEMS")

            selected = self._next_candidate(recognized)
            if selected is None:
                self.selling.close_inventory_read_only()
                return AutoSaleAttempt(status="NO_SAFE_EXACT_TEN_ITEMS")

            self.context.log(
                f"AUTO bán VP • kiểm tra {checked_count}/{len(self.ITEM_ORDER)} • "
                f"chọn {selected.label} • score={selected.score:.3f}"
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

        self.selling.close_inventory_read_only()
        return AutoSaleAttempt(status="NO_SAFE_EXACT_TEN_ITEMS")
