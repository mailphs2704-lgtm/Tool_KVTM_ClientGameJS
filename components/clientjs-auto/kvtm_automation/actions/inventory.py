from __future__ import annotations

from pathlib import Path
import time

from ..context import AutomationContext
from ..errors import ScreenTimeout
from ..models import VisualFingerprint
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter


class InventoryActions:
    """Select the clone storage category and locate one exact VP in inventory."""

    # AUTO_PRO_REFERENCE: recovered sellItems geometry at logical 1000x1000.
    STORAGE_ZONE = (380, 277, 125, 453)
    INVENTORY_ZONE = (14, 345, 397, 379)
    STORAGE = {
        1: ("kho_nong_san", (455, 371)),
        2: ("kho_thanh_pham", (450, 442)),
        3: ("kho_vat_dung", (445, 517)),
        4: ("kho_khoang_san", (455, 588)),
        5: ("kho_event", (447, 662)),
    }
    STORAGE_PICKER_THRESHOLD = 0.72
    STORAGE_TARGET_THRESHOLD = 0.74
    STORAGE_PICKER_SCALES = (0.85, 1.00, 1.15, 1.30, 1.45)
    STORAGE_PICKER_TIMEOUT = 3.0
    STORAGE_SELECT_ATTEMPTS = 3
    STORAGE_CHANGE_MIN = 1.00

    def __init__(
        self,
        context: AutomationContext,
        vision: VisionEngine,
        waiter: Waiter,
    ) -> None:
        self.context = context
        self.vision = vision
        self.waiter = waiter
        self.storage_open_wait = 0.40

    def _inventory_crop(self):
        """Capture only the inventory-content ROI for storage-change evidence."""
        frame = self.vision.frame()
        x, y, width, height = self.vision.logical_zone_to_frame(
            self.INVENTORY_ZONE, frame
        )
        return frame[y : y + height, x : x + width].copy()

    @staticmethod
    def _mean_change(before, after) -> float:
        """Return a simple mean absolute pixel delta between two equal ROIs."""
        import cv2

        if before is None or after is None or before.size == 0 or after.size == 0:
            return 0.0
        if before.shape != after.shape:
            after = cv2.resize(
                after,
                (before.shape[1], before.shape[0]),
                interpolation=cv2.INTER_AREA,
            )
        return float(cv2.absdiff(before, after).mean())

    def wait_storage_picker_ready(self, *, timeout: float | None = None):
        """Wait until the storage tabs themselves are visible before any tab click.

        The sale slot opens the inventory picker asynchronously.  Clicking the
        logical storage2 point before this proof can be consumed by the opening
        transition and leaves the picker on its default warehouse tab.
        """
        deadline = time.monotonic() + float(
            self.STORAGE_PICKER_TIMEOUT if timeout is None else timeout
        )
        names = tuple(template for template, _point in self.STORAGE.values())
        best = None
        while time.monotonic() < deadline:
            self.context.ensure_running()
            best = self.vision.find_any(
                names,
                threshold=self.STORAGE_PICKER_THRESHOLD,
                zone=self.STORAGE_ZONE,
                scales=self.STORAGE_PICKER_SCALES,
                click=False,
            )
            if best is not None:
                self.context.detail(
                    "AUTO kho • picker READY • "
                    f"marker={best.name} • score={best.score:.3f}"
                )
                return best
            self.waiter.sleep(0.15)
        raise ScreenTimeout(
            "Không chứng minh được bảng Kho đã mở; không click Kho thành phẩm"
        )

    def select_storage_after_picker_ready(self, storage_id: int) -> float:
        """Select one storage tab only after picker readiness is proven.

        A targeted template center is preferred.  The historical logical fallback
        is allowed only after the picker proof, never during the opening animation.
        We repeat the same idempotent tab click when the content ROI does not move;
        this covers a swallowed first click without toggling the picker itself.
        """
        storage = int(storage_id)
        if storage not in self.STORAGE:
            raise ValueError("Kho bán phải trong khoảng 1..5")
        template, fallback = self.STORAGE[storage]
        self.wait_storage_picker_ready()

        best_change = 0.0
        for attempt in range(1, self.STORAGE_SELECT_ATTEMPTS + 1):
            self.context.ensure_running()
            before = self._inventory_crop()
            match = self.vision.find(
                template,
                threshold=self.STORAGE_TARGET_THRESHOLD,
                zone=self.STORAGE_ZONE,
                scales=self.STORAGE_PICKER_SCALES,
                click=False,
            )
            point = match.center if match is not None else fallback
            self.context.log(
                f"AUTO kho • picker READY • chọn kho {storage} ({template}) • "
                f"attempt={attempt}/{self.STORAGE_SELECT_ATTEMPTS} • "
                f"source={'template' if match is not None else 'verified-fallback'}"
            )
            self.vision.driver.click(*point)
            self.waiter.sleep(self.storage_open_wait)

            # The picker must remain present after a tab switch.  If it vanished,
            # fail closed rather than scanning/clicking items against another UI.
            self.wait_storage_picker_ready(timeout=1.0)
            after = self._inventory_crop()
            change = self._mean_change(before, after)
            best_change = max(best_change, change)
            self.context.detail(
                f"AUTO kho • storage{storage} postcheck • "
                f"attempt={attempt}/{self.STORAGE_SELECT_ATTEMPTS} • change={change:.2f}"
            )
            if change >= self.STORAGE_CHANGE_MIN:
                self.context.log(
                    f"AUTO kho • storage{storage} PASS • change={change:.2f}"
                )
                return best_change
            if attempt < self.STORAGE_SELECT_ATTEMPTS:
                self.waiter.sleep(0.15)

        # A no-delta result can mean the requested tab was already active.  The
        # destructive sale path remains safe because the following recognition is
        # restricted to finished-goods templates and exact-x10/post-click proofs.
        self.context.log(
            f"AUTO kho • storage{storage} targeted click ổn định • "
            f"best_change={best_change:.2f} • tiếp tục scan giới hạn theo VP"
        )
        return best_change

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
        self.waiter.sleep(self.storage_open_wait)
        self.context.log(f"Đã chọn kho bán {storage} ({template})")

    def best_fingerprint_match(
        self,
        fingerprint: VisualFingerprint,
    ) -> tuple[tuple[int, int], float] | None:
        """Return the best inventory match, including scores below acceptance.

        Fingerprint templates are captured earlier in the same clone transaction,
        so their pixel dimensions already belong to the current rendered client.
        Only the logical 1000 inventory ROI and the returned click center need a
        logical/frame conversion here. Keeping the template at its captured pixel
        size avoids applying the 500 scale twice.
        """
        import cv2

        template_file = Path(fingerprint.template_file)
        if not template_file.is_file():
            return None
        template = cv2.imread(str(template_file), cv2.IMREAD_COLOR)
        if template is None or template.size == 0:
            return None

        frame = self.vision.frame()
        if frame.ndim == 3 and frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        x, y, width, height = self.vision.logical_zone_to_frame(
            self.INVENTORY_ZONE, frame
        )
        zone = frame[y : y + height, x : x + width]
        if zone.size == 0:
            return None

        best_score = -1.0
        best_center = None
        for scale in (0.75, 0.85, 0.95, 1.00, 1.05, 1.15, 1.25):
            tw = max(4, int(round(template.shape[1] * scale)))
            th = max(4, int(round(template.shape[0] * scale)))
            if tw > zone.shape[1] or th > zone.shape[0]:
                continue
            scaled = cv2.resize(
                template,
                (tw, th),
                interpolation=(
                    cv2.INTER_AREA
                    if tw <= template.shape[1] and th <= template.shape[0]
                    else cv2.INTER_LINEAR
                ),
            )
            result = cv2.matchTemplate(zone, scaled, cv2.TM_CCOEFF_NORMED)
            _min, maximum, _min_loc, max_loc = cv2.minMaxLoc(result)
            score = float(maximum)
            if score > best_score:
                best_score = score
                frame_center = (
                    x + int(max_loc[0]) + tw // 2,
                    y + int(max_loc[1]) + th // 2,
                )
                best_center = self.vision.frame_point_to_logical(
                    frame_center, frame
                )

        if best_center is None:
            return None
        frame_h, frame_w = frame.shape[:2]
        self.context.detail(
            "AUTO inventory fingerprint | "
            f"logical_zone={self.INVENTORY_ZONE} | frame_roi={(x, y, width, height)} | "
            f"frame={frame_w}x{frame_h} | center_logical={best_center} | "
            f"score={best_score:.4f}"
        )
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
