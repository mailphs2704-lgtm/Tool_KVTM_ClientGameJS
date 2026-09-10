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
    STORAGE2_ACTIVE_ZONE = (398, 395, 100, 96)
    STORAGE = {
        1: ("kho_nong_san", (455, 371)),
        2: ("kho_thanh_pham", (450, 442)),
        3: ("kho_vat_dung", (445, 517)),
        4: ("kho_khoang_san", (455, 588)),
        5: ("kho_event", (447, 662)),
    }

    # Native-500 opening proof. Before picker open these markers stayed <0.39.
    N500_PICKER_THRESHOLD = 0.72
    N500_PICKER_SCALES = (0.85, 1.00, 1.15, 1.30, 1.45)
    # Once storage2 is active the tab art changes and no single icon is guaranteed
    # to remain >=0.72. Live active scores included 0.6265/0.6369/0.6184. Two
    # independent >=0.52 markers therefore prove the picker is still visible,
    # but NEVER prove which storage is active.
    N500_PICKER_VISIBLE_THRESHOLD = 0.52
    N500_PICKER_VISIBLE_REQUIRED_MARKERS = 2
    # Target-specific storage2 calibration: kho_thanh_pham ~0.332 before selection
    # and ~0.508 after selection. Require two consecutive target passes in its row.
    N500_STORAGE2_ACTIVE_THRESHOLD = 0.46
    N500_STORAGE2_ACTIVE_PASSES = 2

    # Baseline 1000 contract from AUTO PRO / pre-native migration.
    N1000_PICKER_THRESHOLD = 0.82
    N1000_PICKER_SCALES = (1.00,)
    N1000_STORAGE_TARGET_THRESHOLD = 0.82

    STORAGE_PICKER_TIMEOUT = 3.0
    STORAGE_ACTIVE_TIMEOUT = 2.5
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

    def _native_size(self) -> tuple[int, int]:
        size = getattr(self.vision.driver, "native_size", None)
        if size is not None:
            return tuple(map(int, size))
        frame = self.vision.frame()
        height, width = frame.shape[:2]
        return int(width), int(height)

    def _is_native_500(self) -> bool:
        return self._native_size() == (500, 500)

    def _picker_profile(self) -> tuple[float, tuple[float, ...]]:
        if self._is_native_500():
            return self.N500_PICKER_THRESHOLD, self.N500_PICKER_SCALES
        return self.N1000_PICKER_THRESHOLD, self.N1000_PICKER_SCALES

    def _inventory_crop(self):
        frame = self.vision.frame()
        x, y, width, height = self.vision.logical_zone_to_frame(
            self.INVENTORY_ZONE, frame
        )
        return frame[y : y + height, x : x + width].copy()

    @staticmethod
    def _mean_change(before, after) -> float:
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

    def _storage_marker_matches(
        self,
        *,
        threshold: float,
        scales: tuple[float, ...],
    ):
        matches = []
        for template, _point in self.STORAGE.values():
            match = self.vision.find(
                template,
                threshold=float(threshold),
                zone=self.STORAGE_ZONE,
                scales=scales,
                click=False,
            )
            if match is not None:
                matches.append(match)
        return tuple(matches)

    def _native500_picker_visible_matches(self):
        return self._storage_marker_matches(
            threshold=self.N500_PICKER_VISIBLE_THRESHOLD,
            scales=self.N500_PICKER_SCALES,
        )

    def is_storage_picker_ready(self) -> bool:
        """Read-only picker visibility proof; never implies storage2 active."""
        threshold, scales = self._picker_profile()
        strict = self._storage_marker_matches(
            threshold=threshold,
            scales=scales,
        )
        if strict:
            return True
        if self._is_native_500():
            return (
                len(self._native500_picker_visible_matches())
                >= self.N500_PICKER_VISIBLE_REQUIRED_MARKERS
            )
        return False

    def wait_storage_picker_ready(
        self,
        *,
        timeout: float | None = None,
        threshold: float | None = None,
        required_markers: int = 1,
    ):
        """Wait for picker visibility without authorizing any storage content.

        Native 500 accepts either one strict opening marker (>=0.72) or two lower
        active-style markers (>=0.52). The lower proof cannot fire on the own-stall
        pre-open state from the live calibration and prevents a selected storage2
        picker from being mistaken for closed after cancel.
        """
        profile_threshold, scales = self._picker_profile()
        marker_threshold = float(
            profile_threshold if threshold is None else threshold
        )
        required = max(1, int(required_markers))
        deadline = time.monotonic() + float(
            self.STORAGE_PICKER_TIMEOUT if timeout is None else timeout
        )
        last_matches = ()
        while time.monotonic() < deadline:
            self.context.ensure_running()
            last_matches = self._storage_marker_matches(
                threshold=marker_threshold,
                scales=scales,
            )
            ready = len(last_matches) >= required
            proof = "strict"
            if (
                not ready
                and threshold is None
                and required == 1
                and self._is_native_500()
            ):
                visible = self._native500_picker_visible_matches()
                if len(visible) >= self.N500_PICKER_VISIBLE_REQUIRED_MARKERS:
                    last_matches = visible
                    ready = True
                    proof = "native500-active-visible"
            if ready:
                best = max(last_matches, key=lambda item: float(item.score))
                native = self._native_size()
                self.context.detail(
                    "AUTO kho • PICKER READY • "
                    f"native={native[0]}x{native[1]} • proof={proof} • "
                    f"markers={len(last_matches)} • best={best.name}:{best.score:.3f}"
                )
                return best
            self.waiter.sleep(0.15)
        raise ScreenTimeout(
            "Không chứng minh được bảng Kho đã mở; không click Kho thành phẩm • "
            f"markers={len(last_matches)}/{required} • threshold={marker_threshold:.2f}"
        )

    def _wait_native500_storage2_active(self, *, timeout: float | None = None):
        """Prove storage2 specifically; generic storage icons cannot authorize it."""
        deadline = time.monotonic() + float(
            self.STORAGE_ACTIVE_TIMEOUT if timeout is None else timeout
        )
        passes = 0
        best = None
        while time.monotonic() < deadline:
            self.context.ensure_running()
            match = self.vision.find(
                "kho_thanh_pham",
                threshold=self.N500_STORAGE2_ACTIVE_THRESHOLD,
                zone=self.STORAGE2_ACTIVE_ZONE,
                scales=self.N500_PICKER_SCALES,
                click=False,
            )
            visible = self._native500_picker_visible_matches()
            picker_visible = (
                len(visible) >= self.N500_PICKER_VISIBLE_REQUIRED_MARKERS
            )
            if match is None or not picker_visible:
                passes = 0
            else:
                passes += 1
                if best is None or match.score > best.score:
                    best = match
                self.context.detail(
                    "AUTO kho • STORAGE2 ACTIVE proof • native=500x500 • "
                    f"passes={passes}/{self.N500_STORAGE2_ACTIVE_PASSES} • "
                    f"target={match.score:.3f} • generic_markers={len(visible)}"
                )
                if passes >= self.N500_STORAGE2_ACTIVE_PASSES:
                    return best
            self.waiter.sleep(0.15)
        raise ScreenTimeout(
            "Kho thành phẩm storage2 chưa đạt target-specific ACTIVE proof trên "
            "native 500; không dùng marker của tab kho khác để thay thế"
        )

    def select_storage_after_picker_ready(self, storage_id: int) -> float:
        """Click requested storage at most once, then wait for its safe state."""
        storage = int(storage_id)
        if storage not in self.STORAGE:
            raise ValueError("Kho bán phải trong khoảng 1..5")
        template, fallback = self.STORAGE[storage]
        self.wait_storage_picker_ready()

        before = self._inventory_crop()
        native = self._native_size()
        if native == (500, 500) and storage == 2:
            try:
                active = self._wait_native500_storage2_active(timeout=0.45)
            except ScreenTimeout:
                active = None
            if active is None:
                candidate = self.vision.find(
                    template,
                    threshold=self.N500_PICKER_THRESHOLD,
                    zone=self.STORAGE2_ACTIVE_ZONE,
                    scales=self.N500_PICKER_SCALES,
                    click=False,
                )
                point = candidate.center if candidate is not None else fallback
                self.context.log(
                    "AUTO kho • PICKER READY • STORAGE2 click-once • "
                    f"native=500x500 • point={point}"
                )
                self.vision.driver.click(*point)
                self._wait_native500_storage2_active()
            else:
                self.context.log(
                    "AUTO kho • STORAGE2 ACTIVE sẵn • native=500x500 • "
                    f"score={active.score:.3f} • không click lại"
                )
        else:
            scales = self.N1000_PICKER_SCALES if native == (1000, 1000) else (1.0,)
            threshold = (
                self.N1000_STORAGE_TARGET_THRESHOLD
                if native == (1000, 1000)
                else self.N1000_PICKER_THRESHOLD
            )
            candidate = self.vision.find(
                template,
                threshold=threshold,
                zone=self.STORAGE_ZONE,
                scales=scales,
                click=False,
            )
            point = candidate.center if candidate is not None else fallback
            self.context.log(
                "AUTO kho • PICKER READY • storage click-once • "
                f"native={native[0]}x{native[1]} • storage={storage} • point={point} • "
                "contract=1000-baseline"
            )
            self.vision.driver.click(*point)
            self.waiter.sleep(self.storage_open_wait)
            self.wait_storage_picker_ready(timeout=1.5)

        after = self._inventory_crop()
        change = self._mean_change(before, after)
        self.context.log(
            f"AUTO kho • STORAGE{storage} READY • native={native[0]}x{native[1]} • "
            f"content_change={change:.2f} • click_count<=1"
        )
        return change

    def select_storage(self, storage_id: int) -> None:
        """Shared legacy selector retained for non-AUTO-Main transactions."""
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
            self.vision.driver.click(*fallback)
        self.waiter.sleep(self.storage_open_wait)
        self.context.log(f"Đã chọn kho bán {storage} ({template})")

    def best_fingerprint_match(
        self,
        fingerprint: VisualFingerprint,
    ) -> tuple[tuple[int, int], float] | None:
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
        match = self.best_fingerprint_match(fingerprint)
        if match is None or match[1] < float(threshold):
            return None
        return match
