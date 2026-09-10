from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from ...automation import KVAutomation
from ..auto_function_one import FunctionOneWorkflow
from ..auto_function_two import FunctionTwoWorkflow
from ..auto_vp_sale import AutoVpSaleWorkflow
from ..game_session import GameSessionWorkflow
from .catalog import get_function_spec


__all__ = [
    "EnterGamePopupModule",
    "SellFunctionVpModule",
    "FunctionModule",
    "MachineRepairTestModule",
]
FILE_FUNCTIONS = (
    "Gọi riêng module vào game và đóng popup",
    "Gọi riêng module bán VP theo Function",
    "Gọi riêng một vòng Function hoàn chỉnh",
    "Gọi riêng TEST Sửa máy bắt đầu tại panel sản xuất VP đang mở",
    "Chuẩn hóa result module về dict để Scheduler ghi log",
)


def _payload(result: Any) -> dict[str, Any]:
    if is_dataclass(result):
        return dict(asdict(result))
    if hasattr(result, "to_dict"):
        return dict(result.to_dict())
    if isinstance(result, dict):
        return dict(result)
    return {"result": result}


class EnterGamePopupModule:
    module_id = "enter_game_popup"
    label = "Vào game + đóng popup"

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation

    def run(self, *, timeout: float = 180.0) -> dict[str, Any]:
        self.auto.context.stage("builder-module-enter-game-start")
        result = GameSessionWorkflow(self.auto).run(timeout=float(timeout))
        self.auto.context.stage("builder-module-enter-game-finished")
        return _payload(result)


class SellFunctionVpModule:
    module_id = "sell_function_vp"
    label = "Bán VP theo Function"

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation

    def run(
        self,
        *,
        function_id: str,
        timeout: float = 120.0,
    ) -> dict[str, Any]:
        spec = get_function_spec(function_id)
        self.auto.context.stage(f"builder-module-sale-{spec.function_id}-start")
        result = AutoVpSaleWorkflow(
            self.auto,
            function_id=spec.function_id,
            allowed_item_ids=spec.sale_item_ids,
        ).run(timeout=float(timeout))
        self.auto.context.stage(f"builder-module-sale-{spec.function_id}-finished")
        return _payload(result)


class FunctionModule:
    module_id = "function"
    label = "Function"

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation

    def run(self, *, function_id: str) -> dict[str, Any]:
        spec = get_function_spec(function_id)
        self.auto.context.stage(f"builder-function-{spec.function_id}-start")
        if spec.runner_key == "function_1":
            result = FunctionOneWorkflow(self.auto).run()
        elif spec.runner_key == "function_2":
            result = FunctionTwoWorkflow(self.auto).run()
        else:
            raise ValueError(f"Thiếu runner cho {spec.function_id}")
        self.auto.context.stage(f"builder-function-{spec.function_id}-finished")
        return _payload(result)


class MachineRepairTestModule:
    """DEV-only module; operator must already be on an open production panel."""

    module_id = "machine_repair_test"
    label = "TEST Sửa máy từ panel VP"

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation

    def run(self) -> dict[str, Any]:
        self.auto.context.stage("builder-module-machine-repair-test-start")
        result = self.auto.machine_repair.test_from_open_production_panel()
        self.auto.context.stage("builder-module-machine-repair-test-finished")
        return _payload(result)
