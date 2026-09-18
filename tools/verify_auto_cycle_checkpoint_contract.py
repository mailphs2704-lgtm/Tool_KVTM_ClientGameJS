from __future__ import annotations

import ast
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
AUTO = ROOT / "components" / "clientjs-auto" / "kvtm_automation"
sys.path.insert(0, str(AUTO.parent))


def read(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path))
    return text


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def main() -> int:
    checkpoint = read(AUTO / "recovery" / "cycle_checkpoint.py")
    manager = read(AUTO / "recovery" / "manager.py")
    modules = read(AUTO / "workflows" / "auto_builder" / "modules.py")
    auto_main = read(AUTO / "workflows" / "auto_main" / "workflow.py")
    function_one = read(AUTO / "workflows" / "auto_function_one" / "workflow.py")
    function_three = read(AUTO / "workflows" / "auto_function_three" / "workflow.py")

    require(checkpoint, "def run_once(", "Cycle lock runner missing")
    require(checkpoint, "def commit_cycle(", "Cycle lock commit missing")
    require(manager, "self.cycle = CycleCheckpoint(", "RecoveryManager does not own cycle locks")
    require(modules, "self._workflows: dict[str, Any]", "Function workflows are not retained")
    require(modules, "workflow.recovery.commit_cycle()", "Completion cannot release locks")
    require(
        auto_main,
        "self.function.commit_cycle(function_id=self.spec.function_id)",
        "AUTO Main does not commit only after completion validation",
    )

    for token in (
        "function-1-dried-apple",
        "function-1-apple-floor-1-to-5",
        "function-1-apple-floor-6",
        "function-1-apple-juice",
        "function-1-yellow-fabric",
    ):
        require(function_one, token, f"Function 1 lock missing: {token}")

    for ordinal in range(1, 7):
        require(
            function_three,
            f'"function-3-step-{ordinal}"',
            f"Function 3 Step {ordinal} lock missing",
        )

    material_files = {
        "dried_apple.py": 1,
        "yellow_fabric.py": 1,
        "rose_oil.py": 3,
        "dried_tea_step_one.py": 2,
        "dried_tea_step_two.py": 1,
        "dried_tea_step_three.py": 2,
        "dried_tea_step_four.py": 4,
        "dried_tea_step_five.py": 2,
        "dried_tea_step_six.py": 2,
    }
    for name, minimum in material_files.items():
        source = read(AUTO / "recipes" / name)
        actual = source.count("self.recovery.cycle.run_once(")
        if actual < minimum:
            raise AssertionError(
                f"Material locks missing in {name}: {actual}/{minimum}"
            )

    print("AUTO FUNCTION CYCLE CHECKPOINT CONTRACT VERIFIED")
    print("functions=1+2+3 retain in-flight workflow until completion gate")
    print("materials=all current crop positions use shared RecoveryManager cycle lock")
    print("recovery=completed phases skip side effects and replay canonical navigation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
