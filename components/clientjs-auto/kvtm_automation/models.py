from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from typing import Any


@dataclass(frozen=True)
class VisualFingerprint:
    """Stable visual identity used across scans, carryover and resale."""

    sha256: str
    perceptual_hash: str
    width: int
    height: int
    template_file: str = ""

    def __post_init__(self) -> None:
        if len(str(self.sha256)) != 64:
            raise ValueError("Fingerprint SHA-256 không hợp lệ")
        if len(str(self.perceptual_hash)) != 16:
            raise ValueError("Fingerprint perceptual hash không hợp lệ")
        if int(self.width) <= 0 or int(self.height) <= 0:
            raise ValueError("Fingerprint thiếu kích thước ảnh")

    @classmethod
    def from_image(cls, image: Any, template_file: str = "") -> "VisualFingerprint":
        if image is None or getattr(image, "size", 0) == 0:
            raise ValueError("Ảnh fingerprint rỗng")
        raw = image.tobytes()
        height, width = image.shape[:2]
        return cls(
            sha256=hashlib.sha256(raw).hexdigest(),
            perceptual_hash=_average_hash(image),
            width=int(width),
            height=int(height),
            template_file=str(template_file),
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "VisualFingerprint":
        if not isinstance(payload, dict):
            raise ValueError("Fingerprint JSON không hợp lệ")
        return cls(
            sha256=str(payload.get("sha256") or ""),
            perceptual_hash=str(payload.get("perceptual_hash") or ""),
            width=int(payload.get("width") or 0),
            height=int(payload.get("height") or 0),
            template_file=str(payload.get("template_file") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def group_key(self) -> str:
        """Conservative same-VP key used to build exact batches of ten."""
        return self.perceptual_hash


@dataclass(frozen=True)
class StallSlotObservation:
    view: int
    local_slot: int
    physical_slot: int
    center: tuple[int, int]
    click_center: tuple[int, int]
    fingerprint: VisualFingerprint
    occupancy_score: float

    def __post_init__(self) -> None:
        if not 1 <= int(self.view) <= 4:
            raise ValueError("View quầy phải trong khoảng 1..4")
        if not 1 <= int(self.local_slot) <= 8:
            raise ValueError("Ô hiển thị quầy phải trong khoảng 1..8")
        if not 1 <= int(self.physical_slot) <= 20:
            raise ValueError("Ô vật lý quầy phải trong khoảng 1..20")


def hamming_distance(first: str, second: str) -> int:
    return (int(first, 16) ^ int(second, 16)).bit_count()


def _average_hash(image: Any) -> str:
    import cv2

    if len(image.shape) == 3:
        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGRA2GRAY if image.shape[2] == 4 else cv2.COLOR_BGR2GRAY,
        )
    else:
        gray = image
    tiny = cv2.resize(gray, (8, 8), interpolation=cv2.INTER_AREA)
    average = float(tiny.mean())
    bits = 0
    for value in tiny.reshape(-1):
        bits = (bits << 1) | int(float(value) >= average)
    return f"{bits:016x}"
