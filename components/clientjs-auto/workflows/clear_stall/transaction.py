from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Any, Callable, Iterable

from .detector import ICON_HALF_HEIGHT, ICON_HALF_WIDTH, VISIBLE_SLOT_CENTERS
from .manifest import ItemFingerprint, PurchasedItem, hamming_distance


PURCHASE_CONFIRM_TEMPLATES = (
    "buy_item",
    "mua_vat_pham",
    "mua",
    "xac_nhan",
    "dong_y",
)
SALE_CONFIRM_TEMPLATES = (
    "sell_item",
    "ban_vat_pham",
    "ban",
    "xac_nhan",
    "dong_y",
)
CANCEL_TEMPLATES = ("huy", "close_game", "close")


@dataclass(frozen=True)
class VerifiedAction:
    screen_change: float
    template_used: str
    slot_center: tuple[int, int]


class VisualTransactionExecutor:
    """Purchase and resell with visual proof around every state-changing click."""

    def __init__(
        self,
        controller: Any,
        *,
        stop_event: threading.Event,
        logger: Callable[[str], None],
        minimum_screen_change: float = 2.0,
        fingerprint_distance: int = 5,
    ) -> None:
        self.controller = controller
        self.driver = getattr(controller, "driver", None)
        self.processor = getattr(controller, "image_processor", None)
        if self.driver is None or self.processor is None:
            raise RuntimeError("AUTO PRO thiếu driver hoặc image processor")
        self.stop_event = stop_event
        self.log = logger
        self.minimum_screen_change = float(minimum_screen_change)
        self.fingerprint_distance = int(fingerprint_distance)

    def purchase_listing(self, item: PurchasedItem) -> VerifiedAction:
        """Buy one source listing and return only after visible confirmation."""
        self._ensure_running()
        center = self._slot_center(item.source_slot)
        before = self._region()
        self.driver.click(*center)
        template = self._wait_and_click(PURCHASE_CONFIRM_TEMPLATES, timeout=5.0)
        if not template:
            self._cancel_dialog()
            raise RuntimeError(
                f"Ô {item.source_slot} trang {item.source_page} không mở hộp mua"
            )
        change = self._wait_for_change(before, timeout=6.0)
        if change < self.minimum_screen_change:
            self._cancel_dialog()
            raise RuntimeError(
                f"Không xác nhận được giao dịch mua tại trang "
                f"{item.source_page}, ô {item.source_slot}"
            )
        self.log(
            f"Đã xác nhận giao diện thay đổi sau mua "
            f"(template={template}, change={change:.2f})"
        )
        return VerifiedAction(change, template, center)

    def find_inventory_match(
        self,
        fingerprint: ItemFingerprint,
    ) -> tuple[int, tuple[int, int], int] | None:
        """Return the closest visible inventory slot if it is an exact-safe match."""
        frame = self.driver.screenshot(format="opencv")
        best = None
        for slot, center in enumerate(VISIBLE_SLOT_CENTERS, start=1):
            crop = self._crop_icon(frame, center)
            candidate = ItemFingerprint.from_bgra(
                crop.tobytes(), crop.shape[1], crop.shape[0], ""
            )
            distance = hamming_distance(
                fingerprint.perceptual_hash, candidate.perceptual_hash
            )
            if best is None or distance < best[2]:
                best = (slot, center, distance)
        if best is None or best[2] > self.fingerprint_distance:
            return None
        return best

    def sell_manifest_item(self, item: PurchasedItem) -> VerifiedAction:
        """Sell only a visible inventory icon matching the purchased fingerprint."""
        self._ensure_running()
        match = self.find_inventory_match(item.fingerprint)
        if match is None:
            raise RuntimeError(
                f"Không tìm thấy đúng vật phẩm đã mua từ trang "
                f"{item.source_page}, ô {item.source_slot}"
            )
        slot, center, distance = match
        before = self._region()
        self.driver.click(*center)
        template = self._wait_and_click(SALE_CONFIRM_TEMPLATES, timeout=5.0)
        if not template:
            self._cancel_dialog()
            raise RuntimeError(
                f"Vật phẩm khớp ô kho {slot} nhưng không mở được hộp bán"
            )
        change = self._wait_for_change(before, timeout=6.0)
        if change < self.minimum_screen_change:
            self._cancel_dialog()
            raise RuntimeError(f"Không xác nhận được giao dịch bán tại ô kho {slot}")
        self.log(
            f"Đã bán vật phẩm khớp manifest tại ô {slot} "
            f"(distance={distance}, change={change:.2f})"
        )
        return VerifiedAction(change, template, center)

    def _wait_and_click(
        self,
        templates: Iterable[str],
        *,
        timeout: float,
    ) -> str:
        deadline = time.monotonic() + float(timeout)
        while time.monotonic() < deadline:
            self._ensure_running()
            for name in templates:
                try:
                    if self.processor.find_image(
                        name, threshold=0.84, click=True
                    ):
                        return name
                except Exception:
                    continue
            time.sleep(0.20)
        return ""

    def _wait_for_change(self, before, *, timeout: float) -> float:
        deadline = time.monotonic() + float(timeout)
        best = 0.0
        while time.monotonic() < deadline:
            self._ensure_running()
            after = self._region()
            best = max(best, _mean_difference(before, after))
            if best >= self.minimum_screen_change:
                return best
            time.sleep(0.20)
        return best

    def _cancel_dialog(self) -> None:
        for name in CANCEL_TEMPLATES:
            try:
                if self.processor.find_image(name, threshold=0.82, click=True):
                    return
            except Exception:
                continue
        press_back = getattr(self.controller, "press_back", None)
        if callable(press_back):
            try:
                press_back(self.stop_event)
            except TypeError:
                press_back()

    def _region(self):
        frame = self.driver.screenshot(format="opencv")
        return frame[330:760, 180:820].copy()

    @staticmethod
    def _slot_center(slot: int) -> tuple[int, int]:
        index = int(slot) - 1
        if not 0 <= index < len(VISIBLE_SLOT_CENTERS):
            raise ValueError(f"Ô vật phẩm không hợp lệ: {slot}")
        return VISIBLE_SLOT_CENTERS[index]

    @staticmethod
    def _crop_icon(frame, center: tuple[int, int]):
        x, y = center
        return frame[
            y - ICON_HALF_HEIGHT : y + ICON_HALF_HEIGHT,
            x - ICON_HALF_WIDTH : x + ICON_HALF_WIDTH,
        ].copy()

    def _ensure_running(self) -> None:
        if self.stop_event.is_set():
            raise InterruptedError("Dọn quầy đã được yêu cầu dừng")


def _mean_difference(first, second) -> float:
    try:
        import cv2
        return float(cv2.absdiff(first, second).mean())
    except Exception:
        first_raw, second_raw = first.tobytes(), second.tobytes()
        size = min(len(first_raw), len(second_raw))
        if size <= 0:
            return 0.0
        return sum(
            abs(first_raw[index] - second_raw[index])
            for index in range(size)
        ) / size
