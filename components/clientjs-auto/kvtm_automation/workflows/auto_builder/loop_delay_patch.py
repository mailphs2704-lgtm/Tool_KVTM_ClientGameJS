from __future__ import annotations

import time


__all__ = ["install_function_loop_delay"]
FILE_FUNCTIONS = (
    "Áp dụng thời gian chờ chỉ cho module Function có loops",
    "Boundary delay bắt đầu ngay khi Function PASS; thời gian Sale/maintenance được tính vào khoảng chờ",
    "Sau Sale chỉ chờ phần thời gian còn thiếu, không sleep lại toàn bộ delay",
    "Không chờ sau vòng cuối và không ảnh hưởng Click/Swipe/Wait/Bán VP/Vào game",
    "Hỗ trợ cả Function built-in và Function tự tạo được gọi lặp",
    "Giữ wait stop-aware qua automation.wait.sleep",
)

_INSTALLED = False
_MAX_LOOP_DELAY_SECONDS = 3600.0


def _loop_delay(step: dict) -> float:
    value = float(step.get("loop_delay_seconds", 0.0) or 0.0)
    if value < 0.0 or value > _MAX_LOOP_DELAY_SECONDS:
        raise ValueError(
            "loop_delay_seconds phải trong khoảng 0..3600 giây"
        )
    return value


def _wait_between_loops(
    runner,
    *,
    step: dict,
    label: str,
    loop_index: int,
    loops: int,
    boundary_started_at: float,
) -> None:
    if loop_index >= loops:
        return
    delay = _loop_delay(step)
    if delay <= 0.0:
        return

    elapsed = max(0.0, time.monotonic() - float(boundary_started_at))
    remaining = max(0.0, delay - elapsed)
    runner.context.ensure_running()
    if remaining <= 0.0:
        runner.context.log(
            f"AUTO Builder • {label} • boundary đã dùng {elapsed:.3f}s/"
            f"{delay:.3f}s (Sale/maintenance đã đủ thời gian chờ) • "
            f"vào vòng {loop_index + 1}/{loops} ngay"
        )
        return

    runner.context.log(
        f"AUTO Builder • {label} • boundary đã dùng {elapsed:.3f}s/"
        f"{delay:.3f}s • chỉ chờ thêm {remaining:.3f}s trước vòng "
        f"{loop_index + 1}/{loops}"
    )
    runner.auto.wait.sleep(remaining)


def install_function_loop_delay(runner_class) -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_run_action = runner_class._run_action

    def run_action(self, step: dict, call_stack: tuple[str, ...]):
        if step.get("type") != "function":
            return original_run_action(self, step, call_stack)

        function_id = str(step.get("function_id") or "function_1")
        loops = int(step.get("loops", 1))
        for loop_index in range(1, loops + 1):
            self.context.ensure_running()
            self.context.log(
                f"AUTO Builder • {function_id} • vòng {loop_index}/{loops} START"
            )
            self.function.run(function_id=function_id)
            self.function.commit_cycle(function_id=function_id)
            self.function_loops[function_id] = self.function_loops.get(function_id, 0) + 1
            boundary_started_at = time.monotonic()
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
            _wait_between_loops(
                self,
                step=step,
                label=function_id,
                loop_index=loop_index,
                loops=loops,
                boundary_started_at=boundary_started_at,
            )
        return None

    original_run_saved = runner_class._run_saved_function

    def run_saved_function(self, step: dict, call_stack: tuple[str, ...]) -> None:
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
            boundary_started_at = time.monotonic()
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
            _wait_between_loops(
                self,
                step=step,
                label=f"Function tự tạo {function['name']}",
                loop_index=loop_index,
                loops=loops,
                boundary_started_at=boundary_started_at,
            )

    # Keep original references available for debugging/introspection while the
    # runtime class uses the delay-aware variants.
    runner_class._run_action_without_loop_delay = original_run_action
    runner_class._run_saved_function_without_loop_delay = original_run_saved
    runner_class._run_action = run_action
    runner_class._run_saved_function = run_saved_function
