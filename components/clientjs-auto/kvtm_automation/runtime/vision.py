from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

__all__ = ["Match", "VisionEngine"]
FILE_FUNCTIONS = (
    "Chụp frame ClientJS qua driver",
    "Nạp và cache template",
    "So khớp một template với score/threshold",
    "So khớp nhóm template trên cùng một frame",
    "Ghi trace nhận diện PASS hoặc FAIL",
)

from .assets import AssetLibrary


@dataclass(frozen=True)
class Match:
    name: str
    score: float
    center: tuple[int, int]
    box: tuple[int, int, int, int]
    template: Path
    scale: float


class VisionEngine:
    """Small deterministic template matcher shared by every clean workflow."""

    def __init__(
        self,
        driver: Any,
        assets: AssetLibrary,
        *,
        detail_logger: Callable[[str], None] | None = None,
    ) -> None:
        self.driver = driver
        self.assets = assets
        self.detail_logger = detail_logger
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

    def find(
        self,
        name: str,
        *,
        threshold: float = 0.80,
        zone: tuple[int, int, int, int] | None = None,
        scales: Iterable[float] = (1.0,),
        click: bool = False,
        frame=None,
    ) -> Match | None:
        import cv2

        source = self.frame() if frame is None else frame
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
            return None

        best: Match | None = None
        for path in self.assets.candidates(name):
            template = self._template(path)
            if template is None:
                continue
            for scale in scales:
                scale = float(scale)
                tw = max(2, int(round(template.shape[1] * scale)))
                th = max(2, int(round(template.shape[0] * scale)))
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
                _minimum, maximum, _min_loc, max_loc = cv2.minMaxLoc(result)
                score = float(maximum)
                left, top = x0 + int(max_loc[0]), y0 + int(max_loc[1])
                match = Match(
                    name=str(name),
                    score=score,
                    center=(left + tw // 2, top + th // 2),
                    box=(left, top, tw, th),
                    template=path,
                    scale=scale,
                )
                if best is None or match.score > best.score:
                    best = match
        passed = best is not None and best.score >= float(threshold)
        score = float(best.score) if best is not None else -1.0
        scale = float(best.scale) if best is not None else 0.0
        self._detail(
            f"Match [{name}] | Context: clean-main | Score: {score:.4f} | "
            f"Threshold: {float(threshold):.4f} | Zone: {zone or 'FULL'} | "
            f"Scale: {scale:.2f} | {'PASS' if passed else 'FAIL'}"
        )
        if not passed:
            return None
        if click:
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
