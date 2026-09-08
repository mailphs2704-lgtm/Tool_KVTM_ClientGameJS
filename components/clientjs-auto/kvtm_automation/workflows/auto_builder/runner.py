from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...automation import KVAutomation
from ...errors import ScreenTimeout
from .catalog import get_function_spec
from .image_match import match_custom_template
from .modules import (
    EnterGamePopupModule,
    FunctionModule,
    MachineRepairTestModule,
    SellFunctionVpModule,
)


__all__ = ["AutoBuilderResult", "AutoBuilderRunner", "validate_plan"]
FILE_FUNCTIONS = (
    "Validate plan AUTO Builder và thư viện Function trước khi chạy",
    "Chạy module vào game/đóng popup theo đúng vị trí trong plan",
    "Chạy module bán VP độc lập theo Function",
    "Chạy Function có sẵn theo vòng lặp và callback sale rõ ràng",
    "Chạy Function tự tạo lồng nhau theo đúng block operator lưu",
    "Chạy riêng TEST Sửa máy từ panel sản xuất VP đang mở",
    "Chạy block nhận diện ảnh người dùng",
    "Validate và chạy Swipe nhiều điểm bằng native swipe_points/BATCH_SWIPE",
    "Chạy click/wait theo thứ tự người dùng sắp",
    "Fail-close khi block/tham số/function graph không hợp lệ",
)

_SUPPORTED_STEP_TYPES = {
    "enter_game_popup",
    "sell_function_vp",
    "function",
    "call_saved_function",
    "machine_repair_test",
    "recognize_image",
    "click",
    "swipe",
    "wait",
    "finish_pass",
    "finish_fail",
}


@dataclass(frozen=True)
class AutoBuilderResult:
    profile_id: str
    plan_name: str
    completed_steps: int
    total_steps: int
    function_loops: dict[str, int]
    sale_calls: dict[str, int]
    outcome: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "plan_name": self.plan_name,
            "completed_steps": self.completed_steps,
            "total_steps": self.total_steps,
            "function_loops": dict(self.function_loops),
            "sale_calls": dict(self.sale_calls),
            "outcome": self.outcome,
        }


def _normalize_swipe_points(step: dict[str, Any], *, scope: str, step_id: str) -> list[list[int]]:
    raw = step.get("points")
    if raw in (None, "", []):
        raw = [
            [step.get("x1", -1), step.get("y1", -1)],
            [step.get("x2", -1), step.get("y2", -1)],
        ]
    if not isinstance(raw, (list, tuple)) or len(raw) < 2:
        raise ValueError(f"{scope}/{step_id}: Swipe phải có ít nhất 2 điểm")
    points: list[list[int]] = []
    for point_index, item in enumerate(raw, start=1):
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError(
                f"{scope}/{step_id}: điểm Swipe {point_index} phải có đúng x,y"
            )
        try:
            x, y = int(item[0]), int(item[1])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{scope}/{step_id}: điểm Swipe {point_index} không phải số"
            ) from exc
        if not (0 <= x <= 1000 and 0 <= y <= 1000):
            raise ValueError(
                f"{scope}/{step_id}: điểm Swipe ngoài vùng 0..1000: {(x, y)}"
            )
        points.append([x, y])
    if all(points[index] == points[index - 1] for index in range(1, len(points))):
        raise ValueError(f"{scope}/{step_id}: đường Swipe không có chuyển động")
    return points


def _normalize_steps(
    raw_steps: Any,
    *,
    scope: str,
    saved_function_ids: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(raw_steps, list):
        raise ValueError(f"{scope}: steps phải là list")
    steps: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_steps, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"{scope}: bước {index} không phải object")
        step = dict(raw)
        step_type = str(step.get("type") or "").strip()
        if step_type not in _SUPPORTED_STEP_TYPES:
            raise ValueError(f"{scope}: bước {index} có type chưa hỗ trợ: {step_type!r}")
        step_id = str(step.get("id") or f"step-{index}").strip()
        if not step_id or step_id in seen_ids:
            raise ValueError(f"{scope}: trùng/rỗng id bước Builder: {step_id!r}")
        seen_ids.add(step_id)
        step["id"] = step_id
        step["type"] = step_type
        if step_type in {"sell_function_vp", "function"}:
            get_function_spec(str(step.get("function_id") or "function_1"))
        if step_type in {"function", "call_saved_function"}:
            loops = int(step.get("loops", 1) or 1)
            if loops < 1 or loops > 999:
                raise ValueError(f"{scope}/{step_id}: loops phải trong 1..999")
            step["loops"] = loops
            step["sale_after_each_loop"] = bool(step.get("sale_after_each_loop", False))
        if step_type == "call_saved_function":
            function_id = str(step.get("function_id") or "").strip()
            if not function_id or function_id not in saved_function_ids:
                raise ValueError(
                    f"{scope}/{step_id}: Function tự tạo không tồn tại: {function_id!r}"
                )
            step["function_id"] = function_id
            sale_function_id = str(step.get("sale_function_id") or "function_1")
            if step["sale_after_each_loop"]:
                get_function_spec(sale_function_id)
            step["sale_function_id"] = sale_function_id
        if step_type == "swipe":
            points = _normalize_swipe_points(step, scope=scope, step_id=step_id)
            duration = float(step.get("duration", 0.35))
            if duration <= 0 or duration > 10.0:
                raise ValueError(
                    f"{scope}/{step_id}: thời lượng Swipe ngoài 0..10s: {duration}"
                )
            step["points"] = points
            step["x1"], step["y1"] = points[0]
            step["x2"], step["y2"] = points[-1]
            step["duration"] = duration
        steps.append(step)
    return steps


def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, dict):
        raise ValueError("AUTO Builder plan phải là object")
    version = int(plan.get("version", 1) or 1)
    if version != 1:
        raise ValueError(f"AUTO Builder chưa hỗ trợ plan version={version}")
    name = str(plan.get("name") or "AUTO tự tạo").strip() or "AUTO tự tạo"

    raw_functions = plan.get("saved_functions") or {}
    if not isinstance(raw_functions, dict):
        raise ValueError("saved_functions phải là object")
    saved_function_ids = {str(key) for key in raw_functions}
    saved_functions: dict[str, dict[str, Any]] = {}
    for function_id, raw_function in raw_functions.items():
        if not isinstance(raw_function, dict):
            raise ValueError(f"Function {function_id}: document không hợp lệ")
        embedded_id = str(raw_function.get("function_id") or function_id).strip()
        if embedded_id != str(function_id):
            raise ValueError(
                f"Function key/id không khớp: {function_id!r} != {embedded_id!r}"
            )
        function_name = str(raw_function.get("name") or embedded_id).strip() or embedded_id
        saved_functions[embedded_id] = {
            "version": 1,
            "kind": "function",
            "function_id": embedded_id,
            "name": function_name,
            "steps": _normalize_steps(
                raw_function.get("steps"),
                scope=f"Function {function_name}",
                saved_function_ids=saved_function_ids,
            ),
        }

    steps = _normalize_steps(
        plan.get("steps"), scope=f"Plan {name}", saved_function_ids=saved_function_ids
    )
    if not steps:
        raise ValueError("AUTO Builder cần ít nhất một bước")

    graph = {
        function_id: {
            str(step.get("function_id"))
            for step in function["steps"]
            if step["type"] == "call_saved_function"
        }
        for function_id, function in saved_functions.items()
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(function_id: str) -> None:
        if function_id in visited:
            return
        if function_id in visiting:
            raise ValueError(f"Function tự tạo bị vòng gọi đệ quy: {function_id}")
        visiting.add(function_id)
        for dependency in graph.get(function_id, set()):
            visit(dependency)
        visiting.remove(function_id)
        visited.add(function_id)

    for function_id in graph:
        visit(function_id)

    return {
        "version": 1,
        "kind": "plan",
        "name": name,
        "steps": steps,
        "saved_functions": saved_functions,
    }


class AutoBuilderRunner:
    """Execute exactly the operator-visible Builder plan/function graph."""

    def __init__(self, automation: KVAutomation, plan: dict[str, Any]) -> None:
        self.auto = automation
        self.context = automation.context
        self.plan = validate_plan(plan)
        self.saved_functions = self.plan["saved_functions"]
        self.enter_game = EnterGamePopupModule(automation)
        self.sale = SellFunctionVpModule(automation)
        self.function = FunctionModule(automation)
        self.machine_repair_test = MachineRepairTestModule(automation)
        self.function_loops: dict[str, int] = {}
        self.sale_calls: dict[str, int] = {}

    @staticmethod
    def _zone(step: dict[str, Any]) -> tuple[int, int, int, int] | None:
        raw = step.get("zone")
        if raw in (None, "", []):
            return None
        if not isinstance(raw, (list, tuple)) or len(raw) != 4:
            raise ValueError(f"Zone Builder không hợp lệ: {raw!r}")
        zone = tuple(map(int, raw))
        x, y, w, h = zone
        if x < 0 or y < 0 or w <= 0 or h <= 0 or x > 1000 or y > 1000:
            raise ValueError(f"Zone Builder ngoài vùng hợp lệ: {zone!r}")
        return zone

    def _run_saved_function(self, step: dict[str, Any], call_stack: tuple[str, ...]) -> None:
        function_id = str(step["function_id"])
        function = self.saved_functions[function_id]
        loops = int(step.get("loops", 1))
        for loop_index in range(1, loops + 1):
            self.context.ensure_running()
            self.context.log(
                f"AUTO Builder • Function tự tạo {function['name']} • "
                f"vòng {loop_index}/{loops} START"
            )
            self._run_sequence(
                function["steps"],
                scope=f"Function {function['name']}",
                call_stack=call_stack + (function_id,),
                terminal_is_local=True,
            )
            self.function_loops[function_id] = self.function_loops.get(function_id, 0) + 1
            if bool(step.get("sale_after_each_loop", False)):
                sale_function_id = str(step.get("sale_function_id") or "function_1")
                self.context.log(
                    f"AUTO Builder • {function['name']} vòng {loop_index}/{loops} xong • "
                    f"gọi module Bán VP {sale_function_id}"
                )
                self.sale.run(
                    function_id=sale_function_id,
                    timeout=float(step.get("sale_timeout", 120.0)),
                )
                self.sale_calls[sale_function_id] = self.sale_calls.get(sale_function_id, 0) + 1

    def _run_action(self, step: dict[str, Any], call_stack: tuple[str, ...]) -> str | None:
        step_type = step["type"]
        if step_type == "enter_game_popup":
            self.enter_game.run(timeout=float(step.get("timeout", 180.0)))
        elif step_type == "sell_function_vp":
            function_id = str(step.get("function_id") or "function_1")
            self.sale.run(function_id=function_id, timeout=float(step.get("timeout", 120.0)))
            self.sale_calls[function_id] = self.sale_calls.get(function_id, 0) + 1
        elif step_type == "function":
            function_id = str(step.get("function_id") or "function_1")
            loops = int(step.get("loops", 1))
            for loop_index in range(1, loops + 1):
                self.context.ensure_running()
                self.context.log(
                    f"AUTO Builder • {function_id} • vòng {loop_index}/{loops} START"
                )
                self.function.run(function_id=function_id)
                self.function_loops[function_id] = self.function_loops.get(function_id, 0) + 1
                if bool(step.get("sale_after_each_loop", False)):
                    self.context.log(
                        f"AUTO Builder • {function_id} vòng {loop_index}/{loops} xong • "
                        "gọi module Bán VP theo Function"
                    )
                    self.sale.run(
                        function_id=function_id,
                        timeout=float(step.get("sale_timeout", 120.0)),
                    )
                    self.sale_calls[function_id] = self.sale_calls.get(function_id, 0) + 1
        elif step_type == "call_saved_function":
            function_id = str(step["function_id"])
            if function_id in call_stack:
                raise RuntimeError(f"Function recursion runtime bị chặn: {function_id}")
            self._run_saved_function(step, call_stack)
        elif step_type == "machine_repair_test":
            self.machine_repair_test.run()
        elif step_type == "recognize_image":
            raw_template = str(step.get("template_path") or "").strip()
            if not raw_template:
                raise ValueError("Bước nhận diện thiếu template_path")
            template = Path(raw_template).expanduser()
            match = match_custom_template(
                self.auto,
                template,
                threshold=float(step.get("threshold", 0.80)),
                zone=self._zone(step),
                scales=tuple(step.get("scales") or (1.0,)),
            )
            if match is None and str(step.get("on_fail") or "stop") != "continue":
                raise ScreenTimeout(f"AUTO Builder không nhận diện được: {template.name}")
        elif step_type == "click":
            x, y = int(step.get("x", -1)), int(step.get("y", -1))
            if not (0 <= x <= 1000 and 0 <= y <= 1000):
                raise ValueError(f"Click Builder ngoài vùng 0..1000: {(x, y)}")
            self.auto.driver.click(x, y)
        elif step_type == "swipe":
            points = [tuple(map(int, point)) for point in step["points"]]
            duration = float(
                step.get("duration", self.auto.speed_config.floor_swipe_duration)
            )
            self.context.log(
                f"AUTO Builder • Swipe nhiều điểm • points={len(points)} • "
                f"segments={len(points) - 1} • duration={duration:.3f}s"
            )
            self.auto.driver.swipe_points(points, duration=duration)
        elif step_type == "wait":
            seconds = float(step.get("seconds", 0.5))
            if seconds < 0 or seconds > 300:
                raise ValueError(f"Wait Builder ngoài 0..300s: {seconds}")
            self.auto.wait.sleep(seconds)
        elif step_type == "finish_pass":
            return "pass"
        elif step_type == "finish_fail":
            raise RuntimeError(str(step.get("message") or "AUTO Builder kết thúc FAIL"))
        else:
            raise ValueError(f"Block Builder chưa hỗ trợ: {step_type}")
        return None

    def _run_sequence(
        self,
        steps: list[dict[str, Any]],
        *,
        scope: str,
        call_stack: tuple[str, ...],
        terminal_is_local: bool,
    ) -> tuple[int, str | None]:
        completed = 0
        terminal = None
        for index, step in enumerate(steps, start=1):
            self.context.ensure_running()
            self.context.stage(f"auto-builder-{scope}-{index}-{step['type']}")
            self.context.log(
                f"AUTO Builder • {scope} • bước {index}/{len(steps)} • {step['type']}"
            )
            terminal = self._run_action(step, call_stack)
            completed = index
            if terminal == "pass":
                if terminal_is_local:
                    self.context.log(f"AUTO Builder • {scope} • Kết thúc PASS cục bộ")
                break
        return completed, terminal

    def run(self) -> AutoBuilderResult:
        steps = self.plan["steps"]
        self.context.stage("auto-builder-start")
        self.context.log(
            f"AUTO Builder START • plan={self.plan['name']} • {len(steps)} bước • "
            f"saved_functions={len(self.saved_functions)}"
        )
        completed, terminal = self._run_sequence(
            steps,
            scope="plan-main",
            call_stack=(),
            terminal_is_local=False,
        )
        outcome = "pass" if terminal == "pass" else "completed"
        self.context.stage("auto-builder-finished")
        self.context.log(
            f"AUTO Builder FINISHED • plan={self.plan['name']} • {completed}/{len(steps)} bước"
        )
        return AutoBuilderResult(
            profile_id=self.context.profile_id,
            plan_name=self.plan["name"],
            completed_steps=completed,
            total_steps=len(steps),
            function_loops=self.function_loops,
            sale_calls=self.sale_calls,
            outcome=outcome,
        )
