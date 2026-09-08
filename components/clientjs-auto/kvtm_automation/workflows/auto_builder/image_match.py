from __future__ import annotations

from pathlib import Path
from typing import Iterable


__all__ = ["match_custom_template"]
FILE_FUNCTIONS = (
    "Nạp template người dùng đã chọn",
    "So khớp template trên fresh frame theo zone/scales",
    "Trả best score/box/center và ghi detail log",
)


def match_custom_template(
    automation,
    template_path: str | Path,
    *,
    threshold: float = 0.80,
    zone: tuple[int, int, int, int] | None = None,
    scales: Iterable[float] = (1.0,),
):
    import cv2

    path = Path(template_path).expanduser().resolve()
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise RuntimeError(f"Không đọc được ảnh nhận diện Builder: {path}")

    source = automation.vision.frame()
    if source.ndim == 3 and source.shape[2] == 4:
        source = cv2.cvtColor(source, cv2.COLOR_BGRA2BGR)
    height, width = source.shape[:2]
    if zone is None:
        x0, y0, x1, y1 = 0, 0, width, height
    else:
        x, y, w, h = map(int, zone)
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(width, x + w), min(height, y + h)
    roi = source[y0:y1, x0:x1]
    if roi.size == 0:
        raise RuntimeError(f"Zone nhận diện Builder rỗng: {zone}")

    best = None
    for scale_value in scales:
        scale = float(scale_value)
        if scale <= 0:
            raise ValueError(f"Scale nhận diện phải > 0: {scale}")
        tw = max(2, int(round(image.shape[1] * scale)))
        th = max(2, int(round(image.shape[0] * scale)))
        if tw > roi.shape[1] or th > roi.shape[0]:
            continue
        template = image
        if (tw, th) != (image.shape[1], image.shape[0]):
            template = cv2.resize(
                image,
                (tw, th),
                interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC,
            )
        result = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
        _min_value, maximum, _min_loc, max_loc = cv2.minMaxLoc(result)
        left, top = x0 + int(max_loc[0]), y0 + int(max_loc[1])
        candidate = {
            "score": float(maximum),
            "center": (left + tw // 2, top + th // 2),
            "box": (left, top, tw, th),
            "scale": scale,
            "template": str(path),
        }
        if best is None or candidate["score"] > best["score"]:
            best = candidate

    score = float(best["score"]) if best else -1.0
    passed = bool(best and score >= float(threshold))
    automation.context.detail(
        "Builder match | "
        f"template={path.name} | score={score:.4f} | threshold={float(threshold):.4f} | "
        f"zone={zone or 'FULL'} | best_box={best['box'] if best else 'NONE'} | "
        f"best_center={best['center'] if best else 'NONE'} | "
        f"{'PASS' if passed else 'FAIL'}"
    )
    return best if passed else None
