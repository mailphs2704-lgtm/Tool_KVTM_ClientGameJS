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
    """Place a verified purchased VP stack using the recovered sale order."""

    # AUTO_PRO_REFERENCE: fixed logical 1000x1000 regions/click point.
    EMPTY_STALL_ZONE = (196, 340, 599, 395)
    DAT_BAN_ZONE = (662, 598, 231, 145)
    SL10_ZONE = (737, 426, 81, 81)
    CONFIRM_ZONE = (390, 552, 211, 102)
    PLACE_BUTTON = (771, 692)
    PLACE_BUTTON_ZONE = (700, 650, 180, 90)
    SALE_CHANGE_ZONE = (180, 330, 640, 430)

    # Native-500 live calibration. ``dat_ban`` was captured from the old logical
    # reference and can miss after VisionEngine scales it down. The orange button
    # geometry is stable in the supplied 500x500 sale screenshot, so it is a
    # second proof only inside the canonical button zone. The destructive click
    # remains guarded by post-click screen-change verification below.
    SALE_DIALOG_TEMPLATE_THRESHOLD = 0.68
    SALE_DIALOG_TEMPLATE_SCALES = (
        0.85, 1.00, 1.15, 1.30, 1.45, 1.60, 1.75,
    )
    SALE_BUTTON_ORANGE_MIN = 0.08

    # LIVE_CALIBRATED 20260903-195708: the last two verified x10 batches
    # matched at 0.612 and 0.605 after the own-stall view transition. 0.60 is
    # the smallest calibration that accepts both while retaining provenance.
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

    def _sale_change_crop(self):
        """Capture destructive-sale verification ROI at the actual frame size."""
        frame = self.vision.frame()
        x, y, width, height = self.vision.logical_zone_to_frame(
            self.SALE_CHANGE_ZONE, frame
        )
        return frame[y : y + height, x : x + width].copy()

    def _sale_button_orange_ratio(self, frame=None) -> float:
        """Measure the live orange Đặt bán button only in its canonical zone."""
        import numpy as np

        source = self.vision.frame() if frame is None else frame
        x, y, width, height = self.vision.logical_zone_to_frame(
            self.PLACE_BUTTON_ZONE, source
        )
        roi = source[y : y + height, x : x + width]
        if roi is None or getattr(roi, "size", 0) == 0 or roi.ndim < 3:
            return 0.0

        # Vision frames are OpenCV BGR/BGRA. These loose channel relationships
        # intentionally follow the orange/gold button rather than exact RGB, so
        # native scaling/antialiasing does not break the proof.
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
        """Prove the sale dialog by template OR live native-500 button geometry."""
        source = self.vision.frame() if frame is None else frame
        marker = self.vision.find(
            "dat_ban",
            threshold=self.SALE_DIALOG_TEMPLATE_THRESHOLD,
            zone=self.DAT_BAN_ZONE,
            scales=self.SALE_DIALOG_TEMPLATE_SCALES,
            click=False,
            frame=source,
        )
        if marker is not None:
            self.context.detail(
                "AUTO sale dialog proof | source=dat_ban-template | "
                f"score={marker.score:.3f} | center={marker.center}"
            )
            return True

        orange_ratio = self._sale_button_orange_ratio(source)
        if orange_ratio >= self.SALE_BUTTON_ORANGE_MIN:
            self.context.detail(
                "AUTO sale dialog proof | source=native-500-orange-button | "
                f"orange_ratio={orange_ratio:.3f} | "
                f"min={self.SALE_BUTTON_ORANGE_MIN:.3f}"
            )
            return True
        return False

    def wait_sale_dialog_ready(self, *, timeout: float = 4.0, description: str = "màn hình đặt bán") -> None:
        """Wait for a safe sale-dialog proof without making the button template mandatory."""
        self.waiter.until(
            lambda: self.is_sale_dialog_ready(),
            timeout=float(timeout),
            interval=0.20,
            description=description,
        )

    def open_inventory_read_only(self, *, storage_id: int = 2) -> None:
        """Open the sale inventory without selecting or listing any VP."""
        self.context.ensure_running()
        if not self._find_empty_slot():
            raise NoEmptyStallSlot("Quầy clone không còn ô trống để mở kho")
        self.waiter.sleep(0.25)
        self.inventory.select_storage(storage_id)
        self.context.log("Đã mở kho bán ở chế độ READ-ONLY")

    def close_inventory_read_only(self, timeout: float = 6.0) -> None:
        """Close the item-picker X and verify the READ-ONLY inventory vanished."""
        deadline = time.monotonic() + float(timeout)
        attempts = 0
        while time.monotonic() < deadline:
            self.context.ensure_running()
            if self.vision.find(
                "kho_thanh_pham",
                threshold=0.72,
                zone=self.inventory.STORAGE_ZONE,
            ) is None:
                self.context.log("Đã đóng kho kiểm tra READ-ONLY")
                return

            attempts += 1
            close_match = self.vision.find_any(
                ("close_game", "close", "x_popup_event"),
                threshold=0.72,
                zone=(930, 0, 70, 70),
                click=True,
            )
            if close_match is None:
                # Logical 1000x1000 item-picker X shown at the top-right.
                self.vision.driver.click(968, 28)
            self.waiter.sleep(0.35)

        raise ScreenTimeout(
            f"Không đóng được kho READ-ONLY bằng nút X sau {attempts} lần"
        )

    def _find_empty_slot(self) -> bool:
        for name in ("quaytrong", "quay_trong"):
            if self.vision.find(
                name,
                threshold=0.66,
                zone=self.EMPTY_STALL_ZONE,
                scales=(0.85, 0.92, 1.0, 1.08, 1.15),
                click=True,
            ) is not None:
                return True
        return False

    def _finish_batch_from_match(
        self,
        center: tuple[int, int],
        score: float,
    ) -> None:
        """Finish the sale after one exact purchased inventory match is selected."""
        self.vision.driver.click(*center)
        self.waiter.sleep(0.30)

        try:
            self.wait_sale_dialog_ready(timeout=4.0, description="màn hình đặt bán")
        except ScreenTimeout as exc:
            self._cancel_dialog()
            raise TransactionError("VP không mở được màn hình đặt bán") from exc

        # Do not require the fragile "sl10" marker. The selected inventory
        # item is already constrained by a fingerprint from a verified purchase
        # in this run. Keep the game's current stack quantity and original price;
        # screen change below remains the destructive-action verification gate.
        quantity_marker = self.vision.find(
            "sl10", threshold=0.62, zone=self.SL10_ZONE
        )
        self.context.log(
            "CLEAR_STALL resale quantity marker "
            + ("x10-found" if quantity_marker is not None else "not-required")
        )

        before = self._sale_change_crop()
        self.vision.driver.click(*self.PLACE_BUTTON)

        # The destructive click has already been sent. Keep accounting atomic
        # until the screen-change verification finishes.
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
        """Sell one x10 batch chosen only from this run's verified purchases.

        The empty stall slot is opened before scanning the inventory. This is
        important: the inventory item grid does not exist on the own-stall
        screen, so a pre-scan there can never reliably identify the item.
        """
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
            # The template is a normalized item core with stall background and
            # quantity text removed. Only fingerprints proven by a successful
            # purchase in this run enter this loop; screen change is verified
            # again after placement before the token is consumed.
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