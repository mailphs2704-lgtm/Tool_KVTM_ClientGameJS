from __future__ import annotations

"""Static contract for standardized AUTO MULTI DEV Function 2."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "components/clientjs-auto/kvtm_automation"
PLANTING = CLEAN / "actions/planting.py"
LEGACY_F2_PLANTING = CLEAN / "actions/function_two_planting.py"
FARM_ROUTES = CLEAN / "actions/farm_routes.py"
ROSE_OIL_ACTION = CLEAN / "actions/rose_oil_production.py"
ROSE_OIL_RECIPE = CLEAN / "recipes/rose_oil.py"
RECIPE_BOOK = CLEAN / "recipes/book.py"
FUNCTION_ONE = CLEAN / "workflows/auto_function_one/workflow.py"
FUNCTION_TWO = CLEAN / "workflows/auto_function_two/workflow.py"
CATALOG = CLEAN / "workflows/auto_builder/catalog.py"
MODULES = CLEAN / "workflows/auto_builder/modules.py"
SALE_WORKFLOW = CLEAN / "workflows/auto_vp_sale/workflow.py"
SALE_FACADE = CLEAN / "actions/vp_sale_transaction.py"
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
    legacy_planting = read(LEGACY_F2_PLANTING)
    farm_routes = read(FARM_ROUTES)
    rose_action = read(ROSE_OIL_ACTION)
    rose_recipe = read(ROSE_OIL_RECIPE)
    recipe_book = read(RECIPE_BOOK)
    function_one = read(FUNCTION_ONE)
    function_two = read(FUNCTION_TWO)
    catalog = read(CATALOG)
    modules = read(MODULES)
    sale_workflow = read(SALE_WORKFLOW)
    sale_facade = read(SALE_FACADE)
    auto_main = read(AUTO_MAIN)

    # Crop geometry is shared; Function 2 choreography must not live in Actions.
    require(planting, 'SNOW_TEMPLATE = "cay_tuyet"', "Shared snow template missing")
    require(planting, "PATH_5 = (", "Shared 5-pot path missing")
    require(planting, "PATH_28 = (", "Shared 28-pot path missing")
    require(planting, "PATH_30 = (", "Shared 30-pot path missing")
    require(planting, "def harvest_and_replant_current_view", "Shared current-view planting Action missing")
    require(legacy_planting, "LEGACY compatibility facade only", "Function 2 planting compatibility marker missing")
    require(legacy_planting, "FunctionTwoPlantingActions đã retired khỏi runtime chuẩn", "Legacy Function 2 planting is not fail-closed")
    forbid(legacy_planting, "self.function_one_navigation", "Legacy Function 2 Action regained navigation choreography")
    forbid(legacy_planting, "self.pass_three_navigation", "Legacy Function 2 Action regained boundary choreography")

    # Shared semantic farm routes own movement used by RoseOilRecipe.
    require(farm_routes, "class FarmRouteActions", "Generic farm route Action missing")
    require(farm_routes, "def main_to_floor_1", "MAIN->floor1 route missing")
    require(farm_routes, "def floor_1_to_floor_5", "floor1->floor5 route missing")
    require(farm_routes, "def floor_1_to_floor_6", "floor1->floor6 route missing")
    require(farm_routes, "def known_upper_floor_to_main_via_down_floor", "Upper-floor->MAIN boundary route missing")

    # TDHH is a finished VP transaction, not a crop Action. Function 3 Step 4
    # legitimately reuses the same queue engine for 9 items, but Function 2 must
    # stay hard-bound to the explicit produce_7 wrapper.
    require(rose_action, "class RoseOilProductionActions(ProductionPanelActions):", "TDHH production does not use shared panel engine")
    require(rose_action, "ROSE_OIL_FLOOR = 5", "TDHH floor changed")
    require(rose_action, 'ROSE_OIL_TEMPLATE = "tinh_dau_hh"', "TDHH product template missing")
    require(rose_action, "TARGET_COUNT = 7", "TDHH Function-2 target count changed")
    require(rose_action, "STEP4_TARGET_COUNT = 9", "TDHH Step-4 shared target missing")
    require(rose_action, "DRAG_ATTEMPTS = 3", "TDHH drag retry changed")
    require(rose_action, "VERIFY_RECHECKS = 4", "TDHH verify retry changed")
    require(rose_action, "def _produce_rose_oils(", "Shared exact-count TDHH queue engine missing")
    require(rose_action, "if requested not in (self.TARGET_COUNT, self.STEP4_TARGET_COUNT):", "TDHH exact-count allowlist missing")
    require(rose_action, "for ordinal in range(1, requested + 1):", "TDHH exact-count queue loop missing")
    require(rose_action, "if queued != requested or consumed != requested:", "TDHH exact-count postcheck missing")
    require(rose_action, "def produce_7_rose_oils(", "Function-2 exact-seven TDHH wrapper missing")
    require(rose_action, "target_count=self.TARGET_COUNT", "Function-2 wrapper no longer binds exact seven")
    require(rose_action, "Thiếu Hồng/Tuyết", "TDHH material fail-close missing")

    # RoseOilRecipe owns business order; raw input stays in Actions.
    require(rose_recipe, "ROSE_REQUIRED = 35", "Rose material count changed")
    require(rose_recipe, "SNOW_REQUIRED = 28", "Snow material count changed")
    require(rose_recipe, "ROSE_FIRST_SEGMENT = 30", "Rose first segment changed")
    require(rose_recipe, "ROSE_FINAL_SEGMENT = 5", "Rose final segment changed")
    require(rose_recipe, "self.production = automation.rose_oil_production", "TDHH Recipe bypasses KVAutomation production facade")
    require(rose_recipe, "recovery: RecoveryManager | None = None", "TDHH Recipe shared recovery injection missing")
    require(rose_recipe, "self.recovery = recovery or RecoveryManager(", "TDHH Recipe recovery fallback missing")
    require(rose_recipe, "self.recovery.register_navigation_routes(", "TDHH floor5 recovery routes not registered")
    require(rose_recipe, "to_main_routes={5: self._floor_5_to_main}", "TDHH floor5->MAIN route missing")
    require(rose_recipe, "from_main_routes={5: self._main_to_floor_5}", "TDHH MAIN->floor5 route missing")
    require(rose_recipe, "if (width, height) != (1000, 1000):", "Function 2 native-1000 material gate missing")
    require(rose_recipe, "planting.harvest_and_replant_current_view(", "TDHH Recipe does not use shared PlantingActions")
    require(rose_recipe, "nav.floor_1_to_floor_6()", "Rose material route to floor6 missing")
    require(rose_recipe, "upper_nav.known_upper_floor_to_main_via_down_floor(", "Rose material return-to-MAIN route missing")
    require(rose_recipe, "nav.floor_1_to_floor_5()", "Snow handoff to floor5 missing")
    require(rose_recipe, "self.recovery.run_production(", "TDHH production bypasses RecoveryManager")
    require(rose_recipe, "self.production.produce_7_rose_oils(", "Function 2 no longer calls exact-seven TDHH wrapper")
    require(rose_recipe, "close_after_success=False", "TDHH panel handoff to repair missing")
    require(rose_recipe, "self.auto.machine_repair.repair_after_production(produced)", "TDHH repair handoff missing")
    require(rose_recipe, 'self.recovery.to_main_from_floor(5, "TDHH recipe: cuối production")', "TDHH does not return floor5->MAIN")
    forbid(rose_recipe, "produce_9_rose_oils(", "Function 2 must never call Step-4 exact-nine TDHH wrapper")
    forbid(rose_recipe, "driver.click(", "TDHH Recipe contains raw click")
    forbid(rose_recipe, "driver.swipe(", "TDHH Recipe contains raw swipe")
    forbid(rose_recipe, "FunctionTwoPlantingActions", "TDHH Recipe uses retired Function-specific planting Action")

    # One RecipeBook / RecoveryManager per Function 2.
    require(recipe_book, "self.recovery = recovery or RecoveryManager(", "RecipeBook shared RecoveryManager missing")
    require(recipe_book, 'if self.function_id == "function_2":', "RecipeBook Function-2 branch missing")
    require(recipe_book, "self.rose_oil = RoseOilRecipe(", "RecipeBook TDHH Recipe missing")
    require(recipe_book, "recovery=self.recovery", "RecipeBook does not inject shared recovery into product Recipes")
    forbid(recipe_book, "self.recovery = self.rose_oil.recovery", "RecipeBook regressed to TDHH-owned RecoveryManager")

    # Function 2 composes Function 1 core, consumes known floor3 handoff, then TDHH.
    require(function_one, "normalize_end_to_main: bool = True", "Function 1 standalone normalization contract changed")
    require(function_two, "self.recipes = RecipeBook(", "Function 2 RecipeBook missing")
    require(function_two, 'function_id="function_2"', "Function 2 RecipeBook identity changed")
    require(function_two, "recipes=self.recipes", "Function 2 base does not share RecipeBook")
    require(function_two, "self.recovery = self.recipes.recovery", "Function 2 does not use shared recovery")
    require(function_two, "base = self.base.run(normalize_end_to_main=False)", "Function 2 does not preserve base floor3 handoff")
    require(function_two, "def _base_handoff_to_main", "Function 2 known-floor handoff helper missing")
    require(function_two, "self.recovery.to_main_from_floor(", "Function 2 handoff does not use deterministic known-floor recovery")
    require(function_two, "3,\n            \"Function 2 handoff sau Vải vàng\"", "Function 2 handoff is not bound to floor3")
    require(function_two, "extra = self.rose_oil.run_from_main(count=7)", "Function 2 TDHH stage missing")
    require(function_two, "int(extra.rose_planted) != 35", "Function 2 rose completion gate missing")
    require(function_two, "int(extra.snow_planted) != 28", "Function 2 snow completion gate missing")
    require(function_two, "int(extra.queued_count) != 7", "Function 2 TDHH completion gate missing")
    require(function_two, "progress_steps=4", "Function 2 progress 4/4 missing")
    require(function_two, "total_steps=4", "Function 2 total 4/4 missing")
    forbid(function_two, "recover_unknown_to_main(", "Known floor3 handoff regressed to unknown-camera recovery")

    # Catalog/dispatcher/sale/scheduler remain Function-bound.
    require(catalog, '"function_2": FunctionSpec(', "Function 2 catalog entry missing")
    require(catalog, 'sale_item_ids=("tao_say", "vai_vang", "tinh_dau_hh")', "Function 2 sale ownership changed")
    require(modules, 'elif runner_key == "function_2":', "Function 2 cached dispatcher branch missing")
    require(modules, "workflow = FunctionTwoWorkflow(self.auto)", "Function 2 cached dispatcher target missing")
    require(modules, "result = self._workflow(spec.runner_key).run()", "Function dispatcher does not reuse in-flight workflow")
    require(modules, "workflow.recovery.commit_cycle()", "Function dispatcher cannot commit completed cycle")
    require(sale_workflow, "def _require_function_resolution(self) -> None:", "Function 2 sale resolution gate missing")
    require(sale_workflow, "if native != (1000, 1000):", "Function 2 sale native-1000 check missing")
    require(sale_workflow, "VpSaleTransactionActions(", "Sale workflow does not use neutral VP transaction facade")
    require(sale_facade, "class VpSaleTransactionActions(AutoMainSellingActions):", "Neutral VP sale facade missing")
    require(auto_main, 'if self.spec.runner_key == "function_2":', "AUTO Main Function-2 completion branch missing")
    require(auto_main, '"roses_planted": 35', "AUTO Main rose count gate missing")
    require(auto_main, '"snow_planted": 28', "AUTO Main snow count gate missing")
    require(auto_main, '"rose_oils": 7', "AUTO Main TDHH count gate missing")

    for text in (rose_action, rose_recipe, function_two):
        forbid(text, ".pyc", "Function 2 clean runtime must not load legacy pyc")
        forbid(text, "clear_stall_probe_runtime", "Function 2 must not call Dọn quầy runtime")

    print("AUTO MULTI DEV FUNCTION TWO STATIC CONTRACT VERIFIED")
    print("function2=shared-function1-core+known-floor3-handoff+rose-oil-recipe")
    print("materials=rose35+snow28-via-shared-planting-actions")
    print("tdhh=function2-exact7-wrapper+shared-exact-count-engine+step4-exact9-compatible")
    print("recovery=one-shared-manager-per-function2")
    print("legacy_function2_planting=compatibility-only")
    print("resolution=function2-materials-and-sale-native1000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())