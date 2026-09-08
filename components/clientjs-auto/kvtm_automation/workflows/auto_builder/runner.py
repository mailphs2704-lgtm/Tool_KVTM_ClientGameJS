from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...automation import KVAutomation
from ...errors import ScreenTimeout
from .catalog import get_function_spec
from .image_match import match_custom_template
from .modules import EnterGamePopupModule, FunctionModule, SellFunctionVpModule


__all__ = ["AutoBuilderResult", "AutoBuilderRunner", "validate_plan"]
FILE_FUNCTIONS = (
    "Validate plan AUTO Builder trước khi chạy",
    "Chạy module vào game/đóng popup theo đúng vị trí trong plan",
    "Chạy module bán VP độc lập theo Function",
    "Chạy Function theo số vòng và gọi lại module bán sau mỗi vòng khi bật",
    "Chạy block nhận diện ảnh người dùng",
    "Chạy click/swipe/wait theo thứ tự người dùng sắp",
    "Fail-close khi block hoặc tham số không hợp lệ",
)

_SUPPORTED_STEP_TYPES = {
    "enter_game_popup",
    "sell_function_vp",
    "function",
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


def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, dict):
        raise ValueError("AUTO Builder plan phải là object")
    version = int(plan.get("version", 1) or 1)
    if version != 1:
        raise ValueError(f"AUTO Builder chưa hỗ trợ plan version={version}")
    name = str(plan.get("name") or "AUTO tự tạo").strip() or "AUTO tự tạo"
    raw_steps = plan.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError("AUTO Builder cần ít nhất một bước")
    steps: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_steps, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"Bước {index} không phải object")
        step = dict(raw)
        step_type = str(step.get("type") or "").strip()
        if step_type not in _SUPPORTED_STEP_TYPES:
            raise ValueError(f"Bước {index} có type chưa hỗ trợ: {step_type!r}")
        step_id = str(step.get("id") or f"step-{index}").strip()
        if not step_id or step_id in seen_ids:
            raise ValueError(f"Trùng/rỗng id bước Builder: {step_id!r}")
        seen_ids.add(step_id)
        step["id"] = step_id
        step["type"] = step_type
        if step_type in {"sell_function_vp", "function"}:
            get_function_spec(str(step.get("function_id") or "function_1"))
        if step_type == "function":
            loops = int(step.get("loops", 1) or 1)
            if loops < 1 or loops > 999:
                raise ValueError(f"Bước {step_id}: loops phải trong 1..999")
            step["loops"] = loops
            step["sale_after_each_loop"] = bool(step.get("sale_after_each_loop", False))
        steps.append(step)
    return {"version": 1, "name": name, "steps": steps}


class AutoBuilderRunner:
    """Execute exactly the block order defined by the operator.

    No business module is implicitly inserted at plan start. In particular,
    ``Vào game + đóng popup`` only runs when an ``enter_game_popup`` block is
    present. Function loop callbacks to sale happen only when the Function block
    explicitly has ``sale_after_each_loop=true``.
    """

    def __init__(self, automation: KVAutomation, plan: dict[str, Any]) -> None:
        self.auto = automation
        self.context = automation.context
        self.plan = validate_plan(plan)
        self.enter_game = EnterGamePopupModule(automation)
        self.sale = SellFunctionVpModule(automation)
        self.function = FunctionModule(automation)
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

    def _run_action(self, step: dict[str, Any]) -> str | None:
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
                    # This is intentionally a real independent module call. If
                    # the completed Function left the camera somewhere that the
                    # sale module cannot prove as main, sale fails closed rather
                    # than inventing a hidden floor route.
                    self.sale.run(
                        function_id=function_id,
                        timeout=float(step.get("sale_timeout", 120.0)),
                    )
                    self.sale_calls[function_id] = self.sale_calls.get(function_id, 0) + 1
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
            values = tuple(int(step.get(key, -1)) for key in ("x1", "y1", "x2", "y2"))
            if any(value < 0 or value > 1000 for value in values):
                raise ValueError(f"Swipe Builder ngoài vùng 0..1000: {values}")
            duration = float(
                step.get("duration", self.auto.speed_config.floor_swipe_duration)
            )
            if duration <= 0 or duration > 10.0:
                raise ValueError(f"Thời lượng Swipe Builder ngoài 0..10s: {duration}")
            self.auto.driver.swipe(*values, duration=duration)
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

    def run(self) -> AutoBuilderResult:
        steps = self.plan["steps"]
        self.context.stage("auto-builder-start")
        self.context.log(
            f"AUTO Builder START • plan={self.plan['name']} • {len(steps)} bước"
        )
        completed = 0
        outcome = "completed"
        for index, step in enumerate(steps, start=1):
            self.context.ensure_running()
            self.context.stage(f"auto-builder-step-{index}-{step['type']}")
            self.context.log(
                f"AUTO Builder • bước {index}/{len(steps)} • {step['type']}"
            )
            terminal = self._run_action(step)
            completed = index
            if terminal == "pass":
                outcome = "pass"
                break
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
