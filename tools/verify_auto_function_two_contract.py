from __future__ import annotations

"""Static contract for guarded AUTO MULTI DEV Function 2."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "components/clientjs-auto/kvtm_automation"
PLANTING = CLEAN / "actions/function_two_planting.py"
FUNCTION_ONE_NAV = CLEAN / "actions/function_one_navigation.py"
PASS_THREE_NAV = CLEAN / "actions/function_one_pass_three_navigation.py"
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
    function_one_nav = read(FUNCTION_ONE_NAV)
    pass_three_nav = read(PASS_THREE_NAV)
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

    # Function-2 planting stays native-1000 only.
    require(planting, 'SNOW_TEMPLATE = "cay_tuyet"', "Function 2 snow template missing")
    require(planting, "ROSE_COUNT = 35", "Function 2 rose count changed")
    require(planting, "SNOW_COUNT = 28", "Function 2 snow count changed")
    require(planting, "if (width, height) != (1000, 1000):", "Function 2 native-1000 gate missing")
    require(planting, "Không chạy bảng 500x500", "Function 2 native-500 fail-close marker missing")
    require(planting, "self.vision.driver.swipe_points(\n                    tuple(path),", "RIPE harvest must start from farm path")
    require(planting, "plant_path = (match.center,) + tuple(path[1:])", "Seed drag must start from verified seed center")

    # Operator-confirmed material choreography:
    # Hồng: main->1, goUp(4), goUp(1), 5 Hồng, down1+XUỐNG->main.
    # Tuyết: main->1, 28 cây, goUp(4)->floor5; no floor7 detour.
    if planting.count("self.function_one_navigation.main_to_floor_1()") < 2:
        raise AssertionError("Hồng và Tuyết phải đều bắt đầu lại từ main -> tầng 1")
    require(planting, "self.function_one_navigation.floor_1_to_floor_6()", "Hồng thiếu route goUp(4)+goUp(1) tới tầng 6")
    require(planting, "self.pass_three_navigation.known_upper_floor_to_main_via_down_floor(", "Hồng tầng 6 chưa dùng goDown(1)+click XUỐNG về main")
    require(planting, "self.function_one_navigation.floor_1_to_floor_5()", "Tuyết chưa goUp(4) thẳng tới tầng 5")
    require(planting, "end_floor=5", "Function 2 material handoff phải ở tầng 5")
    forbid(planting, "self.floors.up(5)", "Function 2 không được goUp(1) năm lần tới tầng 6")
    forbid(planting, "end_floor=7", "Function 2 không được bàn giao candidate tầng 7")
    forbid(planting, "Tuyết tầng 7-11", "Function 2 không được trồng Tuyết từ tầng 7")

    require(function_one_nav, "def floor_1_to_floor_5(self) -> NavigationEvidence:", "Thiếu route floor1->floor5 dùng goUp(4)")
    require(function_one_nav, 'self._gesture(self.UP_FOUR, "floor1-goUp(4)-to-floor5")', "floor1->floor5 không dùng nhánh UP_FOUR AUTO PRO")
    require(function_one_nav, "def floor_1_to_floor_6(self) -> NavigationEvidence:", "Route floor1->floor6 bị mất")
    require(pass_three_nav, "def known_upper_floor_to_main_via_down_floor(", "Thiếu helper tầng trên -> goDown(1)+XUỐNG -> main")
    require(pass_three_nav, "swipe_change = self._settle_down_one(swipe_label)", "Helper về main thiếu goDown(1)")
    require(pass_three_nav, "click_change = self._click_down_floor_if_visible(swipe_label)", "Helper về main thiếu visual click XUỐNG")
    require(pass_three_nav, "self.context.mark_camera_exact_main(", "Helper về main thiếu exact-main proof")

    # Exact-seven TDHH production remains product-proven and retry-bounded.
    require(rose_action, "ROSE_OIL_FLOOR = 5", "TDHH floor changed")
    require(rose_action, 'ROSE_OIL_TEMPLATE = "tinh_dau_hh"', "TDHH product template missing")
    require(rose_action, "TARGET_COUNT = 7", "TDHH target count changed")
    require(rose_action, '"tinh_dau_hh",', "TDHH missing from known production anchors")
    require(rose_action, "for ordinal in range(1, self.TARGET_COUNT + 1):", "Exact-seven TDHH loop missing")
    require(rose_action, "if current_empty >= empty_after:", "TDHH post-drag slot proof missing")
    require(rose_action, "consumed != self.TARGET_COUNT", "TDHH exact-seven final delta proof missing")
    require(rose_action, "Thiếu Hồng/Tuyết", "TDHH material fail-close missing")

    # Recipe owns floor5 production and exact operator return route.
    require(rose_recipe, "self.recovery = RecoveryManager(", "TDHH recovery manager missing")
    require(rose_recipe, 'function_id="function_2"', "TDHH recovery is not Function-2-bound")
    require(rose_recipe, "to_main_routes={5: self._floor_5_to_main}", "TDHH floor5->main route missing")
    require(rose_recipe, "from_main_routes={5: self._main_to_floor_5}", "TDHH main->floor5 recovery route missing")
    require(rose_recipe, "function_one_navigation=automation.function_one_navigation", "Planting chưa nhận Function-1 navigation dùng chung")
    require(rose_recipe, "pass_three_navigation=automation.function_one_pass_three_navigation", "Planting chưa nhận down-floor helper dùng chung")
    require(rose_recipe, "int(materials.end_floor) != 5", "TDHH material contract chưa khóa candidate tầng 5")
    forbid(rose_recipe, "from_floor_to_floor(7, 5", "TDHH không được route candidate 7->5")
    forbid(rose_recipe, "between_floor_routes={(7, 5)", "TDHH recovery không được đăng ký route 7->5")
    require(rose_recipe, "self.recovery.run_production(", "TDHH production bypasses RecoveryManager")
    require(rose_recipe, "close_after_success=False", "TDHH panel is not handed to machine repair")
    require(rose_recipe, "self.auto.machine_repair.repair_after_production(produced)", "TDHH repair handoff missing")
    require(rose_recipe, "known_upper_floor_to_main_via_down_floor(", "TDHH floor5 chưa dùng goDown(1)+click XUỐNG về main")
    require(rose_recipe, "self.recovery.to_main_from_floor(5", "TDHH recipe does not normalize floor5->main")

    require(recipe_book, "self.rose_oil: RoseOilRecipe | None = None", "RecipeBook Function-2 slot missing")
    require(recipe_book, 'if self.function_id == "function_2":', "RecipeBook Function-2 branch missing")
    require(recipe_book, "self.rose_oil = RoseOilRecipe(automation)", "RecipeBook does not construct TDHH recipe")
    require(recipe_book, "self.recovery = self.rose_oil.recovery", "Function 2 does not share TDHH recovery manager")
    require(recipe_book, "recovery=self.recovery", "Inherited recipes do not share Function-2 recovery")

    # Function 1 stays standalone-compatible and Function 2 composes it.
    require(function_one, "recipes: RecipeBook | None = None", "Function 1 RecipeBook injection point missing")
    require(function_one, 'function_id="function_1"', "Function 1 standalone identity changed")
    require(function_one, "progress_steps=3", "Function 1 progress contract changed")
    require(function_one, "total_steps=3", "Function 1 total contract changed")
    require(function_two, "from ...recipes import RecipeBook", "Function 2 RecipeBook import missing")
    require(function_two, "recipes=self.recipes", "Function 2 base does not share RecipeBook")
    require(function_two, "int(result.dried_apples) != 9", "Function 2 base dried-apple count gate missing")
    require(function_two, "int(result.apple_juices) != 9", "Function 2 base apple-juice count gate missing")
    require(function_two, "int(result.cotton_planted) != 27", "Function 2 base cotton count gate missing")
    require(function_two, "int(result.yellow_fabrics) != 9", "Function 2 base yellow-fabric count gate missing")
    require(function_two, "int(extra.rose_planted) != 35", "Function 2 rose completion gate missing")
    require(function_two, "int(extra.snow_planted) != 28", "Function 2 snow completion gate missing")
    require(function_two, "int(extra.queued_count) != 7", "Function 2 TDHH completion gate missing")
    require(function_two, "progress_steps=4", "Function 2 progress 4/4 missing")
    require(function_two, "total_steps=4", "Function 2 total 4/4 missing")

    # Catalog/dispatcher/sale/scheduler contract.
    require(catalog, '"function_2": FunctionSpec(', "Function 2 catalog entry missing")
    require(catalog, 'label="9 Táo sấy - 9 Vải vàng - 7 tinh dầu hoa hồng"', "Function 2 operator label changed")
    require(catalog, 'sale_item_ids=("tao_say", "vai_vang", "tinh_dau_hh")', "Function 2 sale ownership changed")
    require(modules, 'elif spec.runner_key == "function_2":', "Function 2 dispatcher branch missing")
    require(modules, "FunctionTwoWorkflow(self.auto).run()", "Function 2 dispatcher target missing")
    require(sale_workflow, "def _require_function_resolution(self) -> None:", "Function 2 sale resolution gate missing")
    require(sale_workflow, "if native != (1000, 1000):", "Function 2 sale native-1000 check missing")
    require(sale_action, '"tinh_dau_hh": "tinh_dau_hh"', "TDHH selected-item proof missing")
    require(sale_action, "item_ids=self.ITEM_ORDER", "Sale recognition is not Function-bound")
    require(sale_action, "N500_EXACT_TEN_THRESHOLD = 0.78", "Native500 x10 threshold regressed")
    require(sale_action, "N1000_EXACT_TEN_THRESHOLD = 0.95", "Native1000 x10 threshold changed")
    require(auto_main, 'if self.spec.runner_key == "function_2":', "AUTO Main Function-2 completion branch missing")
    require(auto_main, '"roses_planted": 35', "AUTO Main rose count gate missing")
    require(auto_main, '"snow_planted": 28', "AUTO Main snow count gate missing")
    require(auto_main, '"rose_oils": 7', "AUTO Main TDHH count gate missing")

    for text in (planting, rose_action, rose_recipe, function_two):
        forbid(text, ".pyc", "Function 2 clean runtime must not load legacy pyc")
        forbid(text, "clear_stall_probe_runtime", "Function 2 must not call Dọn quầy runtime")

    print("AUTO MULTI DEV FUNCTION TWO STATIC CONTRACT VERIFIED")
    print("function_2=base-function1-3of4+rose35+snow28+rose-oil7")
    print("route=rose-main-1-4-1-return-main+snow-main-1-goUp4-floor5")
    print("tdhh=floor5-production+repair+goDown1+down-floor-main")
    print("resolution=function2-native1000-only+native500-sale-table-unchanged")
    print("completion=4of4+exact-counts+exact-main")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
