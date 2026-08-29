from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import time
from typing import Any, Protocol


SCHEMA_VERSION = 1
LOGICAL_SIZE = (1000, 1000)
STEP_TYPES = {
    "click", "swipe_path", "wait", "wait_image", "click_image",
    "swipe_from_image", "log", "if_image", "repeat", "retry",
    "until_image", "call", "fail",
}


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


def _region(value: Any) -> tuple[int, int, int, int] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise FunctionValidationError("region phai gom [x, y, width, height]")
    x, y, width, height = (int(item) for item in value)
    if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1000 or y + height > 1000:
        raise FunctionValidationError(f"region ngoai vung 1000x1000: {value}")
    return x, y, width, height


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
        elif self.type == "swipe_from_image":
            self._validate_image_condition()
            points = self.data.get("points")
            if not isinstance(points, list) or not points:
                raise FunctionValidationError("swipe_from_image thieu diem dich")
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
        elif self.type == "log":
            if not isinstance(self.data.get("message"), str):
                raise FunctionValidationError("log thieu message")
        elif self.type == "if_image":
            self._validate_image_condition()
            self._validate_nested("then_steps")
            self._validate_nested("else_steps")
        elif self.type == "repeat":
            count = int(self.data.get("count", 0))
            if not 1 <= count <= 10000:
                raise FunctionValidationError("repeat count phai tu 1 den 10000")
            self._validate_nested("steps", required=True)
        elif self.type == "retry":
            attempts = int(self.data.get("attempts", 0))
            if not 1 <= attempts <= 100:
                raise FunctionValidationError("retry attempts phai tu 1 den 100")
            delay = float(self.data.get("delay_seconds", 0))
            if not 0 <= delay <= 3600:
                raise FunctionValidationError("retry delay_seconds khong hop le")
            self._validate_nested("steps", required=True)
            self._validate_nested("on_exhausted")
        elif self.type == "until_image":
            self._validate_image_condition()
            attempts = int(self.data.get("attempts", 0))
            if not 1 <= attempts <= 100:
                raise FunctionValidationError("until_image attempts phai tu 1 den 100")
            self._validate_nested("steps", required=True)
            self._validate_nested("on_exhausted")
        elif self.type == "call":
            name = self.data.get("procedure")
            if not isinstance(name, str) or not name.strip():
                raise FunctionValidationError("call thieu procedure")
        elif self.type == "fail":
            if not isinstance(self.data.get("message"), str):
                raise FunctionValidationError("fail thieu message")

    def _validate_image_condition(self) -> None:
        asset = self.data.get("asset")
        if not isinstance(asset, str) or not asset.strip():
            raise FunctionValidationError("if_image thieu asset")
        confidence = float(self.data.get("confidence", 0.85))
        if not 0 < confidence <= 1:
            raise FunctionValidationError("confidence phai nam trong (0, 1]")
        timeout = float(self.data.get("timeout", 0))
        if not 0 <= timeout <= 3600:
            raise FunctionValidationError("timeout khong hop le")
        _region(self.data.get("region"))

    def _validate_nested(self, key: str, required: bool = False) -> None:
        raw = self.data.get(key, [])
        if not isinstance(raw, list) or (required and not raw):
            raise FunctionValidationError(f"{key} phai la danh sach step")
        self.data[key] = [Step.from_dict(item).to_dict() for item in raw]

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, **self.data}


@dataclass
class AutoFunction:
    name: str
    steps: list[Step]
    description: str = ""
    schema_version: int = SCHEMA_VERSION
    logical_size: tuple[int, int] = LOGICAL_SIZE
    procedures: dict[str, list[Step]] = field(default_factory=dict)

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
        raw_procedures = value.get("procedures", {})
        if not isinstance(raw_procedures, dict):
            raise FunctionValidationError("procedures phai la object")
        procedures = {}
        for procedure_name, procedure_steps in raw_procedures.items():
            if not isinstance(procedure_name, str) or not isinstance(procedure_steps, list):
                raise FunctionValidationError("procedure khong hop le")
            procedures[procedure_name] = [Step.from_dict(item) for item in procedure_steps]
        function = cls(
            name=name.strip(),
            description=str(value.get("description", "")),
            steps=[Step.from_dict(item) for item in raw_steps],
            schema_version=version,
            procedures=procedures,
        )
        function._validate_calls()
        return function

    def _validate_calls(self) -> None:
        def walk(steps):
            for step in steps:
                if step.type == "call" and step.data["procedure"] not in self.procedures:
                    raise FunctionValidationError(f"Khong co procedure: {step.data['procedure']}")
                for key in ("steps", "then_steps", "else_steps", "on_exhausted"):
                    if key in step.data:
                        walk([Step.from_dict(item) for item in step.data[key]])
        walk(self.steps)
        for procedure_steps in self.procedures.values():
            walk(procedure_steps)

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
            "procedures": {
                name: [step.to_dict() for step in steps]
                for name, steps in self.procedures.items()
            },
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
    def find_image(self, asset: Path, confidence: float, region=None) -> tuple[float, float] | None: ...


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
        self._event_index = 0
        self._procedures = function.procedures
        self._call_stack: list[str] = []
        events: list[ExecutionEvent] = []
        self._execute_steps(function.steps, events)
        return events

    def _execute_steps(self, steps: list[Step], events: list[ExecutionEvent]) -> None:
        for step in steps:
            index = self._event_index
            self._event_index += 1
            if self._stopped:
                events.append(ExecutionEvent(index, step.type, "stopped"))
                return
            try:
                detail = self._execute(step, events)
                events.append(ExecutionEvent(index, step.type, "ok"))
                if detail:
                    events[-1].detail = detail
            except Exception as exc:
                events.append(ExecutionEvent(index, step.type, "error", str(exc)))
                raise

    def _find_image(self, relative: str, confidence: float, timeout: float, region=None):
        asset = self._asset(relative)
        deadline = time.monotonic() + timeout
        while not self._stopped:
            found = self.engine.find_image(asset, confidence, _region(region))
            if found is not None or time.monotonic() >= deadline:
                return found
            self.sleep(0.10)
        return None

    def _nested(self, raw: list[dict[str, Any]]) -> list[Step]:
        return [Step.from_dict(item) for item in raw]

    def _execute(self, step: Step, events: list[ExecutionEvent]) -> str:
        data = step.data
        if step.type == "click":
            self.engine.click(*_point(data["point"]))
        elif step.type == "swipe_path":
            points = [_point(item) for item in data["points"]]
            self.engine.swipe_points(points, float(data["duration"]))
        elif step.type == "swipe_from_image":
            found = self._find_image(
                data["asset"], float(data.get("confidence", 0.85)),
                float(data.get("timeout", 10)), data.get("region"),
            )
            if found is None:
                raise TimeoutError(f"Khong tim thay anh: {data['asset']}")
            points = [found] + [_point(item) for item in data["points"]]
            self.engine.swipe_points(points, float(data["duration"]))
        elif step.type == "wait":
            self.sleep(float(data["seconds"]))
        elif step.type in {"wait_image", "click_image"}:
            confidence = float(data.get("confidence", 0.85))
            timeout = float(data.get("timeout", 10))
            found = self._find_image(data["asset"], confidence, timeout, data.get("region"))
            if found is None:
                raise TimeoutError(f"Khong tim thay anh: {data['asset']}")
            if step.type == "click_image":
                self.engine.click(*found)
        elif step.type == "log":
            return str(data["message"])
        elif step.type == "if_image":
            found = self._find_image(
                data["asset"], float(data.get("confidence", 0.85)),
                float(data.get("timeout", 0)), data.get("region"),
            )
            branch = "then_steps" if found is not None else "else_steps"
            self._execute_steps(self._nested(data.get(branch, [])), events)
            return "found" if found is not None else "not_found"
        elif step.type == "repeat":
            count = int(data["count"])
            for current in range(count):
                if self._stopped:
                    break
                self._execute_steps(self._nested(data["steps"]), events)
            return f"{count} lan"
        elif step.type == "retry":
            attempts = int(data["attempts"])
            last_error: Exception | None = None
            for current in range(1, attempts + 1):
                try:
                    self._execute_steps(self._nested(data["steps"]), events)
                    return f"thanh cong lan {current}/{attempts}"
                except Exception as exc:
                    last_error = exc
                    if current < attempts:
                        self.sleep(float(data.get("delay_seconds", 0)))
            self._execute_steps(self._nested(data.get("on_exhausted", [])), events)
            if bool(data.get("continue_after_exhausted", False)):
                return f"that bai sau {attempts} lan: {last_error}"
            raise RuntimeError(f"Retry that bai sau {attempts} lan: {last_error}")
        elif step.type == "until_image":
            attempts = int(data["attempts"])
            for current in range(1, attempts + 1):
                found = self._find_image(
                    data["asset"], float(data.get("confidence", 0.85)),
                    float(data.get("timeout", 0)), data.get("region"),
                )
                if found is not None:
                    return f"found lan {current}/{attempts}"
                self._execute_steps(self._nested(data["steps"]), events)
            found = self._find_image(
                data["asset"], float(data.get("confidence", 0.85)), 0,
                data.get("region"),
            )
            if found is not None:
                return f"found sau {attempts} lan"
            self._execute_steps(self._nested(data.get("on_exhausted", [])), events)
            raise TimeoutError(f"Khong dat trang thai anh: {data['asset']}")
        elif step.type == "call":
            name = data["procedure"]
            if name in self._call_stack:
                raise RuntimeError(f"Procedure goi de quy: {name}")
            if name not in self._procedures:
                raise FunctionValidationError(f"Khong co procedure: {name}")
            self._call_stack.append(name)
            try:
                self._execute_steps(self._procedures[name], events)
            finally:
                self._call_stack.pop()
            return name
        elif step.type == "fail":
            raise RuntimeError(str(data["message"]))
        return ""


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
