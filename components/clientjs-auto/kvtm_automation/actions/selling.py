from __future__ import annotations

import time

from ..context import AutomationContext
from ..errors import (
    InsufficientBatch,
    NoEmptyStallSlot,
    ScreenTimeout,
    TransactionError,
)
from ..models import VisualFingerprint
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter
from .inventory import InventoryActions


class SellingActions:
    """Place verified VP stacks while keeping logical 1000 geometry canonical."""

    EMPTY_STALL_ZONE = (196, 340, 599, 395)
    DAT_BAN_ZONE = (662, 598, 231, 145)
    SL10_ZONE = (737, 426, 81, 81)
    CONFIRM_ZONE = (390, 552, 211, 102)
    PLACE_BUTTON = (771, 692)
    PLACE_BUTTON_ZONE = (700, 650, 180, 90)
    SALE_CHANGE_ZONE = (180, 330, 640, 430)
    OWN_STALL_ACTIVE_ZONE = (319, 249, 386, 120)

    # Native-500 keeps the live-calibrated tolerant sale-dialog proof.
    N500_SALE_DIALOG_THRESHOLD = 0.68
    N500_SALE_DIALOG_SCALES = (0.85, 1.00, 1.15, 1.30, 1.45, 1.60, 1.75)
    N500_SALE_BUTTON_ORANGE_MIN = 0.08
    N500_OWN_STALL_THRESHOLD = 0.80

    # Native-1000 follows the recovered pre-500 AUTO-PRO contract.
    N1000_SALE_DIALOG_THRESHOLD = 0.78
    N1000_SALE_DIALOG_SCALES = (1.00,)
    N1000_OWN_STALL_THRESHOLD = 0.90

    EXACT_PURCHASE_MATCH_THRESHOLD = 0.60

    def __init__(
        self,
        context: AutomationContext,
        vision: VisionEngine,
        waiter: Waiter,
        inventory: InventoryActions,
        *,
        minimum_screen_change: float = 2.0,
    ) -> None:
        self.context = context
        self.vision = vision
        self.waiter = waiter
        self.inventory = inventory
        self.minimum_screen_change = float(minimum_screen_change)

    def native_size(self) -> tuple[int, int]:
        size = getattr(self.vision.driver, "native_size", None)
        if size is not None:
            return tuple(map(int, size))
        frame = self.vision.frame()
        height, width = frame.shape[:2]
        return int(width), int(height)

    def _is_native_500(self) -> bool:
        return self.native_size() == (500, 500)

    def _sale_dialog_profile(self) -> tuple[float, tuple[float, ...], bool]:
        if self._is_native_500():
            return (
                self.N500_SALE_DIALOG_THRESHOLD,
                self.N500_SALE_DIALOG_SCALES,
                True,
            )
        return (
            self.N1000_SALE_DIALOG_THRESHOLD,
            self.N1000_SALE_DIALOG_SCALES,
            False,
        )

    def _sale_change_crop(self):
        frame = self.vision.frame()
        x, y, width, height = self.vision.logical_zone_to_frame(
            self.SALE_CHANGE_ZONE, frame
        )
        return frame[y : y + height, x : x + width].copy()

    def _sale_button_orange_ratio(self, frame=None) -> float:
        import numpy as np

        source = self.vision.frame() if frame is None else frame
        x, y, width, height = self.vision.logical_zone_to_frame(
            self.PLACE_BUTTON_ZONE, source
        )
        roi = source[y : y + height, x : x + width]
        if roi is None or getattr(roi, "size", 0) == 0 or roi.ndim < 3:
            return 0.0
        blue = roi[:, :, 0].astype("int16")
        green = roi[:, :, 1].astype("int16")
        red = roi[:, :, 2].astype("int16")
        orange = (
            (red > 150)
            & (green > 60)
            & (blue < 110)
            & (red > green + 20)
            & (red > blue + 80)
            & (green > blue + 20)
        )
        return float(np.mean(orange))

    def is_sale_dialog_ready(self, frame=None) -> bool:
        """Use the recognition table that matches the current native ClientJS."""
        source = self.vision.frame() if frame is None else frame
        threshold, scales, allow_orange = self._sale_dialog_profile()
        marker = self.vision.find(
            "dat_ban",
            threshold=threshold,
            zone=self.DAT_BAN_ZONE,
            scales=scales,
            click=False,
            frame=source,
        )
        if marker is not None:
            self.context.detail(
                "AUTO sale dialog proof | source=dat_ban-template | "
                f"native={self.native_size()[0]}x{self.native_size()[1]} | "
                f"score={marker.score:.3f} | threshold={threshold:.2f}"
            )
            return True

        if allow_orange:
            orange_ratio = self._sale_button_orange_ratio(source)
            if orange_ratio >= self.N500_SALE_BUTTON_ORANGE_MIN:
                self.context.detail(
                    "AUTO sale dialog proof | source=native-500-orange-button | "
                    f"orange_ratio={orange_ratio:.3f} | "
                    f"min={self.N500_SALE_BUTTON_ORANGE_MIN:.3f}"
                )
                return True
        return False

    def wait_sale_dialog_ready(
        self,
        *,
        timeout: float = 4.0,
        description: str = "màn hình đặt bán",
    ) -> None:
        self.waiter.until(
            lambda: self.is_sale_dialog_ready(),
            timeout=float(timeout),
            interval=0.20,
            description=description,
        )

    def find_empty_slot(self, *, click: bool = False):
        """Find an empty stall slot; AUTO Main can prove first then click once."""
        for name in ("quaytrong", "quay_trong"):
            match = self.vision.find(
                name,
                threshold=0.66,
                zone=self.EMPTY_STALL_ZONE,
                scales=(0.85, 0.92, 1.0, 1.08, 1.15),
                click=False,
            )
            if match is None:
                continue
            if click:
                self.vision.driver.click(*match.center)
            return match
        return None

    def _find_empty_slot(self) -> bool:
        """Compatibility wrapper for existing non-AUTO-Main transactions."""
        return self.find_empty_slot(click=True) is not None

    def wait_own_stall_ready(
        self,
        *,
        timeout: float = 4.0,
        required_passes: int = 2,
        description: str = "quầy clone sẵn sàng",
    ):
        """Require stable own-stall state before an empty-slot click is allowed."""
        native = self.native_size()
        threshold = (
            self.N500_OWN_STALL_THRESHOLD
            if native == (500, 500)
            else self.N1000_OWN_STALL_THRESHOLD
        )
        deadline = time.monotonic() + float(timeout)
        passes = 0
        best = None
        while time.monotonic() < deadline:
            self.context.ensure_running()
            frame = self.vision.frame()
            marker = self.vision.find(
                "quay_hang_on",
                threshold=threshold,
                zone=self.OWN_STALL_ACTIVE_ZONE,
                click=False,
                frame=frame,
            )
            dialog_open = self.is_sale_dialog_ready(frame=frame)
            if marker is not None and not dialog_open:
                passes += 1
                if best is None or marker.score > best.score:
                    best = marker
                self.context.detail(
                    "AUTO bán VP • OWN_STALL proof • "
                    f"native={native[0]}x{native[1]} • "
                    f"passes={passes}/{required_passes} • score={marker.score:.3f}"
                )
                if passes >= max(1, int(required_passes)):
                    self.context.log(
                        "AUTO bán VP • OWN_STALL READY • "
                        f"native={native[0]}x{native[1]} • score={best.score:.3f}"
                    )
                    return best
            else:
                passes = 0
            self.waiter.sleep(0.15)
        raise ScreenTimeout(
            f"Không đạt {description} sau {float(timeout):.1f}s; "
            f"native={native[0]}x{native[1]}"
        )

    def open_inventory_read_only(self, *, storage_id: int = 2) -> None:
        self.context.ensure_running()
        if not self._find_empty_slot():
            raise NoEmptyStallSlot("Quầy clone không còn ô trống để mở kho")
        self.waiter.sleep(0.25)
        self.inventory.select_storage(storage_id)
        self.context.log("Đã mở kho bán ở chế độ READ-ONLY")

    def close_inventory_read_only(self, timeout: float = 6.0) -> None:
        deadline = time.monotonic() + float(timeout)
        attempts = 0
        while time.monotonic() < deadline:
            self.context.ensure_running()
            parent = self.vision.find(
                "quay_hang_on",
                threshold=(
                    self.N500_OWN_STALL_THRESHOLD
                    if self._is_native_500()
                    else self.N1000_OWN_STALL_THRESHOLD
                ),
                zone=self.OWN_STALL_ACTIVE_ZONE,
                click=False,
            )
            if parent is not None:
                self.context.log(
                    "Đã đóng kho kiểm tra READ-ONLY • "
                    f"quay_hang_on={parent.score:.3f}"
                )
                return

            attempts += 1
            close_match = self.vision.find_any(
                ("close_game", "close", "x_popup_event"),
                threshold=0.72,
                zone=(930, 0, 70, 70),
                click=True,
            )
            if close_match is None:
                self.vision.driver.click(968, 28)
            self.context.detail(
                f"AUTO kho • đóng READ-ONLY • attempt={attempts} • "
                f"source={'template-x' if close_match is not None else 'fallback-x'}"
            )
            self.waiter.sleep(0.35)

        raise ScreenTimeout(
            "Không đóng được kho READ-ONLY về quầy clone sau "
            f"{attempts} lần; quay_hang_on chưa trở lại"
        )

    def _finish_batch_from_match(
        self,
        center: tuple[int, int],
        score: float,
    ) -> None:
        self.vision.driver.click(*center)
        self.waiter.sleep(0.30)

        try:
            self.wait_sale_dialog_ready(timeout=4.0, description="màn hình đặt bán")
        except ScreenTimeout as exc:
            self._cancel_dialog()
            raise TransactionError("VP không mở được màn hình đặt bán") from exc

        quantity_marker = self.vision.find(
            "sl10", threshold=0.62, zone=self.SL10_ZONE
        )
        self.context.log(
            "CLEAR_STALL resale quantity marker "
            + ("x10-found" if quantity_marker is not None else "not-required")
        )

        before = self._sale_change_crop()
        self.vision.driver.click(*self.PLACE_BUTTON)
        self.waiter.settle(0.20)
        self.vision.find(
            "dong_y",
            threshold=0.74,
            zone=self.CONFIRM_ZONE,
            click=True,
        )

        best_change = 0.0
        deadline = time.monotonic() + 6.0
        while time.monotonic() < deadline:
            after = self._sale_change_crop()
            best_change = max(best_change, _mean_difference(before, after))
            if best_change >= self.minimum_screen_change:
                self.context.log(
                    "Đã treo VP đã mua "
                    f"(inventory-match={score:.3f}, change={best_change:.2f})"
                )
                return
            self.waiter.settle(0.20)
        self._cancel_dialog(cancelable=False)
        raise TransactionError("Không xác nhận được thay đổi sau khi treo VP")

    def sell_batch_of_ten(
        self,
        fingerprint: VisualFingerprint,
        *,
        storage_id: int,
    ) -> None:
        self.context.ensure_running()
        if not self._find_empty_slot():
            raise NoEmptyStallSlot("Quầy clone không còn ô trống")
        self.waiter.sleep(0.25)

        self.inventory.select_storage(storage_id)
        match = self.inventory.find_fingerprint(fingerprint, threshold=0.68)
        if match is None:
            self._cancel_dialog()
            raise TransactionError("Không tìm thấy đúng loại VP cần treo trong kho")
        center, score = match
        self._finish_batch_from_match(center, score)

    def sell_one_of_exact_purchases(
        self,
        fingerprints: list[VisualFingerprint],
        *,
        storage_id: int,
    ) -> VisualFingerprint:
        self.context.ensure_running()
        if not fingerprints:
            raise TransactionError("Không có dấu vân tay VP đã mua trong lượt này")
        if not self._find_empty_slot():
            raise NoEmptyStallSlot("Quầy clone không còn ô trống")
        self.waiter.sleep(0.25)
        self.inventory.select_storage(storage_id)

        seen: set[tuple[str, str]] = set()
        for fingerprint in fingerprints:
            key = (fingerprint.group_key, fingerprint.sha256)
            if key in seen:
                continue
            seen.add(key)
            match = self.inventory.best_fingerprint_match(fingerprint)
            score = float(match[1]) if match is not None else -1.0
            self.context.log(
                "CLEAR_STALL inventory candidate "
                f"sha={fingerprint.sha256[:12]} score={score:.3f} "
                f"threshold={self.EXACT_PURCHASE_MATCH_THRESHOLD:.3f}"
            )
            if match is None or score < self.EXACT_PURCHASE_MATCH_THRESHOLD:
                continue
            center, score = match
            self._finish_batch_from_match(center, score)
            return fingerprint

        self._cancel_dialog()
        raise TransactionError(
            "Không tìm thấy đúng VP đã xác minh mua trong lượt này; dừng trước khi treo"
        )

    def _cancel_dialog(self, *, cancelable: bool = True) -> None:
        for name in ("huy", "close_game", "close", "x_popup_event"):
            try:
                if self.vision.find(name, threshold=0.72, click=True) is not None:
                    if cancelable:
                        self.waiter.sleep(0.20)
                    else:
                        self.waiter.settle(0.20)
                    return
            except Exception:
                continue
        try:
            self.vision.driver.press("back")
        except Exception:
            pass


def _mean_difference(first, second) -> float:
    import cv2
    return float(cv2.absdiff(first, second).mean())
