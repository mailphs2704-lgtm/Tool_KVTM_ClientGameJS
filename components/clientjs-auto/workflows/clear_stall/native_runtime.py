from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
import time
from typing import Callable, Iterable


@dataclass(frozen=True)
class Match:
    name: str
    score: float
    center: tuple[int, int]
    box: tuple[int, int, int, int]


class TemplateMatcher:
    """Small OpenCV matcher used by Dọn quầy without AUTO PRO .pyc modules."""

    def __init__(self, driver, asset_roots: Iterable[Path], logger: Callable[[str], None]):
        self.driver = driver
        self.asset_roots = tuple(Path(root).resolve() for root in asset_roots)
        self.log = logger
        self._cache: dict[str, tuple[Path, object]] = {}

    def _template(self, name: str):
        cached = self._cache.get(name)
        if cached is not None:
            return cached
        import cv2

        filenames = (f"{name}.png", name)
        candidates: list[Path] = []
        for root in self.asset_roots:
            for filename in filenames:
                candidates.extend((
                    root / filename,
                    root / "assets" / "items" / filename,
                    root / "assets" / filename,
                ))
        for path in candidates:
            if not path.is_file():
                continue
            image = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if image is not None and image.size:
                self._cache[name] = (path, image)
                return path, image
        raise FileNotFoundError(f"Không tìm thấy template: {name}")

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

        if frame is None:
            frame = self.driver.screenshot(format="opencv")
        height, width = frame.shape[:2]
        if zone is None:
            x0, y0, zw, zh = 0, 0, width, height
        else:
            x0, y0, zw, zh = map(int, zone)
            x0 = max(0, min(width - 1, x0))
            y0 = max(0, min(height - 1, y0))
            zw = max(1, min(width - x0, zw))
            zh = max(1, min(height - y0, zh))
        roi = frame[y0:y0 + zh, x0:x0 + zw]
        _path, template = self._template(name)

        best: Match | None = None
        for scale in scales:
            tw = max(3, round(template.shape[1] * float(scale)))
            th = max(3, round(template.shape[0] * float(scale)))
            if tw > roi.shape[1] or th > roi.shape[0]:
                continue
            interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
            scaled = cv2.resize(template, (tw, th), interpolation=interpolation)
            result = cv2.matchTemplate(roi, scaled, cv2.TM_CCOEFF_NORMED)
            _mn, mx, _mnloc, mxloc = cv2.minMaxLoc(result)
            score = float(mx)
            center = (x0 + mxloc[0] + tw // 2, y0 + mxloc[1] + th // 2)
            candidate = Match(name, score, center, (x0 + mxloc[0], y0 + mxloc[1], tw, th))
            if best is None or candidate.score > best.score:
                best = candidate

        if best is None or best.score < float(threshold):
            return None
        if click:
            self.driver.click(*best.center)
        return best

    def any(self, names: Iterable[str], *, threshold: float = 0.80, zone=None) -> Match | None:
        for name in names:
            try:
                match = self.find(name, threshold=threshold, zone=zone)
            except FileNotFoundError:
                continue
            if match is not None:
                return match
        return None


class ClearStallNativeRuntime:
    """Pure-Python ClientJS control layer based on recovered AUTO PRO behavior.

    It intentionally does not import automation.pyc, adb_controller.pyc or
    image_processor.pyc. AUTO PRO remains reference material only: templates,
    geometry, gesture direction and workflow order.
    """

    POPUP_SCALES = (0.70, 0.75, 0.80, 0.85, 0.90, 1.0, 1.1, 1.2, 1.3)
    POPUP_ZONE = (520, 130, 460, 430)
    ENTRY_MARKERS = ("friend_off", "icon_home")

    def __init__(
        self,
        pid: int,
        *,
        auto_root: Path,
        stop_event: threading.Event,
        logger: Callable[[str], None],
    ) -> None:
        self.pid = int(pid)
        self.auto_root = Path(auto_root).resolve()
        self.stop_event = stop_event
        self.log = logger
        self._install_library_paths()
        from pc_driver import PCDriver

        self.driver = PCDriver(self.pid, reference_size=(1000, 1000))
        self.matcher = TemplateMatcher(
            self.driver,
            (
                self.auto_root,
                self.auto_root / "assets" / "items",
            ),
            logger,
        )

    def _install_library_paths(self) -> None:
        """Load only third-party libraries shipped with AUTO PRO, never its .pyc logic."""
        import os
        import sys

        internal = self.auto_root / "_internal"
        for path in (
            self.auto_root,
            internal,
            internal / "win32",
            internal / "win32" / "lib",
            internal / "Pythonwin",
            internal / "pywin32_system32",
        ):
            if path.exists() and str(path) not in sys.path:
                sys.path.insert(0, str(path))
        if hasattr(os, "add_dll_directory"):
            for path in (internal, internal / "cv2", internal / "numpy.libs", internal / "pywin32_system32"):
                if path.exists():
                    try:
                        os.add_dll_directory(str(path))
                    except OSError:
                        pass

    def screenshot(self):
        self._ensure_running()
        return self.driver.screenshot(format="opencv")

    def dismiss_popups(self, *, timeout: float = 20.0) -> int:
        """Close entry modals using AUTO PRO templates but pure-Python matching."""
        deadline = time.monotonic() + max(0.0, float(timeout))
        closed = 0
        quiet_since: float | None = None
        while time.monotonic() < deadline:
            self._ensure_running()
            if self.matcher.any(self.ENTRY_MARKERS, threshold=0.72):
                if quiet_since is None:
                    quiet_since = time.monotonic()
                if time.monotonic() - quiet_since >= 1.0:
                    return closed
            else:
                quiet_since = None

            match = None
            try:
                match = self.matcher.find(
                    "x_popup_event",
                    threshold=0.56,
                    zone=self.POPUP_ZONE,
                    scales=self.POPUP_SCALES,
                )
            except FileNotFoundError:
                pass
            if match is not None:
                self.driver.click(*match.center)
                closed += 1
                self.log(f"Đóng popup ClientJS bằng x_popup_event ({match.score:.3f})")
                self._sleep(0.55)
                continue

            # Login/portal states recovered from AUTO PRO naming. These are only
            # attempted when the corresponding image is actually visible.
            acted = False
            for name, click_after in (
                ("tai_khoan", None),
                ("tai_khoan_on", (981, 338)),
                ("icon_game", None),
            ):
                try:
                    found = self.matcher.find(name, threshold=0.76, click=click_after is None)
                except FileNotFoundError:
                    continue
                if found is None:
                    continue
                if click_after is not None:
                    self.driver.click(*click_after)
                self.log(f"ClientJS entry: {name}")
                acted = True
                self._sleep(0.8)
                break
            if not acted:
                self._sleep(0.35)
        return closed

    def wait_main_screen(self, *, timeout: float = 30.0) -> None:
        deadline = time.monotonic() + float(timeout)
        last_log = 0.0
        while time.monotonic() < deadline:
            self._ensure_running()
            if self.matcher.any(self.ENTRY_MARKERS, threshold=0.70):
                self.log("Đã xác nhận màn hình chính bằng runtime Python mới")
                return
            self.dismiss_popups(timeout=1.5)
            now = time.monotonic()
            if now - last_log >= 5.0:
                self.log(f"Đang đưa ClientJS về màn hình chính ({max(0, int(deadline-now))}s)")
                last_log = now
        raise RuntimeError("Không đưa được ClientJS về màn hình chính")

    def find(self, name: str, **kwargs):
        self._ensure_running()
        return self.matcher.find(name, **kwargs)

    def click(self, x: int, y: int) -> None:
        self._ensure_running()
        self.driver.click(int(x), int(y))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.35) -> None:
        self._ensure_running()
        self.driver.swipe(x1, y1, x2, y2, duration=float(duration))

    def press_back(self) -> None:
        self._ensure_running()
        self.driver.press("back")

    def _sleep(self, seconds: float) -> None:
        deadline = time.monotonic() + max(0.0, float(seconds))
        while time.monotonic() < deadline:
            self._ensure_running()
            time.sleep(min(0.05, deadline - time.monotonic()))

    def _ensure_running(self) -> None:
        if self.stop_event.is_set():
            raise InterruptedError("Dọn quầy đã được yêu cầu dừng")
