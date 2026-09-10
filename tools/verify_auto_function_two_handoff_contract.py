from __future__ import annotations

"""Static gate for Function 2 handoff after inherited Vải vàng production."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "components/clientjs-auto/kvtm_automation"
FUNCTION_ONE = CLEAN / "workflows/auto_function_one/workflow.py"
FUNCTION_TWO = CLEAN / "workflows/auto_function_two/workflow.py"


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing Function 2 handoff file: {path}")
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path))
    return text


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def main() -> int:
    function_one = read(FUNCTION_ONE)
    function_two = read(FUNCTION_TWO)

    require(
        function_one,
        "normalize_end_to_main: bool = True",
        "Function 1 standalone end-loop default changed",
    )
    require(
        function_one,
        "if normalize_end_to_main:",
        "Function 1 end-loop normalization is no longer explicitly guarded",
    )
    require(
        function_one,
        "self._normalize_end_of_loop_to_main()",
        "Function 1 standalone exact-main normalization disappeared",
    )
    require(
        function_one,
        'self.context.stage("auto-function-1-handoff-after-yellow-fabric")',
        "Function 1 inherited handoff marker missing",
    )

    require(
        function_two,
        "base = self.base.run(normalize_end_to_main=False)",
        "Function 2 still executes Function 1 terminal normalization",
    )
    require(
        function_two,
        "def _recover_base_handoff_to_main(self) -> None:",
        "Function 2 handoff recovery helper missing",
    )
    require(
        function_two,
        "self.recovery.recover_unknown_to_main(",
        "Function 2 does not use RecoveryManager for inherited handoff",
    )
    require(
        function_two,
        "max_passes=8",
        "Function 2 handoff recovery is not bounded to 8 passes",
    )
    require(
        function_two,
        'self.context.stage("auto-function-2-base-handoff-main-ready")',
        "Function 2 exact-main handoff PASS marker missing",
    )
    require(
        function_two,
        "self._recover_base_handoff_to_main()",
        "Function 2 does not execute handoff recovery",
    )
    require(
        function_two,
        "extra = self.rose_oil.run_from_main(count=7)",
        "Function 2 TDHH stage missing after handoff",
    )
    if function_two.index("self._recover_base_handoff_to_main()") > function_two.index(
        "extra = self.rose_oil.run_from_main(count=7)"
    ):
        raise AssertionError("Function 2 starts TDHH before exact-main handoff recovery")

    print("AUTO MULTI DEV FUNCTION TWO HANDOFF STATIC CONTRACT VERIFIED")
    print("inheritance=import-composition+function1-core")
    print("handoff=skip-function1-terminal-route+bounded-unknown-to-main")
    print("next=exact-main-before-rose35+snow28+rose-oil7")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
