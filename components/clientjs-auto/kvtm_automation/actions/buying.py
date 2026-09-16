from __future__ import annotations

from collections.abc import Callable
import os

from ..context import AutomationContext
from ..errors import InventoryFull, TransactionError
from ..models import StallSlotObservation, VisualFingerprint, hamming_distance
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter
from .stall import StallActions


class BuyingActions:
    """Direct friend-stall purchase loop reconstructed from GoFiendHome."""

    STORAGE_FULL_ZONE = (669, 351, 91, 88)

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

    def _captured_scan_center(
        self,
        observation: StallSlotObservation,
    ) -> tuple[tuple[int, int], float, str] | None:
        """Return Match.center captured by the standalone VP recognition scan."""
        cx, cy = observation.center
        key = (int(cx) - 50, int(cy) - 58, 100, 108)
        centers = getattr(
            self.vision,
            "_kvtm_clear_stall_vp_match_centers",
            None,
        )
        if not isinstance(centers, dict):
            return None
        payload = centers.get(key)
        if not isinstance(payload, dict):
            return None
        center = payload.get("center")
        if not isinstance(center, (tuple, list)) or len(center) != 2:
            return None
        try:
            point = (int(center[0]), int(center[1]))
            score = float(payload.get("score", 0.0))
            name = str(payload.get("name") or "")
        except (TypeError, ValueError):
            return None
        return point, score, name

    def buy_from_listing(
        self,
        observation: StallSlotObservation,
        *,
        maximum: int,
        on_unit: Callable[[int], None] | None = None,
        skip_unbuyable: bool = False,
    ) -> int:
        """Buy and verify one scanned listing at a time."""
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
                captured = self._captured_scan_center(observation)
                if captured is None:
                    if skip_unbuyable:
                        self.context.log(
                            "Bỏ qua VP ô vật lý "
                            f"{observation.physical_slot}: thiếu tâm ảnh PASS từ scan; "
                            "không click tọa độ cố định"
                        )
                        return bought
                    raise TransactionError(
                        "Thiếu tâm ảnh VP PASS từ scan; không dùng tọa độ mua cố định"
                    )
                click_center, scan_score, scan_name = captured
                self.context.log(
                    "Mua VP theo tâm ảnh scan • "
                    f"ô vật lý {observation.physical_slot} • "
                    f"template={scan_name} • center={click_center} • "
                    f"score={scan_score:.3f}"
                )
            else:
                # Multi DEV keeps its established click contract. Standalone is
                # the only mode that opts into exact scan-center buying.
                click_center = observation.click_center

            self.vision.driver.click(*click_center)
            self.waiter.settle(0.50)
            if self.vision.find(
                "x",
                threshold=0.82,
                zone=self.STORAGE_FULL_ZONE,
            ) is not None:
                raise InventoryFull("Kho clone đã đầy trong lúc mua VP")

            # Never account a click as a purchase by timing alone. The source
            # listing must disappear/change first; otherwise stop before the
            # manifest counter is incremented.
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