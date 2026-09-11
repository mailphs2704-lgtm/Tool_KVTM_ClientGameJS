from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "components/clientjs-auto/kvtm_automation"
ERRORS = CLEAN / "errors.py"
EVENTS = CLEAN / "recovery/events.py"
MODULE_EXECUTION = CLEAN / "recovery/module_execution.py"
NAV = CLEAN / "recovery/navigation.py"
PRODUCTION = CLEAN / "recovery/production.py"
MANAGER = CLEAN / "recovery/manager.py"
LEGACY = CLEAN / "workflows/production_warehouse_recovery.py"
FUNCTION_ONE = CLEAN / "workflows/auto_function_one/workflow.py"
RECIPE_BOOK = CLEAN / "recipes/book.py"
AUTO_BUILDER_INIT = CLEAN / "workflows/auto_builder/__init__.py"


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


def forbid_top_level_import_from(text: str, module_name: str, message: str) -> None:
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == module_name:
            raise AssertionError(message)


def main() -> int:
    errors = read(ERRORS)
    events = read(EVENTS)
    module_execution = read(MODULE_EXECUTION)
    nav = read(NAV)
    production = read(PRODUCTION)
    manager = read(MANAGER)
    legacy = read(LEGACY)
    function_one = read(FUNCTION_ONE)
    recipe_book = read(RECIPE_BOOK)
    auto_builder_init = read(AUTO_BUILDER_INIT)

    # errors.py declares signals only.
    require(errors, "class WrongProductionMachine(NavigationError):", "Wrong-machine signal missing")
    require(errors, "class InventoryFull(TransactionError):", "Inventory-full signal missing")
    forbid(errors, "RecoveryManager", "errors.py contains policy")
    forbid(errors, "go_down_one_toward_main", "errors.py contains navigation")

    # recovery/events.py is the extension point for Function/Recipe observers.
    require(events, "class RecoveryEventKind(str, Enum):", "Typed event kind missing")
    require(events, "class RecoveryEvent:", "Typed recovery event missing")
    for token in (
        "MODULE_STARTED", "MODULE_INTERRUPTED", "MODULE_RESUMED", "MODULE_COMPLETED",
        "UNKNOWN_CAMERA", "WRONG_PRODUCTION_MACHINE", "INVENTORY_FULL",
        "MAIN_PROVEN", "FLOOR_REENTERED", "RECOVERY_EXHAUSTED",
    ):
        require(events, token, f"Recovery event missing: {token}")

    # Generic module executor owns the in-flight checkpoint. It may only recover
    # exception types explicitly registered by the module policy.
    require(module_execution, "class ModuleCheckpoint:", "ModuleCheckpoint missing")
    require(module_execution, "class ModuleRecoveryExecutor:", "ModuleRecoveryExecutor missing")
    require(module_execution, "def interrupted(self, exc: Exception)", "Checkpoint interruption update missing")
    require(module_execution, "handler = self._select_handler(exc, handlers)", "Typed handler dispatch missing")
    require(module_execution, "if handler is None:", "Unregistered errors are not fail-close")
    require(
        module_execution,
        "GIỮ NGUYÊN module, chưa trả control về Function/AutoMain",
        "Module checkpoint does not explicitly preserve scheduler boundary",
    )
    require(
        module_execution,
        "chạy tiếp cùng module trước khi cho phép vòng Function mới",
        "Module resume contract missing",
    )

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

    # Production registers only explicit recoverable signals with the generic
    # module executor. Generic ScreenTimeout is never a registered handler.
    require(production, "class ProductionRecovery:", "ProductionRecovery missing")
    require(production, "ModuleRecoveryExecutor(", "Production is not checkpointed as a module")
    require(production, "(WrongProductionMachine, recover_wrong_machine)", "Wrong-machine handler missing")
    require(production, "(InventoryFull, recover_inventory_full)", "Inventory-full handler missing")
    forbid(production, "(ScreenTimeout,", "Generic ScreenTimeout registered as recoverable")
    require(production, "self.navigation.recover_unknown_to_floor(", "Wrong machine not routed through nav recovery")
    require(production, "AutoVpSaleWorkflow(", "Warehouse-full sale recovery missing")
    require(
        production,
        "if sold <= 0 and collected <= 0:",
        "Warehouse recovery must accept either listing or gold-collection progress",
    )

    # Recovery imports auto_builder.catalog for Function sale metadata. The
    # package initializer must stay side-effect free: eagerly importing runner
    # creates recovery -> runner -> FunctionOne -> recipes -> recovery.
    require(auto_builder_init, "def __getattr__(name: str):", "AUTO Builder lazy export hook missing")
    require(auto_builder_init, "install_function_loop_delay(AutoBuilderRunner)", "Lazy Builder runner patch missing")
    forbid_top_level_import_from(
        auto_builder_init,
        "runner",
        "AUTO Builder __init__ eagerly imports runner and can recreate recovery circular import",
    )
    forbid_top_level_import_from(
        auto_builder_init,
        "loop_delay_patch",
        "AUTO Builder __init__ eagerly imports loop-delay patch; keep Builder runtime lazy",
    )

    # Manager is the one recovery facade consumed directly by RecipeBook. Functions
    # receive the same manager through their RecipeBook instead of rebuilding policy.
    require(manager, "class RecoveryManager:", "RecoveryManager missing")
    require(manager, "event_handlers:", "Per-Function event injection missing")
    require(manager, "between_floor_routes:", "Per-Function route injection missing")
    require(manager, "def recover_unknown_to_floor(", "Manager unknown-floor facade missing")
    require(manager, "def from_floor_to_floor(", "Manager known-floor facade missing")
    require(manager, "def run_module(", "Manager module checkpoint facade missing")
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
    print("events=typed-observer-hooks+module-lifecycle")
    print("module_executor=checkpointed+typed-handler-only+no-scheduler-return-on-recovery")
    print("navigation=centralized+injectable-routes")
    print("production=checkpointed-explicit-signals+no-generic-screen-timeout-retry")
    print("warehouse_progress=listing-or-gold-collection")
    print("auto_builder_import=lazy-runner-no-recovery-cycle")
    print("recipes=share-one-RecoveryManager-per-function")
    print("functions=business-flow-composes-RecipeBook")
    print("legacy-recovery=compatibility-facade-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
