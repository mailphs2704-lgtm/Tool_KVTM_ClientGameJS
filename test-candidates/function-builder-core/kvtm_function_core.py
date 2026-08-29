from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import time
from typing import Any, Protocol


SCHEMA_VERSION = 1
LOGICAL_SIZE = (1000, 1000)
STEP_TYPES = {"click", "swipe_path", "wait", "wait_image", "click_image"}


class FunctionValidationError(ValueError):
    pass


def _point(value: Any, label: str = "point") -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise FunctionValidationError(f"{label} phai gom [x, y]")
    try:
        x, y = float(value[0]), float(value[1])
    except (TypeError, ValueError) as exc:
        raise FunctionValidationError(f"{label} khong phai toa do") from exc
    if not (0 <= x <= 1000 and 0 <= y <= 1000):
        raise FunctionValidationError(f"{label} ngoai vung 1000x1000: {(x, y)}")
    return x, y


@dataclass
class Step:
    type: str
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Step":
        if not isinstance(value, dict):
            raise FunctionValidationError("Moi step phai la object")
        step_type = str(value.get("type", ""))
        if step_type not in STEP_TYPES:
            raise FunctionValidationError(f"Step type khong ho tro: {step_type}")
        data = {key: item for key, item in value.items() if key != "type"}
        step = cls(step_type, data)
        step.validate()
        return step

    def validate(self) -> None:
        if self.type == "click":
            _point(self.data.get("point"))
        elif self.type == "swipe_path":
            points = self.data.get("points")
            if not isinstance(points, list) or len(points) < 2:
                raise FunctionValidationError("swipe_path can it nhat hai diem")
            for index, point in enumerate(points):
                _point(point, f"points[{index}]")
            duration = float(self.data.get("duration", 0))
            if not 0.05 <= duration <= 60:
                raise FunctionValidationError("duration phai tu 0.05 den 60 giay")
        elif self.type == "wait":
            seconds = float(self.data.get("seconds", 0))
            if not 0 <= seconds <= 3600:
                raise FunctionValidationError("wait seconds khong hop le")
        elif self.type in {"wait_image", "click_image"}:
            asset = self.data.get("asset")
            if not isinstance(asset, str) or not asset.strip():
                raise FunctionValidationError("image step thieu asset")
            confidence = float(self.data.get("confidence", 0.85))
            if not 0 < confidence <= 1:
                raise FunctionValidationError("confidence phai nam trong (0, 1]")
            timeout = float(self.data.get("timeout", 10))
            if not 0 <= timeout <= 3600:
                raise FunctionValidationError("timeout khong hop le")

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, **self.data}


@dataclass
class AutoFunction:
    name: str
    steps: list[Step]
    description: str = ""
    schema_version: int = SCHEMA_VERSION
    logical_size: tuple[int, int] = LOGICAL_SIZE

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AutoFunction":
        if not isinstance(value, dict):
            raise FunctionValidationError("Function phai la object")
        version = int(value.get("schema_version", SCHEMA_VERSION))
        if version != SCHEMA_VERSION:
            raise FunctionValidationError(f"Schema version khong ho tro: {version}")
        name = value.get("name")
        if not isinstance(name, str) or not name.strip():
            raise FunctionValidationError("Function thieu name")
        logical = tuple(value.get("logical_size", LOGICAL_SIZE))
        if logical != LOGICAL_SIZE:
            raise FunctionValidationError("logical_size bat buoc la [1000, 1000]")
        raw_steps = value.get("steps")
        if not isinstance(raw_steps, list):
            raise FunctionValidationError("steps phai la danh sach")
        return cls(
            name=name.strip(),
            description=str(value.get("description", "")),
            steps=[Step.from_dict(item) for item in raw_steps],
            schema_version=version,
        )

    @classmethod
    def load(cls, path: Path) -> "AutoFunction":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8-sig")))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "description": self.description,
            "logical_size": list(self.logical_size),
            "steps": [step.to_dict() for step in self.steps],
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


class Engine(Protocol):
    def click(self, x: float, y: float) -> None: ...
    def swipe_points(self, points: list[tuple[float, float]], duration: float) -> None: ...
    def find_image(self, asset: Path, confidence: float) -> tuple[float, float] | None: ...


@dataclass
class ExecutionEvent:
    index: int
    step_type: str
    status: str
    detail: str = ""


class FunctionRuntime:
    def __init__(self, engine: Engine, asset_root: Path, sleep=time.sleep) -> None:
        self.engine = engine
        self.asset_root = asset_root.resolve()
        self.sleep = sleep
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    def _asset(self, relative: str) -> Path:
        candidate = (self.asset_root / relative).resolve()
        try:
            candidate.relative_to(self.asset_root)
        except ValueError as exc:
            raise FunctionValidationError("Asset nam ngoai thu vien") from exc
        if not candidate.is_file():
            raise FileNotFoundError(f"Khong tim thay asset: {relative}")
        return candidate

    def run(self, function: AutoFunction) -> list[ExecutionEvent]:
        self._stopped = False
        events: list[ExecutionEvent] = []
        for index, step in enumerate(function.steps):
            if self._stopped:
                events.append(ExecutionEvent(index, step.type, "stopped"))
                break
            try:
                self._execute(step)
                events.append(ExecutionEvent(index, step.type, "ok"))
            except Exception as exc:
                events.append(ExecutionEvent(index, step.type, "error", str(exc)))
                raise
        return events

    def _execute(self, step: Step) -> None:
        data = step.data
        if step.type == "click":
            self.engine.click(*_point(data["point"]))
        elif step.type == "swipe_path":
            points = [_point(item) for item in data["points"]]
            self.engine.swipe_points(points, float(data["duration"]))
        elif step.type == "wait":
            self.sleep(float(data["seconds"]))
        elif step.type in {"wait_image", "click_image"}:
            asset = self._asset(data["asset"])
            confidence = float(data.get("confidence", 0.85))
            timeout = float(data.get("timeout", 10))
            deadline = time.monotonic() + timeout
            found = None
            while not self._stopped:
                found = self.engine.find_image(asset, confidence)
                if found is not None or time.monotonic() >= deadline:
                    break
                self.sleep(0.10)
            if found is None:
                raise TimeoutError(f"Khong tim thay anh: {data['asset']}")
            if step.type == "click_image":
                self.engine.click(*found)


class FunctionRecorder:
    def __init__(self, name: str = "Chuc nang moi") -> None:
        self.function = AutoFunction(name=name, steps=[])
        self._swipe: list[tuple[float, float]] | None = None
        self._swipe_started = 0.0

    def click(self, x: float, y: float) -> None:
        point = _point([x, y])
        self.function.steps.append(Step("click", {"point": list(point)}))

    def swipe_start(self, x: float, y: float, now: float | None = None) -> None:
        self._swipe = [_point([x, y])]
        self._swipe_started = time.monotonic() if now is None else float(now)

    def swipe_move(self, x: float, y: float, minimum_distance: float = 4) -> None:
        if self._swipe is None:
            raise RuntimeError("Swipe chua bat dau")
        point = _point([x, y])
        previous = self._swipe[-1]
        if (point[0] - previous[0]) ** 2 + (point[1] - previous[1]) ** 2 >= minimum_distance ** 2:
            self._swipe.append(point)

    def swipe_end(self, x: float, y: float, now: float | None = None) -> None:
        if self._swipe is None:
            raise RuntimeError("Swipe chua bat dau")
        point = _point([x, y])
        if point != self._swipe[-1]:
            self._swipe.append(point)
        ended = time.monotonic() if now is None else float(now)
        duration = max(0.05, ended - self._swipe_started)
        points = [list(item) for item in self._simplify(self._swipe)]
        self.function.steps.append(
            Step("swipe_path", {"points": points, "duration": round(duration, 3)})
        )
        self._swipe = None

    def add_wait(self, seconds: float) -> None:
        step = Step("wait", {"seconds": float(seconds)})
        step.validate()
        self.function.steps.append(step)

    @staticmethod
    def _simplify(points: list[tuple[float, float]], tolerance: float = 2.0) -> list[tuple[float, float]]:
        if len(points) <= 2:
            return points

        def distance(point, start, end):
            if start == end:
                return ((point[0] - start[0]) ** 2 + (point[1] - start[1]) ** 2) ** 0.5
            dx, dy = end[0] - start[0], end[1] - start[1]
            ratio = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / (dx * dx + dy * dy)
            ratio = max(0.0, min(1.0, ratio))
            px, py = start[0] + ratio * dx, start[1] + ratio * dy
            return ((point[0] - px) ** 2 + (point[1] - py) ** 2) ** 0.5

        def reduce(segment):
            if len(segment) <= 2:
                return segment
            start, end = segment[0], segment[-1]
            index, maximum = 0, 0.0
            for current in range(1, len(segment) - 1):
                value = distance(segment[current], start, end)
                if value > maximum:
                    index, maximum = current, value
            if maximum <= tolerance:
                return [start, end]
            left, right = reduce(segment[:index + 1]), reduce(segment[index:])
            return left[:-1] + right

        return reduce(points)
