from __future__ import annotations

from pathlib import Path
import threading
import time
from typing import Callable

from .detector import (
    FRIEND_PURCHASE_CLICK_CENTERS,
    ICON_HALF_HEIGHT,
    ICON_HALF_WIDTH,
    VISIBLE_SLOT_CENTERS,
)
from .manifest import ItemFingerprint, PurchasedItem, RESALE_BATCH_SIZE, hamming_distance
from .native_runtime import ClearStallNativeRuntime


AUTO_PRO_PURCHASE_FULL_ZONE = (669, 351, 91, 88)
AUTO_PRO_OWN_EMPTY_STALL_ZONE = (196, 340, 599, 395)
AUTO_PRO_INVENTORY_ZONE = (14, 345, 397, 379)
AUTO_PRO_DAT_BAN_ZONE = (662, 598, 231, 145)
AUTO_PRO_SL10_ZONE = (737, 426, 81, 81)
AUTO_PRO_CONFIRM_ZONE = (390, 552, 211, 102)
AUTO_PRO_PLACE_SALE = (771, 692)


class NoEmptyStallSlot(RuntimeError):
    pass


class NativeTransactionExecutor:
    """Pure-Python implementation of AUTO PRO's buy/resale order."""

    def __init__(
        self,
        runtime: ClearStallNativeRuntime,
        *,
        stop_event: threading.Event,
        logger: Callable[[str], None],
        fingerprint_distance: int = 5,
    ) -> None:
        self.runtime = runtime
        self.driver = runtime.driver
        self.matcher = runtime.matcher
        self.stop_event = stop_event
        self.log = logger
        self.fingerprint_distance = int(fingerprint_distance)

    def source_listing_matches(self, item: PurchasedItem) -> bool:
        self._ensure_running()
        index = int(item.source_slot) - 1
        if not 0 <= index < len(VISIBLE_SLOT_CENTERS):
            return False
        frame = self.runtime.screenshot()
        crop = self._crop_icon(frame, VISIBLE_SLOT_CENTERS[index])
        if getattr(crop, "size", 0) == 0:
            return False
        candidate = ItemFingerprint.from_bgra(crop.tobytes(), crop.shape[1], crop.shape[0], "")
        return hamming_distance(
            item.fingerprint.perceptual_hash,
            candidate.perceptual_hash,
        ) <= self.fingerprint_distance

    def purchase_listing(self, item: PurchasedItem):
        """Buy one VP with the recovered direct-click behavior."""
        self._ensure_running()
        center = self._slot_center(item.source_slot)
        before = self._region()
        self.driver.click(*center)
        self._sleep(0.50)

        try:
            full = self.matcher.find(
                "x",
                threshold=0.78,
                zone=AUTO_PRO_PURCHASE_FULL_ZONE,
            )
        except FileNotFoundError:
            full = None
        if full is not None:
            raise RuntimeError("Kho clone đã đầy trong lúc mua VP nhà bạn")

        change = self._mean_difference(before, self._region())
        self.log(
            f"Đã click mua 1 VP: view={item.source_page}, ô={item.source_slot}, "
            f"change={change:.2f}"
        )
        return change

    def find_inventory_match(self, fingerprint: ItemFingerprint):
        """Find the exact purchased VP in the clone inventory."""
        import cv2

        frame = self.runtime.screenshot()
        template_path = Path(fingerprint.template_file)
        if template_path.is_file():
            template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
            if template is not None and template.size:
                x, y, width, height = AUTO_PRO_INVENTORY_ZONE
                zone = frame[y:y + height, x:x + width]
                best_score = -1.0
                best_center = None
                for scale in (0.90, 0.95, 1.0, 1.05, 1.10):
                    sw = max(8, int(template.shape[1] * scale))
                    sh = max(8, int(template.shape[0] * scale))
                    if sw > zone.shape[1] or sh > zone.shape[0]:
                        continue
                    resized = cv2.resize(
                        template,
                        (sw, sh),
                        interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR,
                    )
                    result = cv2.matchTemplate(zone, resized, cv2.TM_CCOEFF_NORMED)
                    _mn, mx, _mnloc, mxloc = cv2.minMaxLoc(result)
                    if float(mx) > best_score:
                        best_score = float(mx)
                        best_center = (x + mxloc[0] + sw // 2, y + mxloc[1] + sh // 2)
                if best_center is not None and best_score >= 0.72:
                    return best_center, best_score

        best = None
        for center in VISIBLE_SLOT_CENTERS:
            crop = self._crop_icon(frame, center)
            if getattr(crop, "size", 0) == 0:
                continue
            candidate = ItemFingerprint.from_bgra(crop.tobytes(), crop.shape[1], crop.shape[0], "")
            distance = hamming_distance(fingerprint.perceptual_hash, candidate.perceptual_hash)
            if best is None or distance < best[1]:
                best = (center, distance)
        if best is None or best[1] > self.fingerprint_distance:
            return None
        return best[0], 1.0 - best[1] / 64.0

    def sell_manifest_batch(self, fingerprint: ItemFingerprint, quantity: int = RESALE_BATCH_SIZE):
        if int(quantity) != RESALE_BATCH_SIZE:
            raise ValueError("Dọn quầy chỉ treo đúng 10 VP mỗi ô")
        self._ensure_running()

        empty = self._wait_template(
            "quaytrong",
            timeout=2.0,
            threshold=0.68,
            zone=AUTO_PRO_OWN_EMPTY_STALL_ZONE,
        )
        if empty is None:
            raise NoEmptyStallSlot("Quầy clone hiện không còn ô trống")
        self.driver.click(*empty.center)
        self._sleep(0.25)

        inventory = self.find_inventory_match(fingerprint)
        if inventory is None:
            self._cancel_dialog()
            raise RuntimeError("Không tìm thấy đúng VP vừa mua trong kho clone")
        center, score = inventory
        self.driver.click(*center)

        if self._wait_template("dat_ban", timeout=4.0, threshold=0.76, zone=AUTO_PRO_DAT_BAN_ZONE) is None:
            self._cancel_dialog()
            raise RuntimeError("Không mở được màn hình đặt bán")
        if self._wait_template("sl10", timeout=3.0, threshold=0.58, zone=AUTO_PRO_SL10_ZONE) is None:
            self._cancel_dialog()
            raise RuntimeError("VP chưa đủ 10 hoặc không nhận dạng được sl10")

        before = self._region()
        self.driver.click(*AUTO_PRO_PLACE_SALE)
        confirm = self._wait_template("dong_y", timeout=1.2, threshold=0.72, zone=AUTO_PRO_CONFIRM_ZONE)
        if confirm is not None:
            self.driver.click(*confirm.center)
        change = self._wait_change(before, timeout=5.0)
        if change < 1.0:
            self._cancel_dialog()
            raise RuntimeError("Không xác nhận được lô bán 10 VP")
        self.log(f"Đã treo 10 VP (inventory_score={score:.3f}, change={change:.2f})")
        return change

    def sell_manifest_item(self, item: PurchasedItem):
        return self.sell_manifest_batch(item.fingerprint, RESALE_BATCH_SIZE)

    def _wait_template(self, name: str, *, timeout: float, threshold: float, zone=None):
        deadline = time.monotonic() + float(timeout)
        while time.monotonic() < deadline:
            self._ensure_running()
            try:
                match = self.matcher.find(name, threshold=threshold, zone=zone)
            except FileNotFoundError:
                return None
            if match is not None:
                return match
            self._sleep(0.18)
        return None

    def _cancel_dialog(self) -> None:
        for name in ("huy", "close_game", "close", "x_popup_event"):
            try:
                match = self.matcher.find(name, threshold=0.62)
            except FileNotFoundError:
                continue
            if match is not None:
                self.driver.click(*match.center)
                return
        self.driver.press("back")

    def _region(self):
        return self.runtime.screenshot()[330:760, 180:820].copy()

    def _wait_change(self, before, *, timeout: float) -> float:
        deadline = time.monotonic() + float(timeout)
        best = 0.0
        while time.monotonic() < deadline:
            self._ensure_running()
            best = max(best, self._mean_difference(before, self._region()))
            if best >= 1.0:
                return best
            self._sleep(0.18)
        return best

    @staticmethod
    def _mean_difference(first, second) -> float:
        import cv2
        return float(cv2.absdiff(first, second).mean())

    @staticmethod
    def _slot_center(slot: int):
        index = int(slot) - 1
        if not 0 <= index < len(FRIEND_PURCHASE_CLICK_CENTERS):
            raise ValueError(f"Ô vật phẩm không hợp lệ: {slot}")
        return FRIEND_PURCHASE_CLICK_CENTERS[index]

    @staticmethod
    def _crop_icon(frame, center):
        x, y = center
        return frame[
            y - ICON_HALF_HEIGHT:y + ICON_HALF_HEIGHT,
            x - ICON_HALF_WIDTH:x + ICON_HALF_WIDTH,
        ].copy()

    def _sleep(self, seconds: float) -> None:
        deadline = time.monotonic() + max(0.0, float(seconds))
        while time.monotonic() < deadline:
            self._ensure_running()
            time.sleep(min(0.05, deadline - time.monotonic()))

    def _ensure_running(self) -> None:
        if self.stop_event.is_set():
            raise InterruptedError("Dọn quầy đã được yêu cầu dừng")
