from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "components/clientjs-auto/kvtm_automation"
RECIPES = CLEAN / "recipes"
ACTIONS = CLEAN / "actions"
WORKFLOWS = CLEAN / "workflows"
AUTOMATION = CLEAN / "automation.py"

DRIED_APPLE = RECIPES / "dried_apple.py"
APPLE_JUICE = RECIPES / "apple_juice.py"
YELLOW_FABRIC = RECIPES / "yellow_fabric.py"
ROSE_OIL = RECIPES / "rose_oil.py"
RECIPE_BOOK = RECIPES / "book.py"
ROSE_OIL_ACTION = ACTIONS / "rose_oil_production.py"
FUNCTION_ONE = WORKFLOWS / "auto_function_one/workflow.py"
FUNCTION_TWO = WORKFLOWS / "auto_function_two/workflow.py"


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing Recipe/Function standardization file: {path}")
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
    for token in (
        ".driver.click(",
        ".driver.swipe(",
        ".driver.swipe_points(",
    ):
        forbid(text, token, f"{label} contains raw input gesture: {token}")


def main() -> int:
    automation = read(AUTOMATION)
    dried_apple = read(DRIED_APPLE)
    apple_juice = read(APPLE_JUICE)
    yellow_fabric = read(YELLOW_FABRIC)
    rose_oil = read(ROSE_OIL)
    recipe_book = read(RECIPE_BOOK)
    rose_oil_action = read(ROSE_OIL_ACTION)
    function_one = read(FUNCTION_ONE)
    function_two = read(FUNCTION_TWO)

    # KVAutomation owns shared Action instances. Recipes consume the facade and
    # never construct product Actions ad hoc.
    require(
        automation,
        "self.rose_oil_production = RoseOilProductionActions(",
        "KVAutomation does not own the TDHH production Action",
    )
    require(
        rose_oil,
        "self.production = automation.rose_oil_production",
        "RoseOilRecipe creates/uses a TDHH production Action outside KVAutomation",
    )
    forbid(
        rose_oil,
        "RoseOilProductionActions(",
        "RoseOilRecipe constructs RoseOilProductionActions directly",
    )
    forbid(
        rose_oil,
        "from ..actions.rose_oil_production import RoseOilProductionActions",
        "RoseOilRecipe imports concrete TDHH Action instead of using KVAutomation facade",
    )

    # Recipe decides WHEN navigation is needed; Action owns HOW to close the panel.
    require(
        rose_oil_action,
        "def close_panel_for_navigation(",
        "TDHH production Action lacks semantic panel-close operation",
    )
    require(
        rose_oil,
        "self.production.close_panel_for_navigation()",
        "RoseOilRecipe does not delegate panel close gesture to Action",
    )

    # No Recipe or Function may contain raw input gestures/coordinates. They may
    # call semantic Actions/Recovery routes and enforce business pre/postconditions.
    for text, label in (
        (dried_apple, "DriedAppleRecipe"),
        (apple_juice, "AppleJuiceRecipe"),
        (yellow_fabric, "YellowFabricRecipe"),
        (rose_oil, "RoseOilRecipe"),
        (function_one, "FunctionOneWorkflow"),
        (function_two, "FunctionTwoWorkflow"),
    ):
        forbid_raw_input(text, label)

    # Exactly one RecoveryManager is shared through RecipeBook per Function.
    require(
        recipe_book,
        "self.recovery = recovery or RecoveryManager(",
        "RecipeBook does not own one shared RecoveryManager",
    )
    for token in (
        "recovery=self.recovery",
        "self.dried_apple = DriedAppleRecipe(",
        "self.apple_juice = AppleJuiceRecipe(",
        "self.yellow_fabric = YellowFabricRecipe(",
    ):
        require(recipe_book, token, f"RecipeBook shared-recovery contract missing: {token}")
    require(
        recipe_book,
        'if self.function_id == "function_2":',
        "RecipeBook does not scope RoseOilRecipe to Function 2",
    )

    # Product recipes route production through shared RecoveryManager and repair
    # through Action facade; they must not own warehouse/wrong-machine handlers.
    for text, label in (
        (dried_apple, "DriedAppleRecipe"),
        (apple_juice, "AppleJuiceRecipe"),
        (yellow_fabric, "YellowFabricRecipe"),
        (rose_oil, "RoseOilRecipe"),
    ):
        require(text, "self.recovery", f"{label} does not consume shared recovery")
        forbid(text, "except InventoryFull", f"{label} duplicates InventoryFull recovery")
        forbid(text, "except WrongProductionMachine", f"{label} duplicates wrong-machine recovery")

    require(
        function_one,
        "self.recipes = RecipeBook(",
        "Function 1 does not compose RecipeBook",
    )
    require(
        function_one,
        "self.recovery = self.recipes.recovery",
        "Function 1 does not share RecipeBook recovery",
    )
    forbid(function_one, "RecoveryManager(", "Function 1 constructs a parallel RecoveryManager")

    require(
        function_two,
        'function_id="function_2"',
        "Function 2 does not construct Function-2 RecipeBook",
    )
    require(
        function_two,
        "self.recovery = self.recipes.recovery",
        "Function 2 does not share RecipeBook recovery",
    )
    require(
        function_two,
        "self.base = FunctionOneWorkflow(",
        "Function 2 no longer composes Function 1 core",
    )
    forbid(function_two, "RecoveryManager(", "Function 2 constructs a parallel RecoveryManager")

    # TDHH semantics stay explicit: materials are crops, TDHH is the finished VP.
    require(rose_oil, "Hồng and Tuyết are crop/material inputs", "TDHH material classification missing")
    require(rose_oil, "TDHH (Tinh dầu hoa hồng) is a finished VP product", "TDHH finished-VP classification missing")

    print("AUTO RECIPE/FUNCTION STANDARDIZATION CONTRACT VERIFIED")
    print("recipes=orchestration-only+no-raw-input")
    print("actions=shared-through-KVAutomation")
    print("recovery=one-shared-manager-per-function")
    print("functions=compose-recipes+no-parallel-recovery")
    print("tdhh=rose-snow-materials+finished-vp-production")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
