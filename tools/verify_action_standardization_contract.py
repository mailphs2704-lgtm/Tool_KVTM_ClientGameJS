from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "components/clientjs-auto/kvtm_automation"
ACTIONS = CLEAN / "actions"
PLANTING = ACTIONS / "planting.py"
APPLE_SUPPLY = ACTIONS / "apple_supply.py"
ACTIONS_INIT = ACTIONS / "__init__.py"
FARM_ROUTES = ACTIONS / "farm_routes.py"
FUNCTION_ONE_NAV = ACTIONS / "function_one_navigation.py"
FUNCTION_ONE_BOUNDARY_NAV = ACTIONS / "function_one_pass_three_navigation.py"
VP_SALE_TRANSACTION = ACTIONS / "vp_sale_transaction.py"
FUNCTION_TWO_PLANTING = ACTIONS / "function_two_planting.py"
SALE_WORKFLOW = CLEAN / "workflows/auto_vp_sale/workflow.py"
AUTOMATION = CLEAN / "automation.py"
ROSE_OIL_RECIPE = CLEAN / "recipes/rose_oil.py"


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing standardized Action file: {path}")
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
    apple_supply = read(APPLE_SUPPLY)
    actions_init = read(ACTIONS_INIT)
    farm_routes = read(FARM_ROUTES)
    function_one_nav = read(FUNCTION_ONE_NAV)
    function_one_boundary_nav = read(FUNCTION_ONE_BOUNDARY_NAV)
    vp_sale_transaction = read(VP_SALE_TRANSACTION)
    function_two_planting = read(FUNCTION_TWO_PLANTING)
    sale_workflow = read(SALE_WORKFLOW)
    automation = read(AUTOMATION)
    rose_oil_recipe = read(ROSE_OIL_RECIPE)

    # Shared planting geometry owns all currently verified reusable paths.
    for token in (
        "PATH_3 = (",
        "PATH_5 = (",
        "PATH_6 = (",
        "PATH_24 = (",
        "PATH_27 = (",
        "PATH_28 = (",
        "PATH_30 = (",
        "3: PATH_3",
        "6: PATH_6",
        "24: PATH_24",
        "def path_for_count(cls, count: int)",
        "plant_count: int | None = None",
        "replant_path = self.path_for_count(plant_requested)",
    ):
        require(planting, token, f"Shared planting contract missing: {token}")

    # Every generic planting attempt must reopen the picker through the
    # operator-verified click hitbox. The path's first point is drag geometry,
    # not a valid replacement click point. RIPE on attempt 6 must still reopen
    # and plant inside that same attempt.
    for token in (
        "self.vision.driver.click(*self.OPEN_PLANT_POINT)",
        "harvest_path[1] is only a drag waypoint",
        "never require an artificial attempt 7",
        "sau thu hoạch đã mở lại bảng gieo",
        "đã click lại điểm mở chuẩn=",
    ):
        require(
            planting,
            token,
            f"Planting picker contract missing: {token}",
        )
    forbid(
        planting,
        "open_point=first_pot_point",
        "Planting retry regressed to using a drag waypoint as click hitbox",
    )

    # Seed identity is dynamic across accounts/sessions. Page turning is legal
    # only after the existing arrow template proves the seed picker is open.
    for token in (
        'SEED_PANEL_ARROW_TEMPLATE = "next_gieo_trai"',
        "def _find_seed_panel_arrow(",
        "def _prove_seed_picker_open_for_page_turn(",
        "arrow = self._prove_seed_picker_open_for_page_turn()",
        "if arrow is None:",
        "KHÔNG chuyển trang",
        "plant_path = (match.center,) + tuple(replant_path[1:])",
    ):
        require(
            planting,
            token,
            f"Dynamic seed/picker proof contract missing: {token}",
        )

    # Runtime ownership/call chain must stay:
    # RoseOilRecipe -> KVAutomation.planting -> shared PlantingActions method.
    require(
        automation,
        "self.planting = PlantingActions(",
        "KVAutomation no longer owns the shared PlantingActions instance",
    )
    require(
        rose_oil_recipe,
        "planting = self.auto.planting",
        "RoseOilRecipe does not consume KVAutomation.planting",
    )
    if rose_oil_recipe.count("planting.harvest_and_replant_current_view(") != 3:
        raise AssertionError(
            "RoseOilRecipe must route Hồng30, Hồng5 and Tuyết28 through shared planting"
        )
    forbid(
        rose_oil_recipe,
        "PlantingActions(",
        "RoseOilRecipe must not construct a parallel PlantingActions instance",
    )

    # Apple supply keeps crop-specific wait semantics but no longer owns duplicate
    # 30-pot/6-pot geometry or floor navigation.
    require(
        apple_supply,
        "class AppleSupplyActions(PlantingActions):",
        "AppleSupplyActions is not layered over shared PlantingActions",
    )
    require(
        apple_supply,
        "FIVE_FLOOR_PATH = PlantingActions.PATH_30",
        "Apple supply still duplicates the 30-pot path",
    )
    require(
        apple_supply,
        "FLOOR_6_ROW = PlantingActions.PATH_6",
        "Apple supply still duplicates the 6-pot path",
    )
    forbid(apple_supply, "go_up(", "Apple supply must not own floor navigation")
    forbid(apple_supply, "go_down(", "Apple supply must not own floor navigation")

    # Generic farm route files own the real implementation. Historical Function 1
    # files are compatibility wrappers only and must not become a second source.
    require(farm_routes, "class FarmRouteActions(FloorNavigationActions):", "Canonical FarmRouteActions implementation missing")
    require(farm_routes, "class FarmBoundaryRouteActions(FarmRouteActions):", "Canonical FarmBoundaryRouteActions implementation missing")
    for token in (
        "def main_to_floor_1(self)",
        "def floor_1_to_floor_5(self)",
        "def floor_1_to_floor_6(self)",
        "def main_to_floor_2(self)",
        "def main_to_floor_3(self)",
        "def main_to_floor(self, target_floor: int)",
        "def floor_1_to_floor_3(self)",
        "def floor_3_to_main_via_down_floor(self)",
        "def go_down_one_toward_main(self, label: str)",
    ):
        require(farm_routes, token, f"Canonical farm route missing: {token}")
    require(
        function_one_nav,
        "class FunctionOneNavigationActions(FarmRouteActions):",
        "Function 1 navigation is not a compatibility wrapper",
    )
    require(
        function_one_boundary_nav,
        "class FunctionOnePassThreeNavigationActions(FarmBoundaryRouteActions):",
        "Function 1 boundary navigation is not a compatibility wrapper",
    )
    forbid(function_one_nav, "def main_to_floor_1(", "Function 1 wrapper regained route implementation")
    forbid(function_one_boundary_nav, "def floor_1_to_floor_3(", "Function 1 boundary wrapper regained route implementation")

    # One VP listing transaction is a generic Action; AUTO Main is not its owner.
    require(
        vp_sale_transaction,
        "class VpSaleTransactionActions(AutoMainSellingActions):",
        "Generic VP sale transaction facade missing",
    )
    require(
        actions_init,
        "VpSaleTransactionActions",
        "Generic VP sale transaction Action is not exported",
    )
    require(
        sale_workflow,
        "from ...actions.vp_sale_transaction import VpSaleTransactionActions",
        "Sale Module does not use the neutral VP transaction facade",
    )
    require(
        sale_workflow,
        "self.sale = VpSaleTransactionActions(",
        "Sale Module does not instantiate the neutral VP transaction Action",
    )
    forbid(
        sale_workflow,
        "AutoMainSellingActions",
        "Sale Module regressed to AUTO Main-specific Action naming",
    )

    # Business sale loop belongs to the Module, not the transaction Action.
    require(sale_workflow, "VIEW_COUNT = 5", "Sale Module is not scanning five views")
    require(sale_workflow, "self.auto.stall.next_view()", "Sale Module lost two-swipe view Action")
    require(
        sale_workflow,
        "collect_own_stall_gold(maximum=8)",
        "Sale Module no longer checks visible sold-gold slots first",
    )
    require(
        sale_workflow,
        "self._check_advertisement_checkpoint(view)",
        "Sale Module no longer checks QC after gold",
    )

    # Function 2 planting choreography remains retired from Actions.
    require(
        function_two_planting,
        "Deprecated compatibility facade",
        "FunctionTwoPlantingActions is no longer marked compatibility-only",
    )
    require(
        function_two_planting,
        "raise RuntimeError(",
        "Legacy Function 2 choreography can run again from Actions",
    )
    require(
        function_two_planting,
        "Dùng RoseOilRecipe",
        "Legacy Function 2 planting file does not point to Recipe ownership",
    )

    print("AUTO ACTION STANDARDIZATION CONTRACT VERIFIED")
    print("planting=shared-paths-3-5-6-24-27-28-30+split-harvest-replant+verified-picker-click+arrow-proof-page-gate+same-attempt-replant")
    print("apple-supply=shared-geometry+crop-wait-only")
    print("farm-routes=generic-canonical+function1-wrappers-only")
    print("vp-sale=neutral-transaction-action+five-view-module")
    print("function-two-planting=compatibility-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
