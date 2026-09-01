from __future__ import annotations

from collections.abc import Callable

from ..context import AutomationContext
from ..errors import InventoryFull
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

    def buy_from_listing(
        self,
        observation: StallSlotObservation,
        *,
        maximum: int,
        on_unit: Callable[[int], None] | None = None,
    ) -> int:
        """Click the same source listing until target is met or it disappears.

        `on_unit` is called immediately after every verified click so the
        workflow can atomically persist manifest/carryover state. A stop request
        received after the click is honored only after that unit is accounted.
        """
        target = max(0, int(maximum))
        bought = 0
        while bought < target:
            self.context.ensure_running()
            if not self.listing_matches(observation):
                break
            self.vision.driver.click(*observation.click_center)
            self.waiter.settle(0.50)
            if self.vision.find(
                "x",
                threshold=0.82,
                zone=self.STORAGE_FULL_ZONE,
            ) is not None:
                raise InventoryFull("Kho clone đã đầy trong lúc mua VP")
            bought += 1
            if on_unit is not None:
                on_unit(bought)
            self.context.log(
                f"Mua VP ô vật lý {observation.physical_slot}: "
                f"{bought}/{target} click đã xác nhận"
            )
        return bought
