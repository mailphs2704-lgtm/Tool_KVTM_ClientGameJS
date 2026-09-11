from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "components/clientjs-auto/kvtm_automation"
AUTOMATION = CLEAN / "automation.py"
ERRORS = CLEAN / "errors.py"
EVENTS = CLEAN / "recovery/events.py"
MODULE_EXECUTION = CLEAN / "recovery/module_execution.py"
NAV = CLEAN / "recovery/navigation.py"
PRODUCTION = CLEAN / "recovery/production.py"
MATERIAL_RECOVERY = CLEAN / "recovery/material_shortage.py"
MANAGER = CLEAN / "recovery/manager.py"
FARM_ROUTES = CLEAN / "actions/farm_routes.py"
COTTON = CLEAN / "actions/cotton_planting.py"
LEGACY = CLEAN / "workflows/production_warehouse_recovery.py"
FUNCTION_ONE = CLEAN / "workflows/auto_function_one/workflow.py"
RECIPE_BOOK = CLEAN / "recipes/book.py"
ROSE_OIL = CLEAN / "recipes/rose_oil.py"
GAME_SESSION = CLEAN / "workflows/game_session/workflow.py"
AUTO_MAIN = CLEAN / "workflows/auto_main/workflow.py"
AUTO_BUILDER_INIT = CLEAN / "workflows/auto_builder/__init__.py"
WORKER = ROOT / "components/clientjs-auto/worker/auto_multi_dev_worker.py"
MULTI_TOOL = ROOT / "source-archive/multi-current/kvtm_multi_tool"
BUILDER_INTEGRATION = MULTI_TOOL / "auto_builder_integration.py"
PROFILE_SETTINGS = MULTI_TOOL / "auto_main_profile_settings.py"


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
    automation = read(AUTOMATION)
    errors = read(ERRORS)
    events = read(EVENTS)
    module_execution = read(MODULE_EXECUTION)
    nav = read(NAV)
    production = read(PRODUCTION)
    material_recovery = read(MATERIAL_RECOVERY)
    manager = read(MANAGER)
    farm_routes = read(FARM_ROUTES)
    cotton = read(COTTON)
    legacy = read(LEGACY)
    function_one = read(FUNCTION_ONE)
    recipe_book = read(RECIPE_BOOK)
    rose_oil = read(ROSE_OIL)
    game_session = read(GAME_SESSION)
    auto_main = read(AUTO_MAIN)
    auto_builder_init = read(AUTO_BUILDER_INIT)
    worker = read(WORKER)
    builder_integration = read(BUILDER_INTEGRATION)
    profile_settings = read(PROFILE_SETTINGS)

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

    # Generic farm-route facade replaces Function-specific route ownership.
    require(farm_routes, "class FarmRouteActions", "Generic FarmRouteActions missing")
    require(farm_routes, "class FarmBoundaryRouteActions", "Generic FarmBoundaryRouteActions missing")
    require(automation, "self.farm_routes = FarmRouteActions(", "Automation generic farm_routes facade missing")
    require(automation, "self.farm_boundary_routes = FarmBoundaryRouteActions(", "Automation generic boundary routes missing")
    require(automation, "self.function_one_navigation = self.farm_routes", "Legacy route alias must share the same object")
    require(automation, "self.function_one_pass_three_navigation = self.farm_boundary_routes", "Legacy boundary alias must share the same object")
    require(nav, "self.auto.farm_routes", "Global Recovery still depends on Function-specific route facade")
    require(nav, "self.auto.farm_boundary_routes", "Global Recovery boundary path is not generic")
    forbid(nav, "self.auto.function_one_navigation", "Global Recovery uses Function-specific route name")
    forbid(nav, "self.auto.function_one_pass_three_navigation", "Global Recovery uses Function-specific boundary route name")
    require(function_one, "self.auto.farm_routes", "Function 1 still calls Function-specific navigation facade")
    require(rose_oil, "self.auto.farm_routes", "TDHH recipe still calls Function-specific navigation facade")
    require(rose_oil, "self.auto.farm_boundary_routes", "TDHH recipe boundary route is not generic")

    # Navigation owns all reusable position recovery and supports injected routes.
    require(nav, "class NavigationRecovery:", "NavigationRecovery missing")
    require(nav, "UNKNOWN_FLOOR_MAIN_RECOVERY_PASSES = 6", "Unknown-floor bound changed")
    require(nav, "def recover_unknown_to_main(", "Unknown->main API missing")
    require(nav, "go_down_one_toward_main(", "Unknown-floor main-boundary recovery missing")
    require(nav, "def to_main_from_floor(", "Floor->main API missing")
    require(nav, "def from_main_to_floor(", "Main->floor API missing")
    require(nav, "def from_floor_to_floor(", "Floor->floor API missing")
    require(nav, "def register_routes(", "Navigation route registration missing")
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

    # Crop Action owns HOW to obtain a real cotton batch; Recovery owns WHY it is
    # needed and navigation/resume policy. Keep this boundary explicit. Check
    # semantic phrases independently so harmless docstring line wrapping cannot
    # break the package gate.
    require(cotton, "def wait_harvest_and_replant_27_cotton(", "Neutral cotton batch Action missing")
    require(
        cotton,
        "Recipe/Recovery chịu trách nhiệm điều hướng và quyết định vì sao cần batch Bông",
        "Cotton Action/Recovery ownership marker missing",
    )
    require(cotton, "not know *why* the batch is needed", "Cotton Action responsibility boundary missing")
    require(material_recovery, "self.auto.cotton_planting.wait_harvest_and_replant_27_cotton()", "Material Recovery does not call neutral cotton Action")
    forbid(material_recovery, "replenish_27_cotton_from_floor_1()", "Recovery still calls recovery-named method inside Actions")

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

    # Manager is the one recovery facade consumed directly by RecipeBook. Recipes
    # may add deterministic routes but must keep the same manager instance.
    require(manager, "class RecoveryManager:", "RecoveryManager missing")
    require(manager, "event_handlers:", "Per-Function event injection missing")
    require(manager, "between_floor_routes:", "Per-Function route injection missing")
    require(manager, "def register_navigation_routes(", "Shared manager route registration missing")
    require(manager, "def recover_unknown_to_floor(", "Manager unknown-floor facade missing")
    require(manager, "def from_floor_to_floor(", "Manager known-floor facade missing")
    require(manager, "def run_module(", "Manager module checkpoint facade missing")
    require(manager, "def run_production(", "Manager production facade missing")

    require(recipe_book, "from ..recovery import RecoveryManager", "RecipeBook recovery import missing")
    require(recipe_book, "self.recovery = recovery or RecoveryManager(",
            "RecipeBook does not share one RecoveryManager")
    require(recipe_book, "recovery=self.recovery", "Recipes are not receiving shared recovery")

    # TDHH classification is explicit: Hồng/Tuyết are planting materials, TDHH
    # itself is a VP product produced by the production action.
    require(rose_oil, "Hồng and Tuyết are crop/material inputs", "TDHH material classification missing")
    require(rose_oil, "TDHH (Tinh dầu hoa hồng) is a finished VP product", "TDHH is not classified as finished VP")
    require(rose_oil, "RoseOilProductionActions", "TDHH VP production action missing")
    require(rose_oil, "auto-recipe-rose-oil-vp-production", "TDHH VP production stage missing")
    require(rose_oil, "recovery=self.recovery", "RoseOilRecipe does not share Function recovery")

    # Startup follows the operator-approved invariant: fresh login/restart begins
    # at MAIN and the worker watches/clears popups continuously for a full minute.
    require(game_session, "POPUP_WATCH_SECONDS = 60.0", "Startup popup watch is not 60 seconds")
    require(game_session, "mark_startup_exact_main", "Startup MAIN contract marker missing")
    forbid(game_session, "go_down_one_toward_main", "Startup must not manufacture MAIN with goDown(1)")

    # Scheduler restart is three-hour, safe-boundary lifecycle only. Emergency
    # mid-Function restart remains a separate durable-checkpoint feature.
    require(auto_main, "CLIENT_RESTART_INTERVAL_SECONDS = 10800.0", "AUTO Main restart is not 3h")
    require(auto_main, "_request_client_restart_at_safe_boundary", "Safe restart boundary API missing")
    require(auto_main, "auto-main-client-restart-pre-sale", "Pre-restart safe sale missing")
    require(auto_main, "skip_initial_sale_once", "Post-restart one-shot sale skip missing")
    forbid(auto_main, "CLIENT_RESTART_INTERVAL_SECONDS = 7200.0", "Old 2h AUTO Main restart remains")

    # Worker is a lifecycle host, not a second recovery engine. Registered errors
    # are handled below it; anything escaping RecoveryManager fails closed.
    require(worker, "except ClientRestartRequested as exc:", "Worker restart lifecycle branch missing")
    require(worker, '"client_restart_requested"', "Worker explicit restart lifecycle event missing")
    require(worker, 'lifecycle_event="client_restart_requested"', "Worker restart supervisor bridge missing")
    require(worker, "unregistered_runtime_error; recovery=fail-close", "Worker fail-close contract missing")
    forbid(worker, "_AUTO_MAIN_SAME_ERROR_LIMIT", "Old catch-all same-error restart loop remains")
    forbid(worker, "_recover_auto_main_to_main_screen", "Worker still owns generic camera recovery")
    forbid(worker, "runtime_error_policy=recover-main-restart", "Worker still advertises pipeline restart recovery")

    # Multi integration owns only scheduled ClientJS lifecycle: exact profile,
    # new worker/Bridge generation and one-shot startup-sale skip.
    require(builder_integration, "_CLIENT_RESTART_INTERVAL_SECONDS = 10800.0", "Multi restart integration is not 3h")
    require(builder_integration, 'lifecycle_event == "client_restart_requested"', "Supervisor lifecycle marker missing")
    require(builder_integration, 'resume["skip_initial_sale_once"] = True', "Restart handoff does not skip duplicate startup sale")
    require(builder_integration, "_start_clean_auto_profile_only(profile_id)", "Restart does not relaunch exact profile")
    forbid(builder_integration, "_CLIENT_RESTART_INTERVAL_SECONDS = 7200.0", "Old 2h integration constant remains")
    forbid(builder_integration, "restart ClientJS=2 giờ", "Old 2h integration UI remains")
    forbid(profile_settings, "restart ClientJS=2 giờ", "Old 2h profile UI remains")

    # Old class remains adapter only; Function 1 composes RecipeBook and must not
    # duplicate unknown-camera or production recovery loops.
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
    print("navigation=canonical-primitives+generic-farm-routes+injectable-recovery-routes")
    print("production=checkpointed-explicit-signals+no-generic-screen-timeout-retry")
    print("material_shortage=crop-action-how+recovery-policy-why")
    print("warehouse_progress=listing-or-gold-collection")
    print("startup=continuous-popup-watch-60s+no-goDown-main-normalize")
    print("tdhh=finished-vp+rose-snow-materials")
    print("scheduled_restart=3h+safe-function-boundary+exact-profile-relaunch")
    print("worker=typed-recovery-boundary+unregistered-fail-close")
    print("auto_builder_import=lazy-runner-no-recovery-cycle")
    print("recipes=share-one-RecoveryManager-per-function")
    print("functions=business-flow-composes-RecipeBook")
    print("legacy-recovery=compatibility-facade-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
