from __future__ import annotations

from pathlib import Path
from typing import Iterable


__all__ = ["match_custom_template"]
FILE_FUNCTIONS = (
    "Nạp template người dùng đã chọn",
    "So khớp template trên fresh frame theo zone/scales logical 1000",
    "Scale template vào kích thước frame ClientJS thực tế",
    "Trả best score/box/center ở logical 1000 và ghi detail log",
)


def match_custom_template(
    automation,
    template_path: str | Path,
    *,
    threshold: float = 0.80,
    zone: tuple[int, int, int, int] | None = None,
    scales: Iterable[float] = (1.0,),
):
    """Match one Builder template while preserving logical-1000 geometry.

    Builder coordinates/zones are stored in the same 1000x1000 logical space as
    normal Actions. User-selected Builder templates are therefore treated as
    reference-space templates and resized into the fresh ClientJS frame before
    matching. Public box/center values are converted back to logical coordinates.
    """
    import cv2

    path = Path(template_path).expanduser().resolve()
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise RuntimeError(f"Không đọc được ảnh nhận diện Builder: {path}")

    source = automation.vision.frame()
    if source.ndim == 3 and source.shape[2] == 4:
        source = cv2.cvtColor(source, cv2.COLOR_BGRA2BGR)
    height, width = source.shape[:2]
    frame_sx, frame_sy = automation.vision.frame_scales(source)

    if zone is None:
        x0, y0, roi_w, roi_h = 0, 0, width, height
    else:
        x0, y0, roi_w, roi_h = automation.vision.logical_zone_to_frame(
            zone, source
        )
    x1, y1 = x0 + roi_w, y0 + roi_h
    roi = source[y0:y1, x0:x1]
    if roi.size == 0:
        raise RuntimeError(
            f"Zone nhận diện Builder rỗng: logical={zone}, "
            f"frame_roi={(x0, y0, roi_w, roi_h)}, frame={width}x{height}"
        )

    best = None
    best_frame_box = None
    best_frame_center = None
    for scale_value in scales:
        scale = float(scale_value)
        if scale <= 0:
            raise ValueError(f"Scale nhận diện phải > 0: {scale}")
        tw = max(2, int(round(image.shape[1] * frame_sx * scale)))
        th = max(2, int(round(image.shape[0] * frame_sy * scale)))
        if tw > roi.shape[1] or th > roi.shape[0]:
            continue
        template = image
        if (tw, th) != (image.shape[1], image.shape[0]):
            template = cv2.resize(
                image,
                (tw, th),
                interpolation=(
                    cv2.INTER_AREA
                    if tw <= image.shape[1] and th <= image.shape[0]
                    else cv2.INTER_CUBIC
                ),
            )
        result = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
        _min_value, maximum, _min_loc, max_loc = cv2.minMaxLoc(result)
        left, top = x0 + int(max_loc[0]), y0 + int(max_loc[1])
        frame_box = (left, top, tw, th)
        frame_center = (left + tw // 2, top + th // 2)
        candidate = {
            "score": float(maximum),
            "center": automation.vision.frame_point_to_logical(
                frame_center, source
            ),
            "box": automation.vision.frame_box_to_logical(frame_box, source),
            "scale": scale,
            "template": str(path),
        }
        if best is None or candidate["score"] > best["score"]:
            best = candidate
            best_frame_box = frame_box
            best_frame_center = frame_center

    score = float(best["score"]) if best else -1.0
    passed = bool(best and score >= float(threshold))
    automation.context.detail(
        "Builder match | "
        f"template={path.name} | score={score:.4f} | threshold={float(threshold):.4f} | "
        f"logical_zone={zone or 'FULL'} | frame_roi={(x0, y0, roi_w, roi_h)} | "
        f"frame={width}x{height} | frame_scale=({frame_sx:.4f},{frame_sy:.4f}) | "
        f"best_box_logical={best['box'] if best else 'NONE'} | "
        f"best_center_logical={best['center'] if best else 'NONE'} | "
        f"best_box_frame={best_frame_box or 'NONE'} | "
        f"best_center_frame={best_frame_center or 'NONE'} | "
        f"{'PASS' if passed else 'FAIL'}"
    )
    return best if passed else None
