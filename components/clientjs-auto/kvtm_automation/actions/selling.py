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
    """Place one exact batch of ten VP using the recovered sale order."""

    # AUTO_PRO_REFERENCE: fixed 1000x1000 regions/click point.
    EMPTY_STALL_ZONE = (196, 340, 599, 395)
    DAT_BAN_ZONE = (662, 598, 231, 145)
    SL10_ZONE = (737, 426, 81, 81)
    CONFIRM_ZONE = (390, 552, 211, 102)
    PLACE_BUTTON = (771, 692)

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

    def _find_empty_slot(self) -> bool:
        for name in ("quaytrong", "quay_trong"):
            if self.vision.find(
                name,
                threshold=0.72,
                zone=self.EMPTY_STALL_ZONE,
                click=True,
            ) is not None:
                return True
        return False

    def _finish_batch_from_match(
        self,
        center: tuple[int, int],
        score: float,
    ) -> None:
        """Finish the x10 sale after one exact inventory match is selected."""
        self.vision.driver.click(*center)
        self.waiter.sleep(0.30)

        try:
            self.waiter.until(
                lambda: self.vision.find(
                    "dat_ban",
                    threshold=0.78,
                    zone=self.DAT_BAN_ZONE,
                ),
                timeout=4.0,
                interval=0.20,
                description="màn hình đặt bán",
            )
        except ScreenTimeout as exc:
            self._cancel_dialog()
            raise TransactionError("VP không mở được màn hình đặt bán") from exc

        # LIVE_VERIFIED/AUTO_PRO_REFERENCE: x10 is the only quantity Gate 4 may
        # place. The existing price controls are intentionally never touched.
        sl10 = None
        deadline = time.monotonic() + 2.5
        while time.monotonic() < deadline:
            self.context.ensure_running()
            sl10 = self.vision.find("sl10", threshold=0.62, zone=self.SL10_ZONE)
            if sl10 is not None:
                break
            self.waiter.sleep(0.20)
        if sl10 is None:
            self._cancel_dialog()
            raise InsufficientBatch("Loại VP hiện không đủ 10 để treo bán")

        before = self.vision.frame()[330:760, 180:820].copy()
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
            after = self.vision.frame()[330:760, 180:820].copy()
            best_change = max(best_change, _mean_difference(before, after))
            if best_change >= self.minimum_screen_change:
                self.context.log(
                    "Đã treo 10 VP "
                    f"(inventory-match={score:.3f}, change={best_change:.2f})"
                )
                return
            self.waiter.settle(0.20)
        self._cancel_dialog(cancelable=False)
        raise TransactionError("Không xác nhận được thay đổi sau khi treo 10 VP")

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
            key = (fingerprint.group, fingerprint.sha256)
            if key in seen:
                continue
            seen.add(key)
            match = self.inventory.find_fingerprint(fingerprint, threshold=0.68)
            if match is None:
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
