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

    # Shared planting geometry owns all currently verified reusable paths.
    for token in (
        "PATH_5 = (",
        "PATH_6 = (",
        "PATH_27 = (",
        "PATH_28 = (",
        "PATH_30 = (",
        "6: PATH_6",
        "def path_for_count(cls, count: int)",
    ):
        require(planting, token, f"Shared planting contract missing: {token}")

    # Every generic planting attempt must reopen the picker by clicking the
    # first real pot in the selected path. After a RIPE harvest the old panel is
    # gone, so a retry may not rely on the historical fixed picker coordinate.
    for token in (
        "first_pot_point = tuple(selected_path[1])",
        "open_point=first_pot_point",
        "đã click lại chậu đầu=",
    ):
        require(
            planting,
            token,
            f"Planting retry does not reopen from the first pot: {token}",
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
    print("planting=shared-paths-5-6-27-28-30+retry-first-pot-click")
    print("apple-supply=shared-geometry+crop-wait-only")
    print("farm-routes=generic-canonical+function1-wrappers-only")
    print("vp-sale=neutral-transaction-action+five-view-module")
    print("function-two-planting=compatibility-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
