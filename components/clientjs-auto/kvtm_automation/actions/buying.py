from __future__ import annotations

from collections.abc import Callable
import os
from pathlib import Path

from ..context import AutomationContext
from ..errors import InventoryFull, TransactionError
from ..models import StallSlotObservation, VisualFingerprint, hamming_distance
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter
from .stall import StallActions


class BuyingActions:
    """Direct friend-stall purchase loop reconstructed from GoFiendHome."""

    STORAGE_FULL_ZONE = (669, 351, 91, 88)
    FRIEND_STALL_CONTENT_ZONE = (196, 340, 599, 395)
    SCANNED_TEMPLATE_THRESHOLD = 0.58

    def __init__(
        self,
        context: AutomationContext,
        vision: VisionEngine,
        waiter: Waiter,
        stall: StallActions,
        *,
        fingerprint_distance: int = 6,
    ) -> None:
        self.context = context
        self.vision = vision
        self.waiter = waiter
        self.stall = stall
        self.fingerprint_distance = int(fingerprint_distance)

    def listing_matches(self, observation: StallSlotObservation) -> bool:
        frame = self.vision.frame()
        crop = self.stall.crop_icon(frame, observation.local_slot)
        if getattr(crop, "size", 0) == 0:
            return False
        current = VisualFingerprint.from_image(crop)
        return hamming_distance(
            current.perceptual_hash,
            observation.fingerprint.perceptual_hash,
        ) <= self.fingerprint_distance

    def _scanned_image_center(
        self,
        observation: StallSlotObservation,
    ) -> tuple[tuple[int, int], float] | None:
        """Relocate the exact VP image captured by scan and return its live center."""
        import cv2

        template_path = Path(str(observation.fingerprint.template_file or ""))
        if not template_path.is_file():
            return None
        template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
        if template is None or getattr(template, "size", 0) == 0:
            return None

        frame = self.vision.frame()
        source = frame
        if source.ndim == 3 and source.shape[2] == 4:
            source = cv2.cvtColor(source, cv2.COLOR_BGRA2BGR)
        x0, y0, width, height = self.vision.logical_zone_to_frame(
            self.FRIEND_STALL_CONTENT_ZONE,
            source,
        )
        roi = source[y0 : y0 + height, x0 : x0 + width]
        if roi.size == 0:
            return None

        frame_sx, frame_sy = self.vision.frame_scales(source)
        tw = max(2, int(round(template.shape[1] * frame_sx)))
        th = max(2, int(round(template.shape[0] * frame_sy)))
        if (tw, th) != (template.shape[1], template.shape[0]):
            template = cv2.resize(template, (tw, th), interpolation=cv2.INTER_AREA)
        if tw > roi.shape[1] or th > roi.shape[0]:
            return None

        result = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
        _minimum, maximum, _min_loc, max_loc = cv2.minMaxLoc(result)
        score = float(maximum)
        if score < self.SCANNED_TEMPLATE_THRESHOLD:
            return None

        frame_center = (
            x0 + int(max_loc[0]) + tw // 2,
            y0 + int(max_loc[1]) + th // 2,
        )
        logical_center = self.vision.frame_point_to_logical(frame_center, source)
        return logical_center, score

    def buy_from_listing(
        self,
        observation: StallSlotObservation,
        *,
        maximum: int,
        on_unit: Callable[[int], None] | None = None,
        skip_unbuyable: bool = False,
    ) -> int:
        """Click the same source listing until target is met or it disappears."""
        target = max(0, int(maximum))
        bought = 0
        image_center_mode = (
            os.environ.get("KVTM_CLEAR_STALL_IMAGE_CENTER_BUY") == "1"
            or os.environ.get("KVTM_CLEAR_STALL_SINGLE_SWIPE") == "1"
        )
        while bought < target:
            self.context.ensure_running()
            if not self.listing_matches(observation):
                break

            if image_center_mode:
                relocated = self._scanned_image_center(observation)
                if relocated is None:
                    if skip_unbuyable:
                        self.context.log(
                            "Bỏ qua VP ô vật lý "
                            f"{observation.physical_slot}: không định vị lại được tâm ảnh scan; "
                            "không click tọa độ cố định"
                        )
                        return bought
                    raise TransactionError(
                        "Không định vị lại được tâm ảnh VP đã scan; không dùng tọa độ mua cố định"
                    )
                click_center, scan_score = relocated
                self.context.log(
                    "Mua VP theo tâm ảnh scan • "
                    f"ô vật lý {observation.physical_slot} • "
                    f"center={click_center} • score={scan_score:.3f}"
                )
            else:
                click_center = observation.click_center
                scan_score = None

            self.vision.driver.click(*click_center)
            self.waiter.settle(0.50)
            if self.vision.find(
                "x",
                threshold=0.82,
                zone=self.STORAGE_FULL_ZONE,
            ) is not None:
                raise InventoryFull("Kho clone đã đầy trong lúc mua VP")

            changed = False
            for _ in range(10):
                if not self.listing_matches(observation):
                    changed = True
                    break
                self.waiter.settle(0.20)
            if not changed:
                if skip_unbuyable:
                    mode_text = "tâm ảnh" if image_center_mode else "ô vật lý"
                    self.context.log(
                        "Bỏ qua VP ô vật lý "
                        f"{observation.physical_slot}: click {mode_text} không đổi "
                        "(có thể chưa đủ level); không cộng 10 VP"
                    )
                    return bought
                raise TransactionError(
                    "Đã click VP nhưng ô quầy không đổi; không cộng 10 VP"
                )
            bought += 1
            if on_unit is not None:
                on_unit(bought)
            suffix = "click tâm ảnh đã xác nhận" if image_center_mode else "click đã xác nhận"
            self.context.log(
                f"Mua VP ô vật lý {observation.physical_slot}: "
                f"{bought}/{target} {suffix}"
            )
        return bought