from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "components/clientjs-auto/kvtm_automation"
INIT = CLEAN / "recipes/__init__.py"
BOOK = CLEAN / "recipes/book.py"
DRIED = CLEAN / "recipes/dried_apple.py"
JUICE = CLEAN / "recipes/apple_juice.py"
FABRIC = CLEAN / "recipes/yellow_fabric.py"
FUNCTION_ONE = CLEAN / "workflows/auto_function_one/workflow.py"


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing recipe architecture file: {path}")
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path))
    return text


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def forbid(text: str, token: str, message: str) -> None:
    if token in text:
        raise AssertionError(message)


def main() -> int:
    init = read(INIT)
    book = read(BOOK)
    dried = read(DRIED)
    juice = read(JUICE)
    fabric = read(FABRIC)
    function_one = read(FUNCTION_ONE)

    for token in (
        "RecipeBook", "DriedAppleRecipe", "AppleJuiceRecipe", "YellowFabricRecipe",
    ):
        require(init, token, f"recipes package export missing: {token}")

    # One book per Function: all product recipes share the same recovery policy.
    require(book, "class RecipeBook:", "RecipeBook missing")
    require(book, "function_id: str", "RecipeBook Function binding missing")
    require(book, "self.recovery = recovery or RecoveryManager(", "Shared recovery manager missing")
    require(book, "self.dried_apple = DriedAppleRecipe(", "Dried recipe wiring missing")
    require(book, "self.apple_juice = AppleJuiceRecipe(", "Juice recipe wiring missing")
    require(book, "self.yellow_fabric = YellowFabricRecipe(", "Fabric recipe wiring missing")
    require(book, "apple_juice=self.apple_juice", "Recipe dependency injection missing")

    # Dried Apple is independently callable and owns its planting + production.
    require(dried, "class DriedAppleRecipe:", "DriedAppleRecipe missing")
    require(dried, "def run_from_session(", "Dried recipe session entry missing")
    require(dried, "def run_from_main(", "Dried recipe standalone main entry missing")
    require(dried, "self.auto.planting.plant_27_apples()", "Dried recipe planting missing")
    require(dried, "self.recovery.run_production(", "Dried recipe recovery missing")
    require(dried, "self.auto.machine_repair.repair_after_production(produced)", "Dried recipe repair missing")

    # Apple Juice must remain standalone: it may not depend on Yellow Fabric.
    require(juice, "class AppleJuiceRecipe:", "AppleJuiceRecipe missing")
    require(juice, "def run_from_main(", "Standalone juice entry missing")
    require(juice, "def run_current_floor_2(", "Known floor2 juice entry missing")
    require(juice, "def run_from_candidate_floor_2(", "Candidate floor2 juice entry missing")
    require(
        juice,
        "production opener để chỉ chạy shared collector đúng một lần",
        "Apple Juice candidate still risks a duplicate probe/collector",
    )
    forbid(
        juice,
        "probe_floor_2_machine()",
        "Apple Juice recipe must not collect VP twice through candidate probe",
    )
    require(juice, "self.recovery.run_production(", "Juice production recovery missing")
    require(juice, "self.auto.machine_repair.repair_after_production(produced)", "Juice repair missing")
    forbid(juice, "YellowFabricRecipe", "Apple Juice must not depend on Yellow Fabric")
    forbid(juice, "cotton_planting", "Apple Juice must not plant cotton")

    # Yellow Fabric may optionally call Apple Juice, but can also run without it.
    require(fabric, "class YellowFabricRecipe:", "YellowFabricRecipe missing")
    require(fabric, "include_apple_juice_dependency: bool = False", "Optional juice dependency default changed")
    require(fabric, "if include_apple_juice_dependency:", "Optional dependency branch missing")
    require(fabric, "self.apple_juice.run_from_main(count=count)", "Reusable juice dependency call missing")
    require(fabric, "def run_after_floor_2(", "Post-juice Function entry missing")
    require(fabric, "self.auto.cotton_planting.plant_27_cotton()", "Cotton planting missing")
    require(fabric, 'self.recovery.from_floor_to_floor(1, 3, "Vải vàng recipe")',
            "Floor1->3 recipe route missing")
    require(fabric, "self.recovery.run_production(", "Fabric production recovery missing")
    require(fabric, "self.auto.machine_repair.repair_after_production(produced)", "Fabric repair missing")

    # Function 1 is now recipe composition plus only its unique apple-supply route.
    require(function_one, "self.recipes = RecipeBook(", "Function 1 RecipeBook missing")
    require(function_one, "self.recipes.dried_apple.run_from_session(count=9)", "Dried recipe call missing")
    require(function_one, "self.recipes.apple_juice.run_from_candidate_floor_2(count=9)", "Juice recipe call missing")
    require(function_one, "self.recipes.yellow_fabric.run_after_floor_2(count=9)", "Fabric recipe call missing")
    forbid(function_one, "self.auto.cotton_planting.plant_27_cotton()", "Function 1 duplicated cotton recipe logic")
    forbid(function_one, "produce_9_apple_juices(", "Function 1 duplicated juice production")
    forbid(function_one, "produce_9_yellow_fabrics(", "Function 1 duplicated fabric production")
    forbid(function_one, "repair_after_production(", "Function 1 duplicated recipe repair")

    print("AUTO MULTI DEV RECIPE ARCHITECTURE CONTRACT VERIFIED")
    print("actions=atomic")
    print("recovery=centralized")
    print("recipes=reusable-product-orchestration")
    print("apple_juice=standalone")
    print("yellow_fabric=optional-apple-juice-dependency")
    print("function1=recipe-composition+unique-supply-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
