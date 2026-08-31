from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
import time
from typing import Any, Callable, Iterable

from .detector import ICON_HALF_HEIGHT, ICON_HALF_WIDTH, VISIBLE_SLOT_CENTERS
from .manifest import (
    ItemFingerprint,
    PurchasedItem,
    RESALE_BATCH_SIZE,
    hamming_distance,
)


PURCHASE_CONFIRM_TEMPLATES = (
    "buy_item",
    "mua_vat_pham",
    "mua",
    "xac_nhan",
    "dong_y",
)
CANCEL_TEMPLATES = ("huy", "close_game", "close")

# Recovered AUTO PRO sellItems() geometry at the fixed 1000x1000 ClientJS size.
AUTO_PRO_INVENTORY_ZONE = (14, 345, 397, 379)
AUTO_PRO_DAT_BAN_ZONE = (662, 598, 231, 145)
AUTO_PRO_SL10_ZONE = (737, 426, 81, 81)
AUTO_PRO_CONFIRM_ZONE = (390, 552, 211, 102)
AUTO_PRO_PLACE_SALE = (771, 692)


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
        """Find the purchased VP inside AUTO PRO's recovered warehouse region."""
        frame = self.driver.screenshot(format="opencv")

        # First use the exact source icon captured during the friend-stall scan.
        # AUTO PRO sellItems() searches this left-side warehouse region rather
        # than the eight shop coordinates, so matching here is the primary path.
        template_path = Path(fingerprint.template_file)
        if template_path.is_file():
            try:
                import cv2

                template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
                if template is not None and template.size:
                    x, y, width, height = AUTO_PRO_INVENTORY_ZONE
                    zone = frame[y : y + height, x : x + width]
                    if zone.ndim == 3 and zone.shape[2] == 4:
                        zone = cv2.cvtColor(zone, cv2.COLOR_BGRA2BGR)
                    best_score = -1.0
                    best_center = None
                    for scale in (0.90, 0.95, 1.00, 1.05, 1.10):
                        scaled_w = max(8, int(template.shape[1] * scale))
                        scaled_h = max(8, int(template.shape[0] * scale))
                        if scaled_w > zone.shape[1] or scaled_h > zone.shape[0]:
                            continue
                        scaled = cv2.resize(
                            template,
                            (scaled_w, scaled_h),
                            interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR,
                        )
                        result = cv2.matchTemplate(
                            zone, scaled, cv2.TM_CCOEFF_NORMED
                        )
                        _minimum, maximum, _min_loc, max_loc = cv2.minMaxLoc(result)
                        if float(maximum) > best_score:
                            best_score = float(maximum)
                            best_center = (
                                x + max_loc[0] + scaled_w // 2,
                                y + max_loc[1] + scaled_h // 2,
                            )
                    if best_center is not None and best_score >= 0.72:
                        distance = max(0, int(round((1.0 - best_score) * 64)))
                        return 0, best_center, distance
            except Exception:
                pass

        # Conservative fallback for older captures where the saved template is
        # unavailable. This keeps the previous pHash behaviour as a recovery path.
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

    def sell_manifest_batch(
        self,
        fingerprint: ItemFingerprint,
        quantity: int = RESALE_BATCH_SIZE,
    ) -> VerifiedAction:
        """Place exactly ten VP into one empty own-stall slot using AUTO PRO flow."""
        if int(quantity) != RESALE_BATCH_SIZE:
            raise ValueError("Dọn quầy chỉ treo đúng 10 VP cho mỗi ô quầy")
        self._ensure_running()
        match = self.find_inventory_match(fingerprint)
        if match is None:
            raise RuntimeError("Không tìm thấy đúng loại VP cần treo bán trong kho")
        slot, center, distance = match

        # AUTO PRO sellItems() first opens the item, waits for dat_ban, then
        # requires the sl10 marker before pressing the place-sale button.
        self.driver.click(*center)
        if not self._wait_for_template(
            "dat_ban",
            timeout=4.0,
            threshold=0.84,
            search_zone=AUTO_PRO_DAT_BAN_ZONE,
        ):
            self._cancel_dialog()
            raise RuntimeError(
                f"VP ở ô kho {slot} không mở được màn hình đặt bán"
            )
        if not self._wait_for_template(
            "sl10",
            timeout=2.5,
            threshold=0.82,
            search_zone=AUTO_PRO_SL10_ZONE,
        ):
            self._cancel_dialog()
            raise RuntimeError(
                "Loại VP được manifest tính đủ 10 nhưng AUTO PRO không thấy sl10"
            )

        before = self._region()
        self.driver.click(*AUTO_PRO_PLACE_SALE)
        # Some warehouse groups have an additional confirmation in the old
        # AUTO PRO flow. Click it only when it actually appears.
        self._wait_for_template(
            "dong_y",
            timeout=1.2,
            threshold=0.82,
            search_zone=AUTO_PRO_CONFIRM_ZONE,
            click=True,
        )
        change = self._wait_for_change(before, timeout=6.0)
        if change < self.minimum_screen_change:
            self._cancel_dialog()
            raise RuntimeError(f"Không xác nhận được lô bán 10 VP tại ô kho {slot}")
        self.log(
            f"Đã treo 10 VP vào một ô quầy "
            f"(ô kho={slot}, distance={distance}, change={change:.2f})"
        )
        return VerifiedAction(change, "sl10", center)

    def sell_manifest_item(self, item: PurchasedItem) -> VerifiedAction:
        """Backward-compatible wrapper; clear-stall resale uses ten-VP batches."""
        return self.sell_manifest_batch(item.fingerprint, RESALE_BATCH_SIZE)

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

    def _wait_for_template(
        self,
        name: str,
        *,
        timeout: float,
        threshold: float,
        search_zone: tuple[int, int, int, int] | None = None,
        click: bool = False,
    ) -> bool:
        deadline = time.monotonic() + float(timeout)
        while time.monotonic() < deadline:
            self._ensure_running()
            kwargs = {
                "threshold": float(threshold),
                "click": bool(click),
            }
            if search_zone is not None:
                kwargs["search_zone"] = search_zone
            try:
                if self.processor.find_image(name, **kwargs):
                    return True
            except Exception:
                pass
            time.sleep(0.20)
        return False

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
