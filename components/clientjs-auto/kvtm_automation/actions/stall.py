from __future__ import annotations

from pathlib import Path
import time
from typing import Any

from ..context import AutomationContext
from ..errors import NavigationError, ScreenTimeout
from ..models import StallSlotObservation, VisualFingerprint
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter


TOTAL_STALL_SLOTS = 20
STALL_VIEW_COUNT = 4
STALL_SHIFT = 4

# Recovered AUTO PRO crop geometry at the fixed 1000x1000 ClientJS size.
VISIBLE_SLOT_CENTERS = (
    (300, 456), (432, 456), (565, 456), (698, 456),
    (300, 647), (432, 647), (565, 647), (698, 647),
)
FRIEND_PURCHASE_CLICK_CENTERS = (
    (290, 435), (423, 432), (554, 435), (690, 435),
    (288, 628), (431, 632), (555, 622), (683, 625),
)
ICON_HALF_WIDTH = 42
ICON_HALF_HEIGHT = 42
CELL_HALF_WIDTH = 52
CELL_HALF_HEIGHT = 67
EMPTY_THRESHOLD = 9.0


class StallActions:
    """Friend/own stall entry, 20-slot scan and shop scrolling."""

    FRIEND_STALL_OPEN_POINT = (656, 824)
    FRIEND_STALL_ZONE = (632, 230, 247, 230)
    OWN_STALL_ACTIVE_ZONE = (319, 249, 386, 120)
    OWN_STALL_ENTRY_POINT = (636, 857)

    def __init__(
        self,
        context: AutomationContext,
        vision: VisionEngine,
        waiter: Waiter,
    ) -> None:
        self.context = context
        self.vision = vision
        self.waiter = waiter

    @staticmethod
    def physical_slot(view: int, local_slot: int) -> int:
        if not 1 <= int(view) <= STALL_VIEW_COUNT:
            raise ValueError(f"Cửa sổ quầy không hợp lệ: {view}")
        if not 1 <= int(local_slot) <= len(VISIBLE_SLOT_CENTERS):
            raise ValueError(f"Ô quầy không hợp lệ: {local_slot}")
        return (int(view) - 1) * STALL_SHIFT + int(local_slot)

    @staticmethod
    def new_local_slots(view: int) -> tuple[int, ...]:
        if int(view) == 1:
            return tuple(range(1, 9))
        if 2 <= int(view) <= STALL_VIEW_COUNT:
            return (5, 6, 7, 8)
        raise ValueError(f"Cửa sổ quầy không hợp lệ: {view}")

    def open_friend_stall(self, timeout: float = 20.0) -> None:
        """Open the single 20-slot stall at the currently visited friend's home.

        GoFiendHome uses this exact entry point and then verifies
        quay_hang_friend in the recovered fixed region. There is no recovered
        evidence of four separate friend stalls; the historical `SellBy` value
        selects an inventory category when reselling at the clone's own stall.
        """
        deadline = time.monotonic() + float(timeout)
        attempt = 0
        while time.monotonic() < deadline and attempt < 5:
            self.context.ensure_running()
            if self.vision.find(
                "quay_hang_friend",
                threshold=0.78,
                zone=self.FRIEND_STALL_ZONE,
            ) is not None:
                self.context.log("Đã mở quầy 20 ô của nhà bạn")
                return
            attempt += 1
            self.vision.driver.click(*self.FRIEND_STALL_OPEN_POINT)
            self.context.log(f"Mở quầy nhà bạn • lần {attempt}/5")
            self.waiter.sleep(0.55)
        raise NavigationError("Không mở được quầy nhà bạn")

    def open_own_stall(self, timeout: float = 25.0) -> None:
        """Enter the clone's own sales stall using recovered makeBuyItems flow."""
        if self.vision.find(
            "quay_hang_on",
            threshold=0.80,
            zone=self.OWN_STALL_ACTIVE_ZONE,
        ) is not None:
            return
        deadline = time.monotonic() + float(timeout)
        attempts = 0
        while time.monotonic() < deadline:
            self.context.ensure_running()
            if self.vision.find(
                "quay_hang_on",
                threshold=0.80,
                zone=self.OWN_STALL_ACTIVE_ZONE,
            ) is not None:
                self.context.log("Đã vào quầy bán của clone")
                return
            if self.vision.find("quay_hang", threshold=0.74) is not None:
                # AUTO PRO deliberately taps this entry point several times to
                # make the shop panel settle before looking for quay_hang_on.
                for _ in range(3):
                    self.context.ensure_running()
                    self.vision.driver.click(*self.OWN_STALL_ENTRY_POINT)
                    self.waiter.sleep(0.45)
                    if self.vision.find(
                        "quay_hang_on",
                        threshold=0.80,
                        zone=self.OWN_STALL_ACTIVE_ZONE,
                    ) is not None:
                        self.context.log("Đã vào quầy bán của clone")
                        return
            attempts += 1
            if attempts >= 3:
                # Recovered recovery tap closes a stale modal before retrying.
                self.vision.driver.click(965, 198)
                attempts = 0
            self.waiter.sleep(0.55)
        raise ScreenTimeout("Không vào được quầy bán của clone")

    def next_view(self) -> None:
        """Recovered `_rollbackItem`: two short drags move four physical slots."""
        for _ in range(2):
            self.context.ensure_running()
            self.vision.driver.swipe(633, 546, 540, 540, duration=0.08)
            self.waiter.sleep(0.50)

    def previous_view(self) -> None:
        """Recovered `_scroll_back_shop`: reverse one 4-slot shop view."""
        for _ in range(2):
            self.context.ensure_running()
            self.vision.driver.swipe(540, 540, 633, 546, duration=0.08)
            self.waiter.sleep(0.50)

    def rewind_to_first(self, current_view: int) -> None:
        for _ in range(max(0, int(current_view) - 1)):
            self.previous_view()

    def scan_view(self, view: int, template_dir: Path) -> tuple[StallSlotObservation, ...]:
        """Capture only the newly exposed physical positions for one shop view."""
        import cv2

        self.context.ensure_running()
        frame = self.vision.frame()
        height, width = frame.shape[:2]
        if width < 800 or height < 750:
            raise RuntimeError(f"Khung ClientJS không hợp lệ: {width}x{height}")
        template_dir = Path(template_dir)
        template_dir.mkdir(parents=True, exist_ok=True)
        observations: list[StallSlotObservation] = []
        for local_slot in self.new_local_slots(view):
            cx, cy = VISIBLE_SLOT_CENTERS[local_slot - 1]
            icon = frame[
                cy - ICON_HALF_HEIGHT : cy + ICON_HALF_HEIGHT,
                cx - ICON_HALF_WIDTH : cx + ICON_HALF_WIDTH,
            ].copy()
            score = _occupancy_score(icon)
            if score < EMPTY_THRESHOLD:
                continue
            physical = self.physical_slot(view, local_slot)
            template_file = template_dir / f"slot-{physical:02d}.png"
            if not cv2.imwrite(str(template_file), icon):
                raise RuntimeError(f"Không lưu được template VP: {template_file}")
            observations.append(
                StallSlotObservation(
                    view=int(view),
                    local_slot=int(local_slot),
                    physical_slot=physical,
                    center=VISIBLE_SLOT_CENTERS[local_slot - 1],
                    click_center=FRIEND_PURCHASE_CLICK_CENTERS[local_slot - 1],
                    fingerprint=VisualFingerprint.from_image(icon, str(template_file)),
                    occupancy_score=score,
                )
            )
        return tuple(observations)

    def scan_all_20(self, template_dir: Path) -> tuple[StallSlotObservation, ...]:
        found: list[StallSlotObservation] = []
        for view in range(1, STALL_VIEW_COUNT + 1):
            self.context.ensure_running()
            self.context.stage(f"scan-stall-view-{view}")
            current = self.scan_view(view, template_dir)
            found.extend(current)
            self.context.log(
                f"Quầy view {view}/4: {len(current)} ô mới có VP"
            )
            if view < STALL_VIEW_COUNT:
                self.next_view()
        return tuple(found)

    @staticmethod
    def crop_icon(frame: Any, local_slot: int):
        cx, cy = VISIBLE_SLOT_CENTERS[int(local_slot) - 1]
        return frame[
            cy - ICON_HALF_HEIGHT : cy + ICON_HALF_HEIGHT,
            cx - ICON_HALF_WIDTH : cx + ICON_HALF_WIDTH,
        ].copy()


def _occupancy_score(image: Any) -> float:
    import cv2

    if image is None or getattr(image, "size", 0) == 0:
        return 0.0
    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGRA2GRAY if len(image.shape) == 3 and image.shape[2] == 4 else cv2.COLOR_BGR2GRAY,
    )
    return float(gray.std())
