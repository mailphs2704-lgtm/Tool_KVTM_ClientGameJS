from __future__ import annotations

"""Static contract for guarded AUTO MULTI DEV Function 2."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "components/clientjs-auto/kvtm_automation"
PLANTING = CLEAN / "actions/function_two_planting.py"
ROSE_OIL_ACTION = CLEAN / "actions/rose_oil_production.py"
ROSE_OIL_RECIPE = CLEAN / "recipes/rose_oil.py"
RECIPE_BOOK = CLEAN / "recipes/book.py"
FUNCTION_ONE = CLEAN / "workflows/auto_function_one/workflow.py"
FUNCTION_TWO = CLEAN / "workflows/auto_function_two/workflow.py"
CATALOG = CLEAN / "workflows/auto_builder/catalog.py"
MODULES = CLEAN / "workflows/auto_builder/modules.py"
SALE_WORKFLOW = CLEAN / "workflows/auto_vp_sale/workflow.py"
SALE_ACTION = CLEAN / "actions/auto_main_selling.py"
AUTO_MAIN = CLEAN / "workflows/auto_main/workflow.py"


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing Function 2 contract file: {path}")
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
    planting = read(PLANTING)
    rose_action = read(ROSE_OIL_ACTION)
    rose_recipe = read(ROSE_OIL_RECIPE)
    recipe_book = read(RECIPE_BOOK)
    function_one = read(FUNCTION_ONE)
    function_two = read(FUNCTION_TWO)
    catalog = read(CATALOG)
    modules = read(MODULES)
    sale_workflow = read(SALE_WORKFLOW)
    sale_action = read(SALE_ACTION)
    auto_main = read(AUTO_MAIN)

    # Function-2 planting is an isolated native-1000 extension. It must not
    # weaken or reuse the stable native-500 sale calibration as an authorization.
    require(planting, 'SNOW_TEMPLATE = "cay_tuyet"', "Function 2 snow template missing")
    require(planting, "ROSE_COUNT = 35", "Function 2 rose count changed")
    require(planting, "SNOW_COUNT = 28", "Function 2 snow count changed")
    require(planting, "if (width, height) != (1000, 1000):", "Function 2 native-1000 gate missing")
    require(planting, "Không chạy bảng 500x500", "Function 2 native-500 fail-close marker missing")
    require(planting, "self.vision.driver.swipe_points(\n                    tuple(path),", "RIPE harvest must start from farm path")
    require(planting, "plant_path = (match.center,) + tuple(path[1:])", "Seed drag must start from verified seed center")
    require(planting, "self.floors.up(5)", "Rose floor1->6 transition missing")
    require(planting, "self.floors.up(1)", "Rose->snow floor7 transition missing")
    require(planting, "end_floor=7", "Function 2 material handoff floor changed")

    # Exact-seven TDHH production remains product-proven, retry-bounded and
    # fail-closed when materials or post-drag slot deltas are not proven.
    require(rose_action, "ROSE_OIL_FLOOR = 5", "TDHH floor changed")
    require(rose_action, 'ROSE_OIL_TEMPLATE = "tinh_dau_hh"', "TDHH product template missing")
    require(rose_action, "TARGET_COUNT = 7", "TDHH target count changed")
    require(rose_action, '"tinh_dau_hh",', "TDHH missing from known production anchors")
    require(rose_action, "for ordinal in range(1, self.TARGET_COUNT + 1):", "Exact-seven TDHH loop missing")
    require(rose_action, "if current_empty >= empty_after:", "TDHH post-drag slot proof missing")
    require(rose_action, "consumed != self.TARGET_COUNT", "TDHH exact-seven final delta proof missing")
    require(rose_action, "Thiếu Hồng/Tuyết", "TDHH material fail-close missing")

    # RoseOilRecipe owns the extra recovery route map. RecipeBook function_2 must
    # reuse that same manager for every inherited Function-1 recipe so warehouse
    # recovery and Function-bound sale policy stay function_2 end-to-end.
    require(rose_recipe, "self.recovery = RecoveryManager(", "TDHH recovery manager missing")
    require(rose_recipe, 'function_id="function_2"', "TDHH recovery is not Function-2-bound")
    require(rose_recipe, "to_main_routes={5: self._floor_5_to_main}", "TDHH floor5->main route missing")
    require(rose_recipe, "from_main_routes={5: self._main_to_floor_5}", "TDHH main->floor5 route missing")
    require(rose_recipe, "between_floor_routes={(7, 5): self._floor_7_to_floor_5}", "TDHH floor7->5 route missing")
    require(rose_recipe, "self.recovery.from_floor_to_floor(7, 5", "TDHH recipe does not use recovery floor7->5")
    require(rose_recipe, "self.recovery.run_production(", "TDHH production bypasses RecoveryManager")
    require(rose_recipe, "close_after_success=False", "TDHH panel is not handed to machine repair")
    require(rose_recipe, "self.auto.machine_repair.repair_after_production(produced)", "TDHH repair handoff missing")
    require(rose_recipe, "self.recovery.to_main_from_floor(5", "TDHH recipe does not normalize floor5->main")

    require(recipe_book, "self.rose_oil: RoseOilRecipe | None = None", "RecipeBook Function-2 slot missing")
    require(recipe_book, 'if self.function_id == "function_2":', "RecipeBook Function-2 branch missing")
    require(recipe_book, "self.rose_oil = RoseOilRecipe(automation)", "RecipeBook does not construct TDHH recipe")
    require(recipe_book, "self.recovery = self.rose_oil.recovery", "Function 2 does not share TDHH recovery manager")
    require(recipe_book, "recovery=self.recovery", "Inherited recipes do not share Function-2 recovery")
    require(recipe_book, "apple_juice=self.apple_juice", "Yellow-fabric dependency sharing changed")

    # FunctionOneWorkflow stays standalone-compatible but can be reused as the
    # proven 3/4 base with the Function-2 RecipeBook injected explicitly.
    require(function_one, "recipes: RecipeBook | None = None", "Function 1 RecipeBook injection point missing")
    require(function_one, "if recipes is None:", "Function 1 standalone RecipeBook path missing")
    require(function_one, "self.recipes = recipes", "Function 1 injected RecipeBook path missing")
    require(function_one, 'function_id="function_1"', "Function 1 standalone identity changed")
    require(function_one, "progress_steps=3", "Function 1 progress contract changed")
    require(function_one, "total_steps=3", "Function 1 total contract changed")

    require(function_two, "from ...recipes import RecipeBook", "Function 2 RecipeBook import missing")
    require(function_two, "self.recipes = RecipeBook(", "Function 2 RecipeBook construction missing")
    require(function_two, 'function_id="function_2"', "Function 2 RecipeBook identity missing")
    require(function_two, "recipes=self.recipes", "Function 2 base does not share RecipeBook")
    require(function_two, "self.recovery = self.recipes.recovery", "Function 2 recovery facade not shared")
    require(function_two, "self.rose_oil = self.recipes.rose_oil", "Function 2 bypasses RecipeBook TDHH recipe")
    forbid(function_two, "RoseOilRecipe(automation)", "Function 2 constructs TDHH recipe outside RecipeBook")
    require(function_two, "int(result.progress_steps) != 3", "Function 2 base 3/3 gate missing")
    require(function_two, "int(result.dried_apples) != 9", "Function 2 base dried-apple count gate missing")
    require(function_two, "int(result.apple_juices) != 9", "Function 2 base apple-juice count gate missing")
    require(function_two, "int(result.cotton_planted) != 27", "Function 2 base cotton count gate missing")
    require(function_two, "int(result.yellow_fabrics) != 9", "Function 2 base yellow-fabric count gate missing")
    require(function_two, "int(extra.rose_planted) != 35", "Function 2 rose completion gate missing")
    require(function_two, "int(extra.snow_planted) != 28", "Function 2 snow completion gate missing")
    require(function_two, "int(extra.queued_count) != 7", "Function 2 TDHH completion gate missing")
    require(function_two, "progress_steps=4", "Function 2 progress 4/4 missing")
    require(function_two, "total_steps=4", "Function 2 total 4/4 missing")

    # Catalog, dispatcher and scheduler must expose the exact Function-2 business
    # contract and never silently route it to Function 1.
    require(catalog, '"function_2": FunctionSpec(', "Function 2 catalog entry missing")
    require(catalog, 'label="9 Táo sấy - 9 Vải vàng - 7 tinh dầu hoa hồng"', "Function 2 operator label changed")
    require(catalog, 'sale_item_ids=("tao_say", "vai_vang", "tinh_dau_hh")', "Function 2 sale ownership changed")
    require(catalog, 'runner_key="function_2"', "Function 2 runner key missing")
    require(modules, 'elif spec.runner_key == "function_2":', "Function 2 dispatcher branch missing")
    require(modules, "FunctionTwoWorkflow(self.auto).run()", "Function 2 dispatcher target missing")

    # Sale must reject Function 2 on non-native-1000 before any stall/inventory UI
    # side effect, and recognition must scan only the Function-specific item list.
    require(sale_workflow, "def _require_function_resolution(self) -> None:", "Function 2 sale resolution gate missing")
    require(sale_workflow, 'if self.function_id != "function_2":', "Function 2 sale gate selector missing")
    require(sale_workflow, "if native != (1000, 1000):", "Function 2 sale native-1000 check missing")
    require(sale_workflow, "self._require_function_resolution()", "Function 2 sale gate not called")
    if sale_workflow.index("self._require_function_resolution()") > sale_workflow.index("self.auto.ensure_main_screen(timeout=timeout)"):
        raise AssertionError("Function 2 resolution gate must run before sale UI/navigation")
    require(sale_action, '"tinh_dau_hh": "tinh_dau_hh"', "TDHH selected-item proof missing")
    require(sale_action, "item_ids=self.ITEM_ORDER", "Sale recognition is not Function-bound")

    # Keep the proven native-500 exact-x10 table intact while Function 2 remains
    # 1000-only. This catches accidental threshold/scale drift during TDHH work.
    require(sale_action, "N500_EXACT_TEN_THRESHOLD = 0.78", "Native500 x10 threshold regressed")
    require(sale_action, "N500_EXACT_TEN_SCALES = (0.75, 0.90, 1.00, 1.10, 1.25, 1.40, 1.55)", "Native500 x10 scales regressed")
    require(sale_action, "N1000_EXACT_TEN_THRESHOLD = 0.95", "Native1000 x10 threshold changed")
    require(sale_action, "N1000_EXACT_TEN_SCALES = (1.00,)", "Native1000 x10 baseline scale changed")

    # Scheduler completion is the final contract boundary before a Function loop
    # is counted PASS and before periodic sale/restart maintenance can continue.
    require(auto_main, 'if self.spec.runner_key == "function_2":', "AUTO Main Function-2 completion branch missing")
    require(auto_main, '"roses_planted": 35', "AUTO Main rose count gate missing")
    require(auto_main, '"snow_planted": 28', "AUTO Main snow count gate missing")
    require(auto_main, '"rose_oils": 7', "AUTO Main TDHH count gate missing")
    require(auto_main, "Function 2 completion gate PASS", "AUTO Main Function-2 PASS marker missing")

    for text in (planting, rose_action, rose_recipe, function_two):
        forbid(text, ".pyc", "Function 2 clean runtime must not load legacy pyc")
        forbid(text, "clear_stall_probe_runtime", "Function 2 must not call Dọn quầy runtime")

    print("AUTO MULTI DEV FUNCTION TWO STATIC CONTRACT VERIFIED")
    print("function_2=base-function1-3of4+rose35+snow28+rose-oil7")
    print("architecture=one-recipe-book+one-function2-recovery-manager")
    print("resolution=function2-native1000-only+native500-sale-table-unchanged")
    print("sale_items=tao_say+vai_vang+tinh_dau_hh")
    print("completion=4of4+exact-counts+exact-main")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
