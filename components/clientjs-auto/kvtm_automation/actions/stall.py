from __future__ import annotations

import os
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

# Recovered AUTO PRO crop geometry in logical 1000x1000 coordinates.
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
# Live Gate v8 evidence across four runs:
# empty wood slot stddev = 13.69; lowest occupied crop = 28.53.
# Keep a wide separation so empty stall wood is never treated as an item.
EMPTY_THRESHOLD = 20.0

# Shared/Multi default stays unchanged. Standalone can opt into one 0.20 s
# swipe per scan through KVTM_CLEAR_STALL_SINGLE_SWIPE without changing Multi.
STALL_SWIPE_DURATION = 0.35
STALL_RENDER_SETTLE = 0.55


class StallActions:
    """Friend/own stall entry, 20-slot scan and shop scrolling."""

    FRIEND_STALL_OPEN_POINT = (656, 824)
    FRIEND_STALL_ZONE = (632, 230, 247, 230)
    OWN_STALL_ACTIVE_ZONE = (319, 249, 386, 120)
    OWN_STALL_ENTRY_POINT = (636, 857)
    OWN_STALL_CONTENT_ZONE = (196, 340, 599, 395)

    def __init__(
        self,
        context: AutomationContext,
        vision: VisionEngine,
        waiter: Waiter,
    ) -> None:
        self.context = context
        self.vision = vision
        self.waiter = waiter
        self.swipe_pulses = 2
        self.swipe_duration = STALL_SWIPE_DURATION
        self.swipe_settle = STALL_RENDER_SETTLE
        self.swipe_start = (633, 546)
        self.swipe_end = (540, 540)

    def apply_runtime_policy(self, policy) -> None:
        self.swipe_pulses = int(policy.swipe_pulses)
        self.swipe_duration = float(policy.swipe_duration)
        self.swipe_settle = float(policy.swipe_settle)
        self.swipe_start = (int(policy.swipe_start_x), int(policy.swipe_start_y))
        self.swipe_end = (int(policy.swipe_end_x), int(policy.swipe_end_y))
        if os.environ.get("KVTM_CLEAR_STALL_SINGLE_SWIPE") == "1":
            self.swipe_pulses = 1
            self.swipe_duration = 0.20
            self.context.log(
                "Dọn quầy standalone • 1 swipe/scan • duration=0.20s • "
                "mua theo tâm ảnh scan"
            )

    @staticmethod
    def physical_slot(view: int, local_slot: int) -> int:
        if not 1 <= int(view) <= STALL_VIEW_COUNT:
            raise ValueError(f"Cửa sổ quầy không hợp lệ: {view}")
        if not 1 <= int(local_slot) <= len(VISIBLE_SLOT_CENTERS):
            raise ValueError(f"Ô quầy không hợp lệ: {local_slot}")
        return (int(view) - 1) * STALL_SHIFT + int(local_slot)

    @staticmethod
    def visible_local_slots(view: int) -> tuple[int, ...]:
        """Every rendered view has two rows; both must be purchase-scanned."""
        if not 1 <= int(view) <= STALL_VIEW_COUNT:
            raise ValueError(f"Cửa sổ quầy không hợp lệ: {view}")
        return tuple(range(1, 9))

    @staticmethod
    def new_local_slots(view: int) -> tuple[int, ...]:
        # Diagnostic overlap only. Production purchase must use a remaining
        # counter and verified disappearance, never infer account capacity
        # from this fixed sample map.
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

    def close_friend_stall(self, timeout: float = 12.0) -> None:
        """Close the current friend stall before a refresh or house change."""
        deadline = time.monotonic() + float(timeout)
        while time.monotonic() < deadline:
            self.context.ensure_running()
            if self.vision.find(
                "quay_hang_friend",
                threshold=0.78,
                zone=self.FRIEND_STALL_ZONE,
            ) is None:
                self.context.log("Đã thoát quầy nhà bạn")
                return
            self.vision.driver.click(965, 198)
            self.waiter.sleep(0.55)
        raise ScreenTimeout("Không thoát được quầy nhà bạn để tải lượt kế tiếp")

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
                self.vision.driver.click(965, 198)
                attempts = 0
            self.waiter.sleep(0.55)
        raise ScreenTimeout("Không vào được quầy bán của clone")

    def close_own_stall(self, timeout: float = 12.0) -> None:
        """Close the clone stall and verify the panel is no longer active."""
        deadline = time.monotonic() + float(timeout)
        while time.monotonic() < deadline:
            self.context.ensure_running()
            if self.vision.find(
                "quay_hang_on",
                threshold=0.80,
                zone=self.OWN_STALL_ACTIVE_ZONE,
            ) is None:
                self.context.log("Đã đóng quầy bán của clone")
                return
            self.vision.driver.click(965, 198)
            self.waiter.sleep(0.50)
        raise ScreenTimeout("Không đóng được quầy bán của clone")

    def collect_own_stall_gold(self, *, maximum: int = 8) -> int:
        """Collect optional gold per slot; unresolved gold blocks view advance."""
        visible_limit = min(len(VISIBLE_SLOT_CENTERS), max(0, int(maximum)))
        collected = 0
        for local_slot in range(1, visible_limit + 1):
            self.context.ensure_running()
            frame = self.vision.frame()
            cx, cy = VISIBLE_SLOT_CENTERS[local_slot - 1]
            slot_zone = (cx - 58, cy - 70, 116, 100)
            match = self.vision.find(
                "vang",
                threshold=0.82,
                zone=slot_zone,
                click=False,
                frame=frame,
            )
            if match is None:
                continue

            self.vision.driver.click(*match.center)
            first_deadline = time.monotonic() + 1.2
            disappeared = False
            while time.monotonic() < first_deadline:
                self.context.ensure_running()
                self.waiter.sleep(0.20)
                if self.vision.find(
                    "vang",
                    threshold=0.82,
                    zone=slot_zone,
                    click=False,
                ) is None:
                    disappeared = True
                    break

            if not disappeared:
                self.vision.driver.click(cx, cy)
                verify_deadline = time.monotonic() + 2.0
                while time.monotonic() < verify_deadline:
                    self.context.ensure_running()
                    self.waiter.sleep(0.20)
                    if self.vision.find(
                        "vang",
                        threshold=0.82,
                        zone=slot_zone,
                        click=False,
                    ) is None:
                        disappeared = True
                        break

            if not disappeared:
                raise ScreenTimeout(
                    "Có vàng nhưng không thu được; giữ nguyên view, không swipe • "
                    f"ô hiển thị {local_slot} score={match.score:.3f}"
                )

            collected += 1
            self.context.log(
                "Thu vàng quầy clone • "
                f"ô hiển thị {local_slot} đã xác minh"
            )

        self.context.log(
            f"Thu vàng quầy clone hoàn tất • {collected} ô đã xác minh"
        )
        return collected

    def next_view(self) -> None:
        """Move one logical view using the configured swipe pulse count."""
        for swipe_index in range(1, self.swipe_pulses + 1):
            self.context.ensure_running()
            self.vision.driver.swipe(
                *self.swipe_start, *self.swipe_end, duration=self.swipe_duration
            )
            self.context.log(
                f"Kéo quầy • swipe {swipe_index}/{self.swipe_pulses} • "
                f"duration={self.swipe_duration:.2f}s"
            )
        self.waiter.sleep(self.swipe_settle)

    def previous_view(self) -> None:
        """Return one logical view using the configured swipe pulse count."""
        for swipe_index in range(1, self.swipe_pulses + 1):
            self.context.ensure_running()
            self.vision.driver.swipe(
                *self.swipe_end, *self.swipe_start, duration=self.swipe_duration
            )
            self.context.log(
                f"Kéo quầy về • swipe {swipe_index}/{self.swipe_pulses} • "
                f"duration={self.swipe_duration:.2f}s"
            )
        self.waiter.sleep(self.swipe_settle)

    def rewind_to_first(self, current_view: int) -> None:
        for _ in range(max(0, int(current_view) - 1)):
            self.previous_view()

    def listing_is_available(self, frame: Any, local_slot: int) -> bool:
        """Reject sold cells before purchase planning at any client resolution."""
        slot = int(local_slot)
        if not 1 <= slot <= len(VISIBLE_SLOT_CENTERS):
            return False
        cx, _cy = VISIBLE_SLOT_CENTERS[slot - 1]
        top, bottom = ((495, 530) if slot <= 4 else (685, 720))
        logical_zone = (cx + 10, top, 38, bottom - top)
        x, y, width, height = self.vision.logical_zone_to_frame(
            logical_zone, frame
        )
        roi = frame[y : y + height, x : x + width]
        if roi is None or getattr(roi, "size", 0) == 0:
            return False
        blue = roi[:, :, 0]
        green = roi[:, :, 1]
        red = roi[:, :, 2]
        coin_pixels = (
            (red > 160)
            & (green > 80)
            & (green < 220)
            & (blue < 80)
            & (red.astype("float32") > green.astype("float32") * 1.10)
        )
        frame_sx, frame_sy = self.vision.frame_scales(frame)
        minimum_coin_pixels = max(
            8,
            int(round(120.0 * frame_sx * frame_sy)),
        )
        return int(coin_pixels.sum()) >= minimum_coin_pixels

    def scan_view(
        self,
        view: int,
        template_dir: Path,
        *,
        frame: Any | None = None,
    ) -> tuple[StallSlotObservation, ...]:
        """Capture visible physical positions using logical 1000 slot geometry."""
        import cv2

        self.context.ensure_running()
        source = self.vision.frame() if frame is None else frame
        height, width = source.shape[:2]
        frame_sx, frame_sy = self.vision.frame_scales(source)
        if frame_sx < 0.40 or frame_sy < 0.40:
            raise RuntimeError(
                f"Khung ClientJS quá nhỏ cho quầy: {width}x{height} "
                f"scale=({frame_sx:.3f},{frame_sy:.3f})"
            )
        template_dir = Path(template_dir)
        template_dir.mkdir(parents=True, exist_ok=True)
        observations: list[StallSlotObservation] = []
        for local_slot in self.visible_local_slots(view):
            if not self.listing_is_available(source, local_slot):
                continue
            icon = self.crop_icon(source, local_slot)
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

    def scan_all_20(
        self,
        template_dir: Path,
        *,
        capture_dir: Path | None = None,
    ) -> tuple[StallSlotObservation, ...]:
        import cv2

        capture_root = Path(capture_dir) if capture_dir is not None else None
        if capture_root is not None:
            capture_root.mkdir(parents=True, exist_ok=True)
        found: list[StallSlotObservation] = []
        for view in range(1, STALL_VIEW_COUNT + 1):
            self.context.ensure_running()
            self.context.stage(f"scan-stall-view-{view}")
            frame = self.vision.frame()
            if capture_root is not None:
                target = capture_root / f"view-{view:02d}.png"
                if not cv2.imwrite(str(target), frame):
                    raise RuntimeError(f"Không lưu được ảnh chẩn đoán: {target}")
            current = self.scan_view(view, template_dir, frame=frame)
            found.extend(current)
            covered = min(TOTAL_STALL_SLOTS, 8 + (view - 1) * STALL_SHIFT)
            self.context.log(
                f"Quầy view {view}/4: {len(current)} ô mới có VP • phủ {covered}/20 ô"
            )
            if view < STALL_VIEW_COUNT:
                self.next_view()
        return tuple(found)

    def crop_icon(self, frame: Any, local_slot: int):
        """Crop one logical slot icon from the actual rendered frame."""
        cx, cy = VISIBLE_SLOT_CENTERS[int(local_slot) - 1]
        logical_zone = (
            cx - ICON_HALF_WIDTH,
            cy - ICON_HALF_HEIGHT,
            ICON_HALF_WIDTH * 2,
            ICON_HALF_HEIGHT * 2,
        )
        x, y, width, height = self.vision.logical_zone_to_frame(
            logical_zone, frame
        )
        return frame[y : y + height, x : x + width].copy()


def _occupancy_score(image: Any) -> float:
    import cv2

    if image is None or getattr(image, "size", 0) == 0:
        return 0.0
    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGRA2GRAY if len(image.shape) == 3 and image.shape[2] == 4 else cv2.COLOR_BGR2GRAY,
    )
    return float(gray.std())
