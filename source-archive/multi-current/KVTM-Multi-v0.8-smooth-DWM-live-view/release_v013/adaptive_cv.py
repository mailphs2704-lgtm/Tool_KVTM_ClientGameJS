"""Scale-aware OpenCV matching for resizable 1000x1000 game clients."""
from __future__ import annotations

import threading

_STATE = threading.local()
_INSTALLED = False
_ORIGINAL = None


def set_capture_scale(scale: float) -> None:
    _STATE.scale = max(0.20, min(1.0, float(scale)))


def install_adaptive_matching() -> None:
    global _INSTALLED, _ORIGINAL
    if _INSTALLED:
        return
    import cv2

    _ORIGINAL = cv2.matchTemplate

    def adaptive_match_template(image, templ, method, *args, **kwargs):
        scale = float(getattr(_STATE, "scale", 1.0))
        if scale >= 0.985:
            return _ORIGINAL(image, templ, method, *args, **kwargs)

        image_h, image_w = image.shape[:2]
        templ_h, templ_w = templ.shape[:2]
        scaled_image = cv2.resize(
            image,
            (max(2, round(image_w * scale)), max(2, round(image_h * scale))),
            interpolation=cv2.INTER_AREA,
        )
        scaled_templ = cv2.resize(
            templ,
            (max(2, round(templ_w * scale)), max(2, round(templ_h * scale))),
            interpolation=cv2.INTER_AREA,
        )

        # Preserve an optional OpenCV mask at the same template scale.
        call_args = list(args)
        if len(call_args) >= 2:
            mask = call_args[1]
            if mask is not None:
                call_args[1] = cv2.resize(
                    mask, (scaled_templ.shape[1], scaled_templ.shape[0]),
                    interpolation=cv2.INTER_NEAREST,
                )
        elif kwargs.get("mask") is not None:
            kwargs["mask"] = cv2.resize(
                kwargs["mask"], (scaled_templ.shape[1], scaled_templ.shape[0]),
                interpolation=cv2.INTER_NEAREST,
            )

        result = _ORIGINAL(scaled_image, scaled_templ, method, *call_args, **kwargs)
        expected_w = max(1, image_w - templ_w + 1)
        expected_h = max(1, image_h - templ_h + 1)
        if result.shape[1] != expected_w or result.shape[0] != expected_h:
            result = cv2.resize(result, (expected_w, expected_h), interpolation=cv2.INTER_LINEAR)
        return result

    cv2.matchTemplate = adaptive_match_template
    _INSTALLED = True
