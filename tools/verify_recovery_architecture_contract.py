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
POPUP = CLEAN / "actions/popup.py"
PRODUCTION_PANEL = CLEAN / "actions/production_panel.py"


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


def section_between(text: str, start_token: str, end_token: str) -> str:
    start = text.find(start_token)
    if start < 0:
        raise AssertionError(f"Missing section start: {start_token}")
    end = text.find(end_token, start + len(start_token))
    if end < 0:
        raise AssertionError(f"Missing section end: {end_token}")
    return text[start:end]


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
    popup = read(POPUP)
    production_panel = read(PRODUCTION_PANEL)

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

    inventory_recovery = section_between(
        production,
        "        def recover_inventory_full(",
        "        return self.executor.run(",
    )
    require(inventory_recovery, "sale_wait_round = 0", "Warehouse-full recovery wait counter missing")
    require(inventory_recovery, "while True:", "Warehouse-full sale recovery must be unbounded")
    require(inventory_recovery, "self.context.ensure_running()", "Unbounded warehouse recovery must remain stoppable")
    require(inventory_recovery, "if sold > 0:", "Warehouse recovery must wait for a real x10 listing")
    require(
        inventory_recovery,
        "tiếp tục quét 5 View + QC cho tới khi người mua tạo ô trống",
        "Warehouse recovery no-progress continuation marker missing",
    )
    forbid(
        inventory_recovery,
        "raise ScreenTimeout(",
        "Warehouse-full recovery must not fail merely because Sale has no progress yet",
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
    # itself is a finished VP produced through the resident automation facade.
    # Recipe code must not import or instantiate the concrete Production Action.
    require(rose_oil, "Hồng and Tuyết are crop/material inputs", "TDHH material classification missing")
    require(rose_oil, "TDHH (Tinh dầu hoa hồng) is a finished VP product", "TDHH is not classified as finished VP")
    require(rose_oil, "self.production = automation.rose_oil_production", "TDHH recipe is not using the resident production facade")
    require(rose_oil, "auto-recipe-rose-oil-vp-production", "TDHH VP production stage missing")
    require(rose_oil, "producer=lambda: self.production.produce_7_rose_oils(", "TDHH x7 producer handoff missing")
    require(rose_oil, "self.recovery = recovery or RecoveryManager(", "RoseOilRecipe recovery injection/fallback missing")
    require(rose_oil, 'if self.recovery.function_id != "function_2":', "RoseOilRecipe recovery ownership guard missing")
    forbid(rose_oil, "from ..actions.rose_oil_production import RoseOilProductionActions", "Recipe imports concrete TDHH Production Action")

    # Startup follows the operator-approved invariant: fresh login/restart begins
    # at MAIN and the worker watches/clears popups continuously for a full minute.
    require(game_session, "POPUP_WATCH_SECONDS = 60.0", "Startup popup watch is not 60 seconds")
    require(game_session, "mark_startup_exact_main", "Startup MAIN contract marker missing")
    forbid(game_session, "go_down_one_toward_main", "Startup must not manufacture MAIN with goDown(1)")

    # ClientJS restart is blocked at scheduler, worker and Multi supervisor.
    require(auto_main, "CLIENT_RESTART_INTERVAL_SECONDS = 0.0", "AUTO Main restart is not blocked")
    require(auto_main, "GLOBAL_RECOVERY_LIMIT = 3", "Global fallback bound missing")
    require(auto_main, "escape_three_then_stay(", "Global fallback escape sequence missing")
    require(auto_main, "recover_unknown_to_main(", "Global fallback exact-main proof missing")
    require(auto_main, "self.friend_refresh.run(", "Global fallback friend refresh missing")
    require(auto_main, "continue", "Global fallback does not retry same Function loop")
    forbid(auto_main, "ClientRestartRequested", "AUTO Main can still request ClientJS restart")

    require(popup, "def escape_three_then_stay(", "ESC/stay popup primitive missing")
    require(popup, "for ordinal in range(1, 4):", "Fallback does not send exactly three ESC keys")
    require(popup, "stay_point = (573, 605)", "Operator-supplied Ở lại point missing")
    require(
        production_panel,
        "Probe a fresh frame before every",
        "VP collector does not probe full warehouse between clicks",
    )
    require(
        production_panel,
        "self._raise_inventory_full(label)",
        "VP collector does not hand full warehouse to typed recovery",
    )

    forbid(worker, "ClientRestartRequested", "Worker restart lifecycle branch remains")
    forbid(worker, '"client_restart_requested"', "Worker still emits restart lifecycle")
    require(worker, "client_restart=BLOCK", "Worker blocked-restart marker missing")
    require(
        worker,
        "unregistered_error=ESCx3->stay->exact-main->friend1->resume-same-loop",
        "Worker global fallback contract marker missing",
    )
    require(worker, "unregistered_runtime_error; recovery=fail-close", "Outer worker fail-close contract missing")

    require(builder_integration, "_CLIENT_RESTART_INTERVAL_SECONDS = 0.0", "Multi restart interval is not blocked")
    require(builder_integration, "scheduled_restart = False", "Multi supervisor restart branch is not blocked")
    require(profile_settings, "restart ClientJS=BLOCK (3h + lỗi)", "Profile UI does not show blocked restart policy")

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
    print("warehouse_progress=unbounded-sale+qc-until-real-x10-listing")
    print("startup=continuous-popup-watch-60s+no-goDown-main-normalize")
    print("tdhh=finished-vp+rose-snow-materials+resident-production-facade")
    print("client_restart=blocked-3h-and-error")
    print("worker=typed-checkpoint-first+global-fallback+outer-fail-close")
    print("auto_builder_import=lazy-runner-no-recovery-cycle")
    print("recipes=share-one-RecoveryManager-per-function")
    print("functions=business-flow-composes-RecipeBook")
    print("legacy-recovery=compatibility-facade-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
