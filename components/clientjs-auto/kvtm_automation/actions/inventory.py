from __future__ import annotations

from pathlib import Path

from ..context import AutomationContext
from ..models import VisualFingerprint
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter


class InventoryActions:
    """Select the clone storage category and locate one exact VP in inventory."""

    # AUTO_PRO_REFERENCE: recovered sellItems geometry at 1000x1000.
    STORAGE_ZONE = (380, 277, 125, 453)
    INVENTORY_ZONE = (14, 345, 397, 379)
    STORAGE = {
        1: ("kho_nong_san", (455, 371)),
        2: ("kho_thanh_pham", (450, 442)),
        3: ("kho_vat_dung", (445, 517)),
        4: ("kho_khoang_san", (455, 588)),
        5: ("kho_event", (447, 662)),
    }

    def __init__(
        self,
        context: AutomationContext,
        vision: VisionEngine,
        waiter: Waiter,
    ) -> None:
        self.context = context
        self.vision = vision
        self.waiter = waiter

    def select_storage(self, storage_id: int) -> None:
        """Select one verified storage tab; detection alone is never success."""
        storage = int(storage_id)
        if storage not in self.STORAGE:
            raise ValueError("Kho bán phải trong khoảng 1..5")
        template, fallback = self.STORAGE[storage]
        match = self.vision.find(
            template,
            threshold=0.82,
            zone=self.STORAGE_ZONE,
            click=True,
        )
        if match is None:
            # AUTO_PRO_REFERENCE: exact fallback points from sellItems.
            self.vision.driver.click(*fallback)
        self.waiter.sleep(0.40)
        self.context.log(f"Đã chọn kho bán {storage} ({template})")

    def best_fingerprint_match(
        self,
        fingerprint: VisualFingerprint,
    ) -> tuple[tuple[int, int], float] | None:
        """Return the best inventory match, including scores below acceptance."""
        import cv2

        template_file = Path(fingerprint.template_file)
        if not template_file.is_file():
            return None
        template = cv2.imread(str(template_file), cv2.IMREAD_COLOR)
        if template is None or template.size == 0:
            return None
        frame = self.vision.frame()
        x, y, width, height = self.INVENTORY_ZONE
        zone = frame[y : y + height, x : x + width]
        if len(zone.shape) == 3 and zone.shape[2] == 4:
            zone = cv2.cvtColor(zone, cv2.COLOR_BGRA2BGR)

        best_score = -1.0
        best_center = None
        for scale in (0.75, 0.85, 0.95, 1.00, 1.05, 1.15, 1.25):
            tw = max(8, int(round(template.shape[1] * scale)))
            th = max(8, int(round(template.shape[0] * scale)))
            if tw > zone.shape[1] or th > zone.shape[0]:
                continue
            scaled = cv2.resize(
                template,
                (tw, th),
                interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR,
            )
            result = cv2.matchTemplate(zone, scaled, cv2.TM_CCOEFF_NORMED)
            _min, maximum, _min_loc, max_loc = cv2.minMaxLoc(result)
            score = float(maximum)
            if score > best_score:
                best_score = score
                best_center = (
                    x + int(max_loc[0]) + tw // 2,
                    y + int(max_loc[1]) + th // 2,
                )
        if best_center is None:
            return None
        return best_center, best_score

    def find_fingerprint(
        self,
        fingerprint: VisualFingerprint,
        *,
        threshold: float = 0.70,
    ) -> tuple[tuple[int, int], float] | None:
        """Find the normalized core icon captured from a verified purchase."""
        match = self.best_fingerprint_match(fingerprint)
        if match is None or match[1] < float(threshold):
            return None
        return match
