from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "components/clientjs-auto/kvtm_automation"
AUTO_MAIN = CLEAN / "workflows/auto_main/workflow.py"
BOUNDARY_DELAY = CLEAN / "workflows/auto_main/boundary_delay.py"
FRIEND_REFRESH = CLEAN / "workflows/auto_main/friend_refresh.py"
BUILDER_MODULES = CLEAN / "workflows/auto_builder/modules.py"
BUILDER_DELAY = CLEAN / "workflows/auto_builder/loop_delay_patch.py"


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing module/scheduler boundary file: {path}")
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path))
    return text


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def forbid(text: str, token: str, message: str) -> None:
    if token in text:
        raise AssertionError(message)


def forbid_raw_input(text: str, label: str) -> None:
    for token in (".driver.click(", ".driver.swipe(", ".driver.swipe_points("):
        forbid(text, token, f"{label} contains raw input gesture: {token}")


def class_source(text: str, class_name: str) -> str:
    tree = ast.parse(text)
    lines = text.splitlines()
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            start = int(node.lineno) - 1
            end = int(getattr(node, "end_lineno", node.lineno))
            return "\n".join(lines[start:end])
    raise AssertionError(f"Missing class: {class_name}")


def main() -> int:
    auto_main = read(AUTO_MAIN)
    boundary_delay = read(BOUNDARY_DELAY)
    friend_refresh = read(FRIEND_REFRESH)
    builder_modules = read(BUILDER_MODULES)
    builder_delay = read(BUILDER_DELAY)

    # The base scheduler remains the single owner of the main run loop. The
    # boundary-delay layer may override hooks only; it must never copy run().
    require(
        boundary_delay,
        "class AutoMainWorkflow(_BaseAutoMainWorkflow):",
        "Boundary-aware scheduler is not a thin subclass of the canonical scheduler",
    )
    for token in (
        "def _sale_once(",
        "def _friend_refresh_if_due(",
        "def _wait_before_next_function_loop(",
    ):
        require(boundary_delay, token, f"Boundary delay hook missing: {token}")
    forbid(
        class_source(boundary_delay, "AutoMainWorkflow"),
        "def run(",
        "boundary_delay.py duplicated the full AUTO Main scheduler run loop",
    )
    require(auto_main, "def run(self) -> AutoMainResult:", "Canonical AUTO Main run loop missing")
    forbid_raw_input(auto_main, "AutoMainWorkflow")

    # Periodic Friend Refresh is a maintenance Module. It uses semantic
    # navigation/recovery APIs and never owns raw coordinates/gestures.
    require(friend_refresh, "class FriendRefreshWorkflow:", "FriendRefreshWorkflow missing")
    require(friend_refresh, "self.auto.navigation.go_to_friend(", "Friend Refresh does not use semantic friend navigation")
    require(friend_refresh, "self.auto.navigation.return_home(", "Friend Refresh does not use semantic return-home navigation")
    require(friend_refresh, "return False", "Friend Refresh cannot report safe recovered/non-PASS maintenance")
    require(friend_refresh, "return True", "Friend Refresh PASS result missing")
    forbid_raw_input(friend_refresh, "FriendRefreshWorkflow")

    # Builder modules are visible independent adapters. FunctionModule must not
    # hide Sale; SellFunctionVpModule is the only business sale adapter here.
    enter_game = class_source(builder_modules, "EnterGamePopupModule")
    sale_module = class_source(builder_modules, "SellFunctionVpModule")
    function_module = class_source(builder_modules, "FunctionModule")
    repair_module = class_source(builder_modules, "MachineRepairTestModule")

    require(enter_game, "GameSessionWorkflow(self.auto).run", "Builder startup module does not delegate GameSessionWorkflow")
    require(sale_module, "AutoVpSaleWorkflow(", "Builder sale module does not delegate AutoVpSaleWorkflow")
    require(function_module, "workflow = FunctionOneWorkflow(self.auto)", "Builder Function 1 cached adapter missing")
    require(function_module, "workflow = FunctionTwoWorkflow(self.auto)", "Builder Function 2 cached adapter missing")
    require(function_module, "result = self._workflow(spec.runner_key).run()", "Builder Function adapter does not reuse in-flight workflow")
    require(function_module, "workflow.recovery.commit_cycle()", "Builder Function adapter cannot commit completed cycle")
    forbid(function_module, "AutoVpSaleWorkflow(", "Builder FunctionModule hides a Sale workflow")
    forbid(function_module, "self.sale", "Builder FunctionModule hides Sale state/calls")
    require(repair_module, "self.auto.machine_repair.test_from_open_production_panel()", "Builder repair module does not delegate repair Action")
    forbid_raw_input(builder_modules, "Builder Modules")

    # Builder loop delay uses the same minimum-boundary semantics: maintenance
    # elapsed time is subtracted before any remaining sleep.
    require(builder_delay, "boundary_started_at = time.monotonic()", "Builder boundary timer does not start after Function PASS")
    require(builder_delay, "remaining = max(0.0, delay - elapsed)", "Builder delay still sleeps the full configured time after maintenance")

    print("AUTO MODULE/SCHEDULER BOUNDARY CONTRACT VERIFIED")
    print("auto-main=single-run-loop+thin-boundary-delay-hooks")
    print("friend-refresh=semantic-navigation+no-raw-input")
    print("builder-modules=independent-visible-adapters")
    print("builder-delay=maintenance-time-counted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
