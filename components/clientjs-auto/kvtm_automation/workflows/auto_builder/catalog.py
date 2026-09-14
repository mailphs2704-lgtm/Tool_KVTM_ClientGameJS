from __future__ import annotations

from dataclasses import dataclass


__all__ = ["FunctionSpec", "FUNCTION_SPECS", "get_function_spec"]
FILE_FUNCTIONS = (
    "Khai báo metadata Function dùng chung cho Builder",
    "Khai báo VP được phép bán theo từng Function",
    "Tra cứu Function theo id và fail-close khi chưa hỗ trợ",
)


@dataclass(frozen=True)
class FunctionSpec:
    function_id: str
    label: str
    sale_item_ids: tuple[str, ...]
    runner_key: str


FUNCTION_SPECS = {
    "function_1": FunctionSpec(
        function_id="function_1",
        label="Function 1 • Táo / Nước táo / Vải vàng",
        sale_item_ids=("tao_say", "vai_vang"),
        runner_key="function_1",
    ),
    "function_2": FunctionSpec(
        function_id="function_2",
        label="9 Táo sấy - 9 Vải vàng - 7 tinh dầu hoa hồng",
        sale_item_ids=("tao_say", "vai_vang", "tinh_dau_hh"),
        runner_key="function_2",
    ),
    "function_3": FunctionSpec(
        function_id="function_3",
        label="9 Nước hoa hồng - 9 Trà đá - 9 Vải vàng",
        sale_item_ids=("nuoc_hoa_hong", "tra_da", "vai_vang"),
        runner_key="function_3",
    ),
}


def get_function_spec(function_id: str) -> FunctionSpec:
    key = str(function_id or "").strip().lower()
    spec = FUNCTION_SPECS.get(key)
    if spec is None:
        raise ValueError(f"AUTO Builder chưa hỗ trợ Function: {function_id!r}")
    return spec
