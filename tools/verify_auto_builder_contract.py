from __future__ import annotations

"""Composite AUTO Builder gate: stable Builder core + guarded Function 2."""

from verify_auto_builder_contract_core import *  # noqa: F401,F403
from verify_auto_builder_contract_core import main as _verify_builder_core
from verify_auto_function_two_contract import main as _verify_function_two
from verify_auto_function_two_handoff_contract import main as _verify_function_two_handoff
from verify_auto_function_two_ui_contract import main as _verify_function_two_ui
from verify_auto_sale_speed_contract import main as _verify_sale_speed


def main() -> int:
    if _verify_builder_core() != 0:
        raise AssertionError("AUTO Builder core static contract failed")
    if _verify_function_two() != 0:
        raise AssertionError("AUTO Function 2 static contract failed")
    if _verify_function_two_handoff() != 0:
        raise AssertionError("AUTO Function 2 handoff static contract failed")
    if _verify_function_two_ui() != 0:
        raise AssertionError("AUTO Function 2 UI static contract failed")
    if _verify_sale_speed() != 0:
        raise AssertionError("AUTO sale speed static contract failed")
    print("AUTO MULTI DEV BUILDER + FUNCTION TWO COMPOSITE GATE VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
