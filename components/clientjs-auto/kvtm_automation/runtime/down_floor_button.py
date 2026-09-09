from __future__ import annotations

import base64
from dataclasses import dataclass
from functools import lru_cache

__all__ = ["DownFloorButtonMatch", "find_down_floor_button"]

# User-confirmed 1000x1000 ClientJS sample, cropped tightly around the bottom-edge
# "XUỐNG" control. Keep it embedded so Multi DEV packaging cannot silently omit
# the detector asset.
_TEMPLATE_PNG_B64 = (
    "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"
)


@dataclass(frozen=True)
class DownFloorButtonMatch:
    score: float
    # Public geometry is logical 1000x1000 because callers pass center to the
    # shared driver, which owns the final logical->client scaling.
    center: tuple[int, int]
    box: tuple[int, int, int, int]
    # Actual template/frame scale used by this dedicated detector.
    scale: float


@lru_cache(maxsize=1)
def _template_gray():
    import cv2
    import numpy as np

    raw = base64.b64decode(_TEMPLATE_PNG_B64)
    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None or image.size == 0:
        raise RuntimeError("Không giải mã được template nút XUỐNG")
    return image


def _frame_point_to_logical(
    point: tuple[int | float, int | float],
    *,
    width: int,
    height: int,
) -> tuple[int, int]:
    if width <= 0 or height <= 0:
        raise ValueError("Frame XUỐNG không có kích thước hợp lệ")
    return (
        int(round(float(point[0]) * 1000.0 / float(width))),
        int(round(float(point[1]) * 1000.0 / float(height))),
    )


def _frame_box_to_logical(
    box: tuple[int, int, int, int],
    *,
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    left, top, box_width, box_height = box
    logical_left, logical_top = _frame_point_to_logical(
        (left, top), width=width, height=height
    )
    logical_right, logical_bottom = _frame_point_to_logical(
        (left + box_width, top + box_height), width=width, height=height
    )
    return (
        logical_left,
        logical_top,
        max(1, logical_right - logical_left),
        max(1, logical_bottom - logical_top),
    )


def find_down_floor_button(
    frame,
    *,
    threshold: float = 0.78,
) -> DownFloorButtonMatch | None:
    """Find the transient bottom-edge XUỐNG control on a fresh ClientJS frame.

    The operator-confirmed behavior is important: this control only appears
    during floor-transition interaction on upper floors and is absent on floor 1.
    Search is therefore intentionally restricted to the bottom-center strip.

    Matching occurs in real frame pixels, but the returned center/box are mapped
    back to logical 1000x1000. This keeps the existing caller safe at 500x500:
    ``driver.click(*match.center)`` performs exactly one resolution conversion.
    """
    import cv2

    source = frame
    if source is None or getattr(source, "size", 0) == 0:
        return None
    if source.ndim == 3 and source.shape[2] == 4:
        source = cv2.cvtColor(source, cv2.COLOR_BGRA2BGR)
    if source.ndim == 3:
        gray = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
    else:
        gray = source

    height, width = gray.shape[:2]
    x0 = max(0, int(round(width * 0.38)))
    x1 = min(width, int(round(width * 0.62)))
    y0 = max(0, int(round(height * 0.935)))
    y1 = height
    roi = gray[y0:y1, x0:x1]
    if roi.size == 0:
        return None

    template = _template_gray()
    # 500x500 maps to exactly 0.50; keep the proven lower bound for this
    # migration. Smaller production sizes require a separate live proof.
    base_scale = max(0.50, min(2.00, min(width, height) / 1000.0))
    best: DownFloorButtonMatch | None = None
    for factor in (0.90, 0.95, 1.00, 1.05, 1.10):
        scale = base_scale * factor
        tw = max(8, int(round(template.shape[1] * scale)))
        th = max(4, int(round(template.shape[0] * scale)))
        if tw > roi.shape[1] or th > roi.shape[0]:
            continue
        scaled = template
        if (tw, th) != (template.shape[1], template.shape[0]):
            scaled = cv2.resize(
                template,
                (tw, th),
                interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC,
            )
        result = cv2.matchTemplate(roi, scaled, cv2.TM_CCOEFF_NORMED)
        _min_value, max_value, _min_loc, max_loc = cv2.minMaxLoc(result)
        score = float(max_value)
        left = x0 + int(max_loc[0])
        top = y0 + int(max_loc[1])
        frame_box = (left, top, tw, th)
        frame_center = (left + tw // 2, top + th // 2)
        match = DownFloorButtonMatch(
            score=score,
            center=_frame_point_to_logical(
                frame_center, width=width, height=height
            ),
            box=_frame_box_to_logical(
                frame_box, width=width, height=height
            ),
            scale=scale,
        )
        if best is None or match.score > best.score:
            best = match

    if best is None or best.score < float(threshold):
        return None
    return best
