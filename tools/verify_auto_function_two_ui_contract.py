from __future__ import annotations

"""Static contract for exposing guarded Function 2 in the AUTO Main UI."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "source-archive/multi-current/kvtm_multi_tool/auto_builder_integration.py"
CATALOG = ROOT / "components/clientjs-auto/kvtm_automation/workflows/auto_builder/catalog.py"


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing Function 2 UI contract file: {path}")
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path))
    return text


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def main() -> int:
    integration = read(INTEGRATION)
    catalog = read(CATALOG)

    function_1 = '("function_1", "01. 9 Táo sấy - 9 Vải vàng")'
    function_2_ui = '("function_2", "02. 9 Táo sấy - 9 Vải vàng - 7 Tinh dầu hoa hồng")'
    function_2_catalog = 'label="9 Táo sấy - 9 Vải vàng - 7 tinh dầu hoa hồng"'

    require(integration, "_AUTO_MAIN_FUNCTION_OPTIONS = (", "AUTO Main Function dropdown missing")
    require(integration, function_1, "Function 1 disappeared from AUTO Main dropdown")
    require(integration, function_2_ui, "Function 2 missing from AUTO Main dropdown")
    require(integration, "default_id, default_label = _AUTO_MAIN_FUNCTION_OPTIONS[0]", "Function 1 default selector changed")
    require(integration, "for function_id, label in _AUTO_MAIN_FUNCTION_OPTIONS:", "Function menu is not built from guarded options")
    require(integration, "valid_ids = {item[0] for item in _AUTO_MAIN_FUNCTION_OPTIONS}", "AUTO Main start does not validate selected Function")
    require(integration, '"function_id": function_id', "Selected Function is not frozen into worker config")
    require(integration, 'start_button.configure(command=self._start_configured_auto_main)', "AUTO Main Start is not bound to configured Function")
    require(integration, "_CLIENT_RESTART_INTERVAL_SECONDS = 0.0", "Function 2 UI integration must block restart")
    require(integration, "scheduled_restart = False", "Function 2 integration restart supervisor is not blocked")
    require(integration, "restart ClientJS=BLOCK (3h + lỗi)", "Function 2 UI blocked-restart marker missing")

    require(catalog, '"function_1": FunctionSpec(', "Function 1 catalog entry missing")
    require(catalog, '"function_2": FunctionSpec(', "Function 2 catalog entry missing")
    require(catalog, function_2_catalog, "Function 2 catalog label drift")
    require(catalog, 'sale_item_ids=("tao_say", "vai_vang", "tinh_dau_hh")', "Function 2 sale ownership changed")

    first = integration.index(function_1)
    second = integration.index(function_2_ui)
    if first >= second:
        raise AssertionError("Function 1 must remain the default first AUTO Main option")

    print("AUTO MULTI DEV FUNCTION TWO UI STATIC CONTRACT VERIFIED")
    print("dropdown=function1-default+function2-explicit")
    print("worker_config=function-id-frozen-per-profile")
    print("restart=blocked-3h-and-error")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
