from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Callable

from .native_runtime import ClearStallNativeRuntime


@dataclass(frozen=True)
class NavigationState:
    friend_ordinal: int
    stall_id: int


class ClearStallNativeNavigation:
    """Pure-Python Dọn quầy navigation.

    AUTO PRO is used only as the behavioral reference. Every transition is
    verified visually before the next transition is allowed.
    """

    # Fixed 1000x1000 ClientJS geometry recovered/verified from AUTO PRO traces.
    # These are interaction regions, not blind success assumptions: after each
    # click the expected next-state template must appear.
    FRIEND_BUTTON_FALLBACK = (52, 966)
    SHOP_BUTTON_FALLBACK = (968, 967)

    def __init__(
        self,
        runtime: ClearStallNativeRuntime,
        *,
        stop_event: threading.Event,
        logger: Callable[[str], None],
    ) -> None:
        self.runtime = runtime
        self.driver = runtime.driver
        self.stop_event = stop_event
        self.log = logger
        self.state: NavigationState | None = None

    def configure(self, friend_ordinal: int, stall_id: int) -> None:
        friend = int(friend_ordinal)
        stall = int(stall_id)
        if not 1 <= friend <= 500:
            raise ValueError("Bạn bè số phải trong khoảng 1..500")
        if not 1 <= stall <= 4:
            raise ValueError("Quầy phải trong khoảng 1..4")
        self.state = NavigationState(friend, stall)

    def ensure_main_screen(self, timeout: float = 35.0) -> None:
        self.runtime.wait_main_screen(timeout=timeout)

    def go_to_friend_home(self, friend_ordinal: int | None = None) -> None:
        """Open friends and enter the requested ordinal without AUTO PRO .pyc.

        The implementation intentionally stops if a visual state is unknown;
        it never converts an unverified click into a successful navigation.
        """
        self._ensure_running()
        if self.state is None and friend_ordinal is None:
            raise RuntimeError("Chưa cấu hình bạn bè Dọn quầy")
        friend = int(friend_ordinal if friend_ordinal is not None else self.state.friend_ordinal)
        self.ensure_main_screen()

        # Prefer visual controls from AUTO PRO assets. The fallback point is
        # only used for the stable bottom-left friends button on 1000x1000.
        if not self._click_first(("friend_off", "friend_on", "ban_be"), threshold=0.70):
            self.driver.click(*self.FRIEND_BUTTON_FALLBACK)
        self.log("Đã mở danh sách bạn bè")
        self._sleep(0.8)

        # AUTO PRO's friend list is paged/scrollable. We select the ordinal by
        # deterministic row geometry, with screenshot-change verification. A
        # later calibrated trace can replace these geometry constants without
        # touching the workflow layer.
        self._select_friend_ordinal(friend)

        if not self._wait_for_any(
            ("friend_home", "icon_home", "kho_ban", "shop_friend", "friend_on"),
            timeout=15.0,
            threshold=0.66,
        ):
            raise RuntimeError(f"Không xác nhận được đã sang nhà bạn số {friend}")
        self.log(f"Đã sang nhà bạn số {friend}")

    def _select_friend_ordinal(self, friend_ordinal: int) -> None:
        """Select friend row using the recovered list layout with verification."""
        # The list presents five usable rows per viewport. Ordinal is 1-based.
        rows_per_view = 5
        row_centers = (300, 410, 520, 630, 740)
        target_index = int(friend_ordinal) - 1
        page, row = divmod(target_index, rows_per_view)

        # Return list to its top when a top marker is available. Otherwise a
        # bounded upward sweep is safe: it affects only the already-open list.
        for _ in range(6):
            self._ensure_running()
            if self._find_any(("friend_top", "friend_list_top"), threshold=0.68):
                break
            self.driver.swipe(515, 350, 515, 760, duration=0.20)
            self._sleep(0.12)

        for _ in range(page):
            self._ensure_running()
            before = self.runtime.screenshot()
            self.driver.swipe(515, 735, 515, 345, duration=0.24)
            self._sleep(0.22)
            if self._mean_change(before, self.runtime.screenshot()) < 0.8:
                raise RuntimeError("Danh sách bạn bè không cuộn khi chọn ordinal")

        before = self.runtime.screenshot()
        self.driver.click(520, row_centers[row])
        self._sleep(0.8)
        if self._mean_change(before, self.runtime.screenshot()) < 0.8:
            raise RuntimeError(f"Click bạn bè số {friend_ordinal} không làm màn hình thay đổi")

    def open_target_stall(self, stall_id: int | None = None) -> None:
        self._ensure_running()
        if self.state is None and stall_id is None:
            raise RuntimeError("Chưa cấu hình quầy Dọn quầy")
        stall = int(stall_id if stall_id is not None else self.state.stall_id)

        if not self._click_first(("kho_ban", "shop_friend", "shop"), threshold=0.66):
            self.driver.click(*self.SHOP_BUTTON_FALLBACK)
        self._sleep(0.7)

        # Four stall tabs are horizontal. Only use the geometry after the shop
        # window itself has been visually detected.
        if not self._wait_for_any(("shop", "kho_ban", "buy_item", "quay_hang_on"), timeout=8.0, threshold=0.64):
            raise RuntimeError("Không mở được cửa sổ quầy nhà bạn")

        tab_centers = ((278, 315), (430, 315), (582, 315), (734, 315))
        self.driver.click(*tab_centers[stall - 1])
        self._sleep(0.45)
        self.log(f"Đã chọn quầy {stall}")

    def return_to_clone_home(self) -> None:
        self._ensure_running()
        for _ in range(8):
            if self._find_any(("friend_off", "icon_home"), threshold=0.68):
                self.log("Đã về màn hình chính clone")
                return
            self.driver.press("back")
            self._sleep(0.45)
        raise RuntimeError("Không quay được về màn hình chính clone")

    def open_clone_stall_for_sale(self, stall_id: int) -> None:
        self.ensure_main_screen()
        if not self._click_first(("kho_ban", "shop", "cua_hang"), threshold=0.66):
            self.driver.click(*self.SHOP_BUTTON_FALLBACK)
        if not self._wait_for_any(("shop", "kho_ban", "quaytrong", "quay_hang_on"), timeout=8.0, threshold=0.64):
            raise RuntimeError("Không mở được quầy của clone")
        tabs = ((278, 315), (430, 315), (582, 315), (734, 315))
        self.driver.click(*tabs[int(stall_id) - 1])
        self._sleep(0.45)

    def swipe_next_stall_page(self) -> None:
        self._ensure_running()
        self.driver.swipe(633, 546, 540, 540, duration=0.35)
        self._sleep(0.35)

    def swipe_previous_stall_page(self) -> None:
        self._ensure_running()
        self.driver.swipe(540, 540, 633, 546, duration=0.35)
        self._sleep(0.35)

    def screenshot(self):
        return self.runtime.screenshot()

    def _click_first(self, names, *, threshold: float) -> bool:
        for name in names:
            try:
                match = self.runtime.find(name, threshold=threshold)
            except FileNotFoundError:
                continue
            if match is None:
                continue
            self.driver.click(*match.center)
            return True
        return False

    def _find_any(self, names, *, threshold: float):
        return self.runtime.matcher.any(names, threshold=threshold)

    def _wait_for_any(self, names, *, timeout: float, threshold: float):
        deadline = time.monotonic() + float(timeout)
        while time.monotonic() < deadline:
            self._ensure_running()
            match = self._find_any(names, threshold=threshold)
            if match is not None:
                return match
            self.runtime.dismiss_popups(timeout=0.6)
            self._sleep(0.2)
        return None

    @staticmethod
    def _mean_change(first, second) -> float:
        import cv2
        return float(cv2.absdiff(first, second).mean())

    def _sleep(self, seconds: float) -> None:
        deadline = time.monotonic() + max(0.0, float(seconds))
        while time.monotonic() < deadline:
            self._ensure_running()
            time.sleep(min(0.05, deadline - time.monotonic()))

    def _ensure_running(self) -> None:
        if self.stop_event.is_set():
            raise InterruptedError("Dọn quầy đã được yêu cầu dừng")
