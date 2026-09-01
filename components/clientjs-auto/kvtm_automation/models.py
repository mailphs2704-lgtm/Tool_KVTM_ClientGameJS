from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class VisualFingerprint:
    sha256: str
    perceptual_hash: str
    width: int
    height: int
    template_file: str = ""

    @classmethod
    def from_image(cls, image: Any, template_file: str = "") -> "VisualFingerprint":
        raw = image.tobytes()
        height, width = image.shape[:2]
        return cls(
            sha256=hashlib.sha256(raw).hexdigest(),
            perceptual_hash=_average_hash(image),
            width=int(width),
            height=int(height),
            template_file=str(template_file),
        )


@dataclass(frozen=True)
class StallSlotObservation:
    view: int
    local_slot: int
    physical_slot: int
    center: tuple[int, int]
    click_center: tuple[int, int]
    fingerprint: VisualFingerprint
    occupancy_score: float


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
