from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any

from .manifest import ItemFingerprint


# Reference coordinates used by the recovered ClientJS shop flow at 1000x1000.
# The friend stall has twenty physical slots but only eight are visible at once.
TOTAL_STALL_SLOTS = 20
VISIBLE_SLOT_CENTERS = (
    (300, 456), (432, 456), (565, 456), (698, 456),
    (300, 647), (432, 647), (565, 647), (698, 647),
)
VISIBLE_STALL_SLOTS = len(VISIBLE_SLOT_CENTERS)
ICON_HALF_WIDTH = 42
ICON_HALF_HEIGHT = 42
CELL_HALF_WIDTH = 52
CELL_HALF_HEIGHT = 67


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
    slot_signatures: tuple[str, ...]
    signature: str


class StallScanner:
    """Scan overlapping eight-slot views while preserving twenty physical slots."""

    def __init__(
        self,
        template_dir: Path,
        *,
        empty_threshold: float = 9.0,
    ) -> None:
        self.template_dir = Path(template_dir)
        self.empty_threshold = float(empty_threshold)

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

            # A larger cell signature is used only to align two overlapping
            # shop views. It includes item/count/price context and is never used
            # as the item identity for resale.
            cx1 = max(0, center_x - CELL_HALF_WIDTH)
            cx2 = min(width, center_x + CELL_HALF_WIDTH)
            cy1 = max(0, center_y - CELL_HALF_HEIGHT)
            cy2 = min(height, center_y + CELL_HALF_HEIGHT)
            cell = frame[cy1:cy2, cx1:cx2].copy()
            signatures.append(_visual_signature(cell, occupied=score >= self.empty_threshold))

            if score < self.empty_threshold:
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
        return PageScan(
            page=page,
            slots=tuple(slots),
            slot_signatures=tuple(signatures),
            signature=signature,
        )

    @staticmethod
    def infer_forward_shift(previous: PageScan, current: PageScan) -> int:
        """Infer how many physical slots entered from the right after one swipe.

        AUTO PRO's _rollbackItem performs small left swipes, so consecutive
        windows overlap. We accept only sequence-consistent overlaps. When
        repeated empty/equal cells make more than one shift possible, choose
        the smallest shift: this is conservative and prevents buying a physical
        slot twice. The twenty-slot coverage loop will keep swiping for any
        still-unseen positions.
        """
        before = previous.slot_signatures
        after = current.slot_signatures
        if len(before) != VISIBLE_STALL_SLOTS or len(after) != VISIBLE_STALL_SLOTS:
            raise RuntimeError("Ảnh quầy không đủ 8 ô để suy ra vị trí kéo")
        if before == after:
            return 0
        candidates = []
        for shift in range(1, VISIBLE_STALL_SLOTS):
            overlap = VISIBLE_STALL_SLOTS - shift
            if before[shift:] == after[:overlap]:
                candidates.append(shift)
        if not candidates:
            raise RuntimeError(
                "Không xác định được số ô quầy đã dịch sau swipe; dừng để tránh mua trùng"
            )
        return min(candidates)


def _occupancy_score(image: Any) -> float:
    """Use luminance spread as a conservative empty-slot rejection signal."""
    try:
        import cv2
        channels = getattr(image, "shape", (0, 0, 0))[2] if len(image.shape) >= 3 else 1
        conversion = cv2.COLOR_BGRA2GRAY if channels == 4 else cv2.COLOR_BGR2GRAY
        gray = cv2.cvtColor(image, conversion)
        return float(gray.std())
    except Exception:
        raw = image.tobytes()
        if not raw:
            return 0.0
        pixels = max(1, int(getattr(image, "shape", (1, 1))[0]) * int(getattr(image, "shape", (1, 1))[1]))
        channels = max(1, len(raw) // pixels)
        luminance = []
        for offset in range(0, len(raw) - max(2, channels - 1), channels):
            blue = raw[offset]
            green = raw[offset + 1] if channels > 1 else blue
            red = raw[offset + 2] if channels > 2 else green
            luminance.append((int(red) * 30 + int(green) * 59 + int(blue) * 11) // 100)
        average = sum(luminance) / max(1, len(luminance))
        variance = sum((value - average) ** 2 for value in luminance) / max(
            1, len(luminance)
        )
        return variance ** 0.5


def _visual_signature(image: Any, *, occupied: bool) -> str:
    """Compact stable cell signature for overlap alignment, not item identity."""
    try:
        import cv2
        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGRA2GRAY if image.shape[2] == 4 else cv2.COLOR_BGR2GRAY,
        )
        tiny = cv2.resize(gray, (16, 16), interpolation=cv2.INTER_AREA)
        mean = float(tiny.mean())
        bits = 0
        for value in tiny.reshape(-1):
            bits = (bits << 1) | int(float(value) >= mean)
        prefix = "o" if occupied else "e"
        return prefix + f"{bits:064x}"
    except Exception:
        prefix = b"o" if occupied else b"e"
        return (prefix + hashlib.sha256(image.tobytes()).hexdigest().encode("ascii")[:64]).decode("ascii")


def _save_image(path: Path, image: Any) -> None:
    try:
        import cv2
        if not cv2.imwrite(str(path), image):
            raise RuntimeError(f"Không lưu được template: {path}")
    except ImportError as exc:
        raise RuntimeError("Thiếu OpenCV để lưu template vật phẩm") from exc
