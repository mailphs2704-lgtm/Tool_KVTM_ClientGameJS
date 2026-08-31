from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any

from .manifest import ItemFingerprint, hamming_distance


# Reference coordinates used by the recovered ClientJS shop flow at 1000x1000.
# Crops stay inside the icon and avoid price/count text.
VISIBLE_SLOT_CENTERS = (
    (300, 456), (432, 456), (565, 456), (698, 456),
    (300, 647), (432, 647), (565, 647), (698, 647),
)
ICON_HALF_WIDTH = 42
ICON_HALF_HEIGHT = 42


@dataclass(frozen=True)
class DetectedSlot:
    page: int
    slot: int
    center: tuple[int, int]
    fingerprint: ItemFingerprint
    occupancy_score: float


@dataclass(frozen=True)
class PageScan:
    page: int
    slots: tuple[DetectedSlot, ...]
    signature: str


class StallScanner:
    """Scan every visible shop page without assuming only eight total items."""

    def __init__(
        self,
        template_dir: Path,
        *,
        empty_threshold: float = 9.0,
        duplicate_distance: int = 4,
    ) -> None:
        self.template_dir = Path(template_dir)
        self.empty_threshold = float(empty_threshold)
        self.duplicate_distance = int(duplicate_distance)
        self._page_signatures: list[str] = []
        self._item_hashes: list[str] = []

    def scan_page(self, frame: Any, page: int) -> PageScan:
        if page < 1:
            raise ValueError("Trang quầy phải bắt đầu từ 1")
        height, width = frame.shape[:2]
        if width < 800 or height < 750:
            raise RuntimeError(
                f"Khung ClientJS quá nhỏ để quét quầy: {width}x{height}"
            )
        self.template_dir.mkdir(parents=True, exist_ok=True)
        slots = []
        signatures = []
        for slot_number, (center_x, center_y) in enumerate(
            VISIBLE_SLOT_CENTERS, start=1
        ):
            x1, x2 = center_x - ICON_HALF_WIDTH, center_x + ICON_HALF_WIDTH
            y1, y2 = center_y - ICON_HALF_HEIGHT, center_y + ICON_HALF_HEIGHT
            crop = frame[y1:y2, x1:x2].copy()
            score = _occupancy_score(crop)
            if score < self.empty_threshold:
                signatures.append("empty")
                continue
            raw = crop.tobytes()
            template_file = self.template_dir / (
                f"page-{page:02d}-slot-{slot_number:02d}.png"
            )
            _save_image(template_file, crop)
            fingerprint = ItemFingerprint.from_bgra(
                raw,
                crop.shape[1],
                crop.shape[0],
                str(template_file),
            )
            signatures.append(fingerprint.perceptual_hash)
            if self._is_duplicate_item(fingerprint.perceptual_hash):
                continue
            self._item_hashes.append(fingerprint.perceptual_hash)
            slots.append(
                DetectedSlot(
                    page=page,
                    slot=slot_number,
                    center=(center_x, center_y),
                    fingerprint=fingerprint,
                    occupancy_score=score,
                )
            )
        signature = hashlib.sha256("|".join(signatures).encode("ascii")).hexdigest()
        return PageScan(page=page, slots=tuple(slots), signature=signature)

    def page_was_seen(self, scan: PageScan) -> bool:
        if scan.signature in self._page_signatures:
            return True
        self._page_signatures.append(scan.signature)
        return False

    def _is_duplicate_item(self, current_hash: str) -> bool:
        return any(
            hamming_distance(current_hash, previous) <= self.duplicate_distance
            for previous in self._item_hashes
        )


def _occupancy_score(image: Any) -> float:
    """Use luminance spread as a conservative empty-slot rejection signal."""
    try:
        import cv2
        gray = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
        return float(gray.std())
    except Exception:
        raw = image.tobytes()
        if not raw:
            return 0.0
        luminance = []
        for offset in range(0, len(raw) - 3, 4):
            blue, green, red = raw[offset : offset + 3]
            luminance.append((int(red) * 30 + int(green) * 59 + int(blue) * 11) // 100)
        average = sum(luminance) / max(1, len(luminance))
        variance = sum((value - average) ** 2 for value in luminance) / max(
            1, len(luminance)
        )
        return variance ** 0.5


def _save_image(path: Path, image: Any) -> None:
    try:
        import cv2
        if not cv2.imwrite(str(path), image):
            raise RuntimeError(f"Không lưu được template: {path}")
    except ImportError as exc:
        raise RuntimeError("Thiếu OpenCV để lưu template vật phẩm") from exc
