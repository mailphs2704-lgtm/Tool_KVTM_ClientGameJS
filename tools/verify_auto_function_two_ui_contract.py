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

    function_1 = '("function_1", "9 Táo sấy - 9 Vải vàng")'
    function_2 = '("function_2", "9 Táo sấy - 9 Vải vàng - 7 Tinh dầu hoa hồng")'
    require(integration, "_AUTO_MAIN_FUNCTION_OPTIONS = (", "AUTO Main Function dropdown missing")
    require(integration, function_1, "Function 1 disappeared from AUTO Main dropdown")
    require(integration, function_2, "Function 2 missing from AUTO Main dropdown")
    require(integration, "default_id, default_label = _AUTO_MAIN_FUNCTION_OPTIONS[0]", "Function 1 default selector changed")
    require(integration, "for function_id, label in _AUTO_MAIN_FUNCTION_OPTIONS:", "Function menu is not built from guarded options")
    require(integration, "valid_ids = {item[0] for item in _AUTO_MAIN_FUNCTION_OPTIONS}", "AUTO Main start does not validate selected Function")
    require(integration, '"function_id": function_id', "Selected Function is not frozen into worker config")
    require(integration, 'start_button.configure(command=self._start_configured_auto_main)', "AUTO Main Start is not bound to configured Function")
    require(integration, 'resume["skip_initial_sale_once"] = True', "Client restart resume guard changed")
    require(integration, "self._start_clean_auto_profile_only(profile_id)", "Client restart does not relaunch only requesting profile")
    require(integration, "_CLIENT_RESTART_INTERVAL_SECONDS = 10800.0", "Function 2 UI integration no longer uses 3h restart")

    require(catalog, '"function_1": FunctionSpec(', "Function 1 catalog entry missing")
    require(catalog, '"function_2": FunctionSpec(', "Function 2 catalog entry missing")
    require(catalog, 'label="9 Táo sấy - 9 Vải vàng - 7 Tinh dầu hoa hồng"', "Function 2 UI/catalog label drift")

    first = integration.index(function_1)
    second = integration.index(function_2)
    if first >= second:
        raise AssertionError("Function 1 must remain the default first AUTO Main option")

    print("AUTO MULTI DEV FUNCTION TWO UI STATIC CONTRACT VERIFIED")
    print("dropdown=function1-default+function2-explicit")
    print("worker_config=function-id-frozen-per-profile")
    print("restart=3h+same-profile+skip-duplicate-initial-sale")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
