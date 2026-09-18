from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

__all__ = ["Match", "VisionEngine"]
FILE_FUNCTIONS = (
    "Chụp frame ClientJS qua driver",
    "Giữ API tọa độ/zone ở hệ logical 1000x1000 dù client thật nhỏ hơn",
    "Scale zone logical sang frame pixel trước khi crop",
    "Scale template 1000-reference theo kích thước frame trước khi match",
    "Đổi center/box frame-pixel về logical trước khi trả cho action/driver",
    "Nạp và cache template",
    "So khớp một template với score/threshold",
    "So khớp nhóm template trên cùng một frame",
    "Ghi trace nhận diện PASS hoặc FAIL với cả logical zone và frame ROI",
)

from .assets import AssetLibrary


@dataclass(frozen=True)
class Match:
    name: str
    score: float
    # Public match geometry is always logical reference-space. This is critical:
    # driver.click() already converts logical coordinates to the actual client.
    center: tuple[int, int]
    box: tuple[int, int, int, int]
    template: Path
    # ``scale`` remains the caller-requested template search factor. The actual
    # frame scale is applied separately by VisionEngine.
    scale: float


class VisionEngine:
    """Deterministic matcher with a fixed logical coordinate contract.

    Actions keep using the established 1000x1000 coordinates. Screenshots are
    captured at the real ClientJS client size (for example 500x500), so every
    logical ROI/template is mapped into that frame for matching. Match geometry
    is then mapped back to logical space before it leaves this class.

    Keeping that boundary here prevents two dangerous regressions:

    * business code does not need duplicate coordinate tables per resolution;
    * a frame-pixel match center is never passed to a driver which would scale
      it a second time.
    """

    REFERENCE_SIZE = (1000, 1000)

    def __init__(
        self,
        driver: Any,
        assets: AssetLibrary,
        *,
        detail_logger: Callable[[str], None] | None = None,
        reference_size: tuple[int, int] | None = None,
    ) -> None:
        self.driver = driver
        self.assets = assets
        self.detail_logger = detail_logger
        inherited = reference_size or getattr(driver, "reference_size", None)
        if inherited is None:
            inherited = self.REFERENCE_SIZE
        ref_w, ref_h = map(int, inherited)
        if ref_w <= 0 or ref_h <= 0:
            raise ValueError("Vision reference_size phải dương")
        self.reference_size = (ref_w, ref_h)
        self._cache: dict[Path, Any] = {}

    def _detail(self, message: str) -> None:
        if self.detail_logger is not None:
            try:
                self.detail_logger(str(message))
            except Exception:
                pass

    def frame(self):
        return self.driver.screenshot(format="opencv")

    def _template(self, path: Path):
        import cv2

        cached = self._cache.get(path)
        if cached is not None:
            return cached
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None or image.size == 0:
            return None
        self._cache[path] = image
        return image

    def frame_scales(self, frame) -> tuple[float, float]:
        """Return frame-pixel per logical-unit scale for one captured frame."""
        height, width = frame.shape[:2]
        ref_w, ref_h = self.reference_size
        return width / float(ref_w), height / float(ref_h)

    def logical_point_to_frame(
        self,
        point: tuple[int | float, int | float],
        frame,
    ) -> tuple[int, int]:
        sx, sy = self.frame_scales(frame)
        return (
            int(round(float(point[0]) * sx)),
            int(round(float(point[1]) * sy)),
        )

    def frame_point_to_logical(
        self,
        point: tuple[int | float, int | float],
        frame,
    ) -> tuple[int, int]:
        sx, sy = self.frame_scales(frame)
        if sx <= 0.0 or sy <= 0.0:
            raise ValueError("Frame scale không hợp lệ")
        return (
            int(round(float(point[0]) / sx)),
            int(round(float(point[1]) / sy)),
        )

    def logical_zone_to_frame(
        self,
        zone: tuple[int | float, int | float, int | float, int | float],
        frame,
    ) -> tuple[int, int, int, int]:
        """Map one logical ``(x,y,w,h)`` zone to a clipped frame-pixel zone."""
        height, width = frame.shape[:2]
        x, y, w, h = map(float, zone)
        sx, sy = self.frame_scales(frame)
        left = max(0, min(width, int(round(x * sx))))
        top = max(0, min(height, int(round(y * sy))))
        right = max(0, min(width, int(round((x + w) * sx))))
        bottom = max(0, min(height, int(round((y + h) * sy))))
        return left, top, max(0, right - left), max(0, bottom - top)

    def frame_box_to_logical(
        self,
        box: tuple[int | float, int | float, int | float, int | float],
        frame,
    ) -> tuple[int, int, int, int]:
        """Map a frame-pixel box back to logical space using edge conversion."""
        left, top, width, height = map(float, box)
        logical_left, logical_top = self.frame_point_to_logical((left, top), frame)
        logical_right, logical_bottom = self.frame_point_to_logical(
            (left + width, top + height), frame
        )
        return (
            logical_left,
            logical_top,
            max(1, logical_right - logical_left),
            max(1, logical_bottom - logical_top),
        )

    def find(
        self,
        name: str,
        *,
        threshold: float = 0.80,
        zone: tuple[int, int, int, int] | None = None,
        scales: Iterable[float] = (1.0,),
        click: bool = False,
        frame=None,
        trace: bool = True,
    ) -> Match | None:
        import cv2

        source = self.frame() if frame is None else frame
        if source.ndim == 3 and source.shape[2] == 4:
            source = cv2.cvtColor(source, cv2.COLOR_BGRA2BGR)
        height, width = source.shape[:2]
        frame_sx, frame_sy = self.frame_scales(source)

        if zone is None:
            x0, y0, roi_w, roi_h = 0, 0, width, height
        else:
            x0, y0, roi_w, roi_h = self.logical_zone_to_frame(zone, source)
        x1, y1 = x0 + roi_w, y0 + roi_h
        roi = source[y0:y1, x0:x1]
        frame_roi = (x0, y0, roi_w, roi_h)

        if roi.size == 0:
            if trace:
                self._detail(
                f"Match [{name}] | Context: clean-main | Score: -1.0000 | "
                f"Threshold: {float(threshold):.4f} | LogicalZone: {zone or 'FULL'} | "
                f"FrameROI: {frame_roi} | Frame: {width}x{height} | "
                f"FrameScale: ({frame_sx:.4f},{frame_sy:.4f}) | "
                "BestBoxLogical: NONE | BestCenterLogical: NONE | "
                "BestBoxFrame: NONE | BestCenterFrame: NONE | "
                    "Scale: 0.00 | Template: NONE | FAIL"
                )
            return None

        best: Match | None = None
        best_frame_box: tuple[int, int, int, int] | None = None
        best_frame_center: tuple[int, int] | None = None
        best_template_size: tuple[int, int] | None = None

        for path in self.assets.candidates(name):
            template = self._template(path)
            if template is None:
                continue
            for scale in scales:
                scale = float(scale)
                # Templates in the shared library are referenced to the same
                # logical 1000x1000 canvas as action coordinates. Resize into
                # the actual frame before matching. At 1000x1000 this is exactly
                # the legacy template size; at 500x500 it is half-size.
                tw = max(
                    2,
                    int(round(template.shape[1] * frame_sx * scale)),
                )
                th = max(
                    2,
                    int(round(template.shape[0] * frame_sy * scale)),
                )
                if tw > roi.shape[1] or th > roi.shape[0]:
                    continue
                scaled = template
                if (tw, th) != (template.shape[1], template.shape[0]):
                    interpolation = (
                        cv2.INTER_AREA
                        if tw <= template.shape[1] and th <= template.shape[0]
                        else cv2.INTER_CUBIC
                    )
                    scaled = cv2.resize(template, (tw, th), interpolation=interpolation)

                result = cv2.matchTemplate(roi, scaled, cv2.TM_CCOEFF_NORMED)
                _minimum, maximum, _min_loc, max_loc = cv2.minMaxLoc(result)
                score = float(maximum)
                left = x0 + int(max_loc[0])
                top = y0 + int(max_loc[1])
                frame_box = (left, top, tw, th)
                frame_center = (left + tw // 2, top + th // 2)
                match = Match(
                    name=str(name),
                    score=score,
                    center=self.frame_point_to_logical(frame_center, source),
                    box=self.frame_box_to_logical(frame_box, source),
                    template=path,
                    scale=scale,
                )
                if best is None or match.score > best.score:
                    best = match
                    best_frame_box = frame_box
                    best_frame_center = frame_center
                    best_template_size = (tw, th)

        passed = best is not None and best.score >= float(threshold)
        score = float(best.score) if best is not None else -1.0
        scale = float(best.scale) if best is not None else 0.0
        best_box = str(best.box) if best is not None else "NONE"
        best_center = str(best.center) if best is not None else "NONE"
        template_name = best.template.name if best is not None else "NONE"
        if trace:
            self._detail(
                f"Match [{name}] | Context: clean-main | Score: {score:.4f} | "
            f"Threshold: {float(threshold):.4f} | LogicalZone: {zone or 'FULL'} | "
            f"FrameROI: {frame_roi} | Frame: {width}x{height} | "
            f"FrameScale: ({frame_sx:.4f},{frame_sy:.4f}) | "
            f"BestBoxLogical: {best_box} | BestCenterLogical: {best_center} | "
            f"BestBoxFrame: {best_frame_box or 'NONE'} | "
            f"BestCenterFrame: {best_frame_center or 'NONE'} | "
            f"TemplateFrameSize: {best_template_size or 'NONE'} | "
            f"Scale: {scale:.2f} | Template: {template_name} | "
                f"{'PASS' if passed else 'FAIL'}"
            )
        if not passed:
            return None
        if click:
            # ``best.center`` is logical. Driver owns the final logical->client
            # input conversion exactly once.
            self.driver.click(*best.center)
        return best

    def find_any(
        self,
        names: Iterable[str],
        *,
        threshold: float = 0.80,
        zone: tuple[int, int, int, int] | None = None,
        scales: Iterable[float] = (1.0,),
        click: bool = False,
    ) -> Match | None:
        frame = self.frame()
        best = None
        for name in names:
            match = self.find(
                name,
                threshold=threshold,
                zone=zone,
                scales=scales,
                click=False,
                frame=frame,
            )
            if match is not None and (best is None or match.score > best.score):
                best = match
        if best is not None and click:
            self.driver.click(*best.center)
        return best
