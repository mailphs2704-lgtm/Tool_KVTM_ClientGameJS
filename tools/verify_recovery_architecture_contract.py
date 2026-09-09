from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "components/clientjs-auto/kvtm_automation"
ERRORS = CLEAN / "errors.py"
EVENTS = CLEAN / "recovery/events.py"
NAV = CLEAN / "recovery/navigation.py"
PRODUCTION = CLEAN / "recovery/production.py"
MANAGER = CLEAN / "recovery/manager.py"
LEGACY = CLEAN / "workflows/production_warehouse_recovery.py"
FUNCTION_ONE = CLEAN / "workflows/auto_function_one/workflow.py"
RECIPE_BOOK = CLEAN / "recipes/book.py"


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing recovery architecture file: {path}")
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
    errors = read(ERRORS)
    events = read(EVENTS)
    nav = read(NAV)
    production = read(PRODUCTION)
    manager = read(MANAGER)
    legacy = read(LEGACY)
    function_one = read(FUNCTION_ONE)
    recipe_book = read(RECIPE_BOOK)

    # errors.py declares signals only.
    require(errors, "class WrongProductionMachine(NavigationError):", "Wrong-machine signal missing")
    require(errors, "class InventoryFull(TransactionError):", "Inventory-full signal missing")
    forbid(errors, "RecoveryManager", "errors.py contains policy")
    forbid(errors, "go_down_one_toward_main", "errors.py contains navigation")

    # recovery/events.py is the extension point for Function/Recipe observers.
    require(events, "class RecoveryEventKind(str, Enum):", "Typed event kind missing")
    require(events, "class RecoveryEvent:", "Typed recovery event missing")
    for token in (
        "UNKNOWN_CAMERA", "WRONG_PRODUCTION_MACHINE", "INVENTORY_FULL",
        "MAIN_PROVEN", "FLOOR_REENTERED", "RECOVERY_EXHAUSTED",
    ):
        require(events, token, f"Recovery event missing: {token}")

    # Navigation owns all reusable position recovery and supports injected routes.
    require(nav, "class NavigationRecovery:", "NavigationRecovery missing")
    require(nav, "UNKNOWN_FLOOR_MAIN_RECOVERY_PASSES = 6", "Unknown-floor bound changed")
    require(nav, "def recover_unknown_to_main(", "Unknown->main API missing")
    require(nav, "go_down_one_toward_main(", "Unknown-floor main-boundary recovery missing")
    require(nav, "def to_main_from_floor(", "Floor->main API missing")
    require(nav, "def from_main_to_floor(", "Main->floor API missing")
    require(nav, "def from_floor_to_floor(", "Floor->floor API missing")
    require(nav, "to_main_routes:", "Injected to-main routes missing")
    require(nav, "from_main_routes:", "Injected from-main routes missing")
    require(nav, "between_floor_routes:", "Injected between-floor routes missing")

    # Production catches only recoverable business/navigation signals.
    require(production, "class ProductionRecovery:", "ProductionRecovery missing")
    require(production, "except WrongProductionMachine as exc:", "Wrong-machine policy missing")
    require(production, "except InventoryFull as exc:", "Inventory-full policy missing")
    forbid(production, "except ScreenTimeout", "Generic ScreenTimeout swallowed by recovery")
    require(production, "self.navigation.recover_unknown_to_floor(", "Wrong machine not routed through nav recovery")
    require(production, "AutoVpSaleWorkflow(", "Warehouse-full sale recovery missing")

    # Manager is the one recovery facade consumed directly by RecipeBook. Functions
    # receive the same manager through their RecipeBook instead of rebuilding policy.
    require(manager, "class RecoveryManager:", "RecoveryManager missing")
    require(manager, "event_handlers:", "Per-Function event injection missing")
    require(manager, "between_floor_routes:", "Per-Function route injection missing")
    require(manager, "def recover_unknown_to_floor(", "Manager unknown-floor facade missing")
    require(manager, "def from_floor_to_floor(", "Manager known-floor facade missing")
    require(manager, "def run_production(", "Manager production facade missing")

    require(recipe_book, "from ..recovery import RecoveryManager", "RecipeBook recovery import missing")
    require(recipe_book, "self.recovery = recovery or RecoveryManager(",
            "RecipeBook does not share one RecoveryManager")

    # Old class remains adapter only; new Function 1 must compose RecipeBook and
    # must not duplicate unknown-camera or production recovery loops.
    require(legacy, "self.manager = RecoveryManager(", "Legacy adapter is not delegated")
    forbid(legacy, "except WrongProductionMachine", "Wrong-machine policy duplicated in legacy adapter")
    forbid(legacy, "except InventoryFull", "Inventory-full policy duplicated in legacy adapter")
    require(function_one, "from ...recipes import RecipeBook", "Function 1 does not use standardized recipes")
    require(function_one, "self.recovery = self.recipes.recovery", "Function 1 does not share recipe recovery")
    forbid(function_one, "ProductionWarehouseRecovery", "Function 1 still imports legacy recovery")
    forbid(function_one, "go_down_one_toward_main(", "Function 1 embeds unknown-camera algorithm")
    forbid(function_one, "self.recovery.run_production(", "Function 1 embeds production recovery")

    print("AUTO MULTI DEV RECOVERY ARCHITECTURE CONTRACT VERIFIED")
    print("errors=signals-only")
    print("events=typed-observer-hooks")
    print("navigation=centralized+injectable-routes")
    print("production=explicit-signals-only+no-generic-screen-timeout-retry")
    print("recipes=share-one-RecoveryManager-per-function")
    print("functions=business-flow-composes-RecipeBook")
    print("legacy-recovery=compatibility-facade-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
