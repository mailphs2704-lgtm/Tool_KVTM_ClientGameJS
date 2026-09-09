from __future__ import annotations

import ast
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "components/clientjs-auto/kvtm_automation"
ACTION = CLEAN / "actions/production.py"
AUTOMATION = CLEAN / "automation.py"
WORKFLOW = CLEAN / "workflows/auto_apple_dryer/workflow.py"
FUNCTION_ONE = CLEAN / "workflows/auto_function_one/workflow.py"
FUNCTION_NAV = CLEAN / "actions/function_one_navigation.py"
PASS_THREE_NAV = CLEAN / "actions/function_one_pass_three_navigation.py"
APPLE_JUICE = CLEAN / "actions/apple_juice_production.py"
YELLOW_FABRIC = CLEAN / "actions/yellow_fabric_production.py"
COTTON = CLEAN / "actions/cotton_planting.py"
MACHINE_REPAIR = CLEAN / "actions/machine_repair.py"
ERRORS = CLEAN / "errors.py"
RECOVERY_EVENTS = CLEAN / "recovery/events.py"
RECOVERY_NAV = CLEAN / "recovery/navigation.py"
RECOVERY_PRODUCTION = CLEAN / "recovery/production.py"
RECOVERY_MANAGER = CLEAN / "recovery/manager.py"
LEGACY_RECOVERY = CLEAN / "workflows/production_warehouse_recovery.py"
RECIPE_BOOK = CLEAN / "recipes/book.py"
RECIPE_DRIED_APPLE = CLEAN / "recipes/dried_apple.py"
RECIPE_APPLE_JUICE = CLEAN / "recipes/apple_juice.py"
RECIPE_YELLOW_FABRIC = CLEAN / "recipes/yellow_fabric.py"
DOWN_FLOOR_DETECTOR = CLEAN / "runtime/down_floor_button.py"
MULTI_DEV_DRIED_APPLE = ROOT / "components/clientjs-auto/assets/items/tao_say.png"
MULTI_DEV_EMPTY_SLOT = ROOT / "components/clientjs-auto/assets/items/o_trong.png"
MULTI_DEV_COTTON = ROOT / "components/clientjs-auto/assets/items/cay_bong.png"
MULTI_DEV_YELLOW_FABRIC = ROOT / "components/clientjs-auto/assets/items/vai_vang.png"
MULTI_DEV_WAREHOUSE_YELLOW_FABRIC = ROOT / "components/clientjs-auto/assets/items/kho_vai_vang.png"
EXPECTED_COTTON_BLOB_SHA = "a828d5a796579f58de77989a80bd92d1122336d3"
EXPECTED_YELLOW_FABRIC_BLOB_SHA = "e963be3a5c33b85732f1b611b6801a741a4837ec"
EXPECTED_WAREHOUSE_YELLOW_FABRIC_BLOB_SHA = "f1d6135fa1af9725897f8a5b046e6fd2e5220754"


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def forbid(text: str, token: str, message: str) -> None:
    if token in text:
        raise AssertionError(message)


def read_python(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing production contract file: {path}")
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path))
    return text


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def main() -> int:
    paths = (
        ACTION, AUTOMATION, WORKFLOW, FUNCTION_ONE, FUNCTION_NAV, PASS_THREE_NAV,
        APPLE_JUICE, YELLOW_FABRIC, COTTON, MACHINE_REPAIR, ERRORS,
        RECOVERY_EVENTS, RECOVERY_NAV, RECOVERY_PRODUCTION, RECOVERY_MANAGER,
        LEGACY_RECOVERY, RECIPE_BOOK, RECIPE_DRIED_APPLE, RECIPE_APPLE_JUICE,
        RECIPE_YELLOW_FABRIC, DOWN_FLOOR_DETECTOR,
    )
    sources = {path: read_python(path) for path in paths}
    action = sources[ACTION]
    automation = sources[AUTOMATION]
    workflow = sources[WORKFLOW]
    function_one = sources[FUNCTION_ONE]
    function_nav = sources[FUNCTION_NAV]
    pass_nav = sources[PASS_THREE_NAV]
    apple_juice = sources[APPLE_JUICE]
    yellow_fabric = sources[YELLOW_FABRIC]
    cotton = sources[COTTON]
    machine_repair = sources[MACHINE_REPAIR]
    errors = sources[ERRORS]
    recovery_events = sources[RECOVERY_EVENTS]
    recovery_nav = sources[RECOVERY_NAV]
    recovery_production = sources[RECOVERY_PRODUCTION]
    recovery_manager = sources[RECOVERY_MANAGER]
    legacy_recovery = sources[LEGACY_RECOVERY]
    recipe_book = sources[RECIPE_BOOK]
    recipe_dried = sources[RECIPE_DRIED_APPLE]
    recipe_juice = sources[RECIPE_APPLE_JUICE]
    recipe_fabric = sources[RECIPE_YELLOW_FABRIC]
    down_floor = sources[DOWN_FLOOR_DETECTOR]

    for asset in (
        MULTI_DEV_DRIED_APPLE, MULTI_DEV_EMPTY_SLOT, MULTI_DEV_COTTON,
        MULTI_DEV_YELLOW_FABRIC, MULTI_DEV_WAREHOUSE_YELLOW_FABRIC,
    ):
        if not asset.is_file():
            raise AssertionError(f"Multi Dev production asset missing: {asset.name}")
    for asset, expected_sha in (
        (MULTI_DEV_COTTON, EXPECTED_COTTON_BLOB_SHA),
        (MULTI_DEV_YELLOW_FABRIC, EXPECTED_YELLOW_FABRIC_BLOB_SHA),
        (MULTI_DEV_WAREHOUSE_YELLOW_FABRIC, EXPECTED_WAREHOUSE_YELLOW_FABRIC_BLOB_SHA),
    ):
        actual = git_blob_sha(asset)
        if actual != expected_sha:
            raise AssertionError(
                f"Canonical asset blob changed: {asset.name} expected={expected_sha} actual={actual}"
            )

    # Shared production transaction: target product proves the panel; a different
    # known product is an explicit recoverable wrong-machine signal.
    require(action, "COLLECT_CLICK_BURST = 5", "Five-click VP collect burst missing")
    require(action, "def _send_collect_burst(", "Raw x5 helper missing")
    require(action, "for _ in range(self.COLLECT_CLICK_BURST):", "Raw x5 loop missing")
    require(action, 'KNOWN_PRODUCT_TEMPLATES = ("tao_say", "nuoc_tao", "vai_vang")',
            "Known production anchors missing")
    require(action, "PRODUCT_SEARCH_ZONE = (420, 550, 170, 120)",
            "Product-library-only zone changed")
    require(action, "def _find_wrong_product_match(", "Wrong-machine scanner missing")
    require(action, "raise WrongProductionMachine(", "Wrong-machine signal missing")
    require(action, "PANEL SAI MÁY/SAI TẦNG", "Wrong-machine runtime marker missing")
    forbid(action, "panel_ready = empty_ready or product_ready",
           "Empty slot may not prove the production panel")
    require(action, "self.speed_config.vp_collect_delay", "VP collect speed binding missing")
    require(action, "self.speed_config.vp_production_delay", "VP production speed binding missing")
    require(action, "empty == self.REQUIRED_COUNT", "9/9 idle-panel gate missing")
    require(action, "raise InventoryFull(", "InventoryFull business signal missing")

    # Product-specific actions remain atomic. Recipes own orchestration; actions
    # only validate/open/queue the requested product and emit typed signals.
    require(apple_juice, 'PRODUCT_TEMPLATE = "nuoc_tao"', "Apple-juice target missing")
    require(apple_juice, "DIRECT_FLOOR_PROBE_BURSTS = 2", "Direct juice probe bound changed")
    require(apple_juice, "DIRECT_FLOOR_PROBE_RECHECKS = 3", "Direct juice probe recheck changed")
    require(apple_juice, "def probe_floor_2_machine(self) -> bool:", "Direct juice probe missing")
    require(apple_juice, "self.slots._click_until_panel_open(", "Apple juice not using shared opener")
    require(apple_juice, "close_after_success: bool = True", "Apple juice panel handoff missing")
    require(yellow_fabric, 'PRODUCT_TEMPLATE = "vai_vang"', "Yellow-fabric target missing")
    require(yellow_fabric, "self.slots._click_until_panel_open(", "Yellow fabric not using shared opener")
    require(yellow_fabric, "close_after_success: bool = True", "Yellow fabric panel handoff missing")
    forbid(yellow_fabric, "kho_vai_vang", "Warehouse asset leaked into production")

    # errors.py contains signals only; handling policy belongs to recovery/.
    require(errors, "class WrongProductionMachine(NavigationError):",
            "WrongProductionMachine signal missing")
    require(errors, "class InventoryFull(TransactionError):", "InventoryFull signal missing")
    forbid(errors, "RecoveryManager", "errors.py must not own recovery policy")
    forbid(errors, "go_down_one_toward_main", "errors.py must not navigate")

    # Typed recovery events allow a Function/Recipe to inject local observers while
    # the core policy remains deterministic and centralized.
    require(recovery_events, "class RecoveryEventKind(str, Enum):", "Recovery event enum missing")
    require(recovery_events, "WRONG_PRODUCTION_MACHINE", "Wrong-machine event missing")
    require(recovery_events, "INVENTORY_FULL", "Inventory-full event missing")
    require(recovery_events, "class RecoveryEvent:", "Recovery event payload missing")

    # Navigation recovery owns unknown camera -> exact main and reusable route maps.
    require(recovery_nav, "UNKNOWN_FLOOR_MAIN_RECOVERY_PASSES = 6",
            "Unknown-camera recovery bound changed")
    require(recovery_nav, "go_down_one_toward_main(", "Unknown-camera safe descent missing")
    require(recovery_nav, "def recover_unknown_to_main(", "Unknown->main API missing")
    require(recovery_nav, "def recover_unknown_to_floor(", "Unknown->floor API missing")
    require(recovery_nav, "def to_main_from_floor(", "Known floor->main API missing")
    require(recovery_nav, "def from_main_to_floor(", "Main->floor API missing")
    require(recovery_nav, "def from_floor_to_floor(", "Known floor->floor API missing")
    require(recovery_nav, "between_floor_routes", "Injectable floor route map missing")
    require(recovery_nav, "self.auto.function_one_pass_three_navigation.floor_1_to_floor_3()",
            "Default floor1->floor3 route missing")
    require(recovery_nav, "self.auto.function_one_pass_three_navigation.floor_3_to_main_via_down_floor()",
            "Default floor3->main route missing")

    # Production recovery catches only explicit recoverable signals. Generic visual
    # failures remain fail-close to avoid replaying a side-effecting transaction.
    require(recovery_production, "except WrongProductionMachine as exc:",
            "Wrong-machine recovery catch missing")
    require(recovery_production, "except InventoryFull as exc:",
            "Inventory-full recovery catch missing")
    forbid(recovery_production, "except ScreenTimeout", "Generic ScreenTimeout must not be swallowed")
    require(recovery_production, "WRONG_MACHINE_RECOVERY_LIMIT = 3",
            "Wrong-machine retry bound changed")
    require(recovery_production, "self.navigation.recover_unknown_to_floor(",
            "Wrong machine does not normalize from unknown camera")
    require(recovery_production, "AutoVpSaleWorkflow(", "Inventory-full sale recovery missing")
    require(recovery_production, "allowed_item_ids=self.spec.sale_item_ids",
            "Inventory-full sale is not Function-bound")
    require(recovery_production, "if int(sale.sold_listings) <= 0:",
            "Inventory-full infinite-loop guard missing")

    require(recovery_manager, "class RecoveryManager:", "RecoveryManager facade missing")
    require(recovery_manager, "event_handlers:", "Injectable recovery event handlers missing")
    require(recovery_manager, "to_main_routes:", "Injectable to-main routes missing")
    require(recovery_manager, "from_main_routes:", "Injectable from-main routes missing")
    require(recovery_manager, "between_floor_routes:", "Injectable floor-floor routes missing")
    require(recovery_manager, "def run_production(", "Recovery production facade missing")
    require(recovery_manager, "def recover_unknown_to_floor(", "Recovery navigation facade missing")
    require(recovery_manager, "def from_floor_to_floor(", "Known-floor facade missing")

    # RecipeBook is per-Function and shares one recovery policy across product
    # recipes. This is the stable business-composition layer for future Functions.
    require(recipe_book, "class RecipeBook:", "RecipeBook facade missing")
    require(recipe_book, "self.recovery = recovery or RecoveryManager(",
            "RecipeBook does not own/share one RecoveryManager")
    require(recipe_book, "self.dried_apple = DriedAppleRecipe(", "Dried-apple recipe wiring missing")
    require(recipe_book, "self.apple_juice = AppleJuiceRecipe(", "Apple-juice recipe wiring missing")
    require(recipe_book, "self.yellow_fabric = YellowFabricRecipe(", "Yellow-fabric recipe wiring missing")
    require(recipe_book, "apple_juice=self.apple_juice", "Yellow-fabric dependency is not reusable")

    require(recipe_dried, "class DriedAppleRecipe:", "DriedAppleRecipe missing")
    require(recipe_dried, "self.auto.planting.plant_27_apples()", "Dried recipe does not own apple planting")
    require(recipe_dried, "self.recovery.run_production(", "Dried recipe does not use centralized recovery")
    require(recipe_dried, "floor=1", "Dried recipe floor binding missing")
    require(recipe_dried, "self.auto.machine_repair.repair_after_production(produced)",
            "Dried recipe repair missing")

    require(recipe_juice, "class AppleJuiceRecipe:", "AppleJuiceRecipe missing")
    require(recipe_juice, "def run_from_main(", "Standalone apple-juice recipe entry missing")
    require(recipe_juice, "def run_from_candidate_floor_2(", "Optimized candidate apple-juice entry missing")
    require(recipe_juice, "probe_floor_2_machine()", "Apple-juice candidate proof missing")
    require(recipe_juice, "self.recovery.recover_unknown_to_floor(",
            "Apple-juice candidate miss not delegated to recovery")
    require(recipe_juice, "self.recovery.run_production(", "Apple-juice recipe recovery missing")
    require(recipe_juice, "floor=2", "Apple-juice recipe floor binding missing")
    require(recipe_juice, "self.auto.machine_repair.repair_after_production(produced)",
            "Apple-juice recipe repair missing")

    require(recipe_fabric, "class YellowFabricRecipe:", "YellowFabricRecipe missing")
    require(recipe_fabric, "include_apple_juice_dependency", "Optional juice dependency missing")
    require(recipe_fabric, "self.apple_juice.run_from_main(count=count)",
            "Yellow-fabric recipe cannot call reusable apple-juice recipe")
    require(recipe_fabric, "def run_after_floor_2(", "Function-1 yellow-fabric entry missing")
    require(recipe_fabric, "self.auto.cotton_planting.plant_27_cotton()", "Yellow recipe does not own cotton planting")
    require(recipe_fabric, 'self.recovery.from_floor_to_floor(1, 3, "Vải vàng recipe")',
            "Yellow recipe does not own known floor1->3 transition")
    require(recipe_fabric, "self.recovery.run_production(", "Yellow recipe recovery missing")
    require(recipe_fabric, "floor=3", "Yellow recipe floor binding missing")
    require(recipe_fabric, "self.auto.machine_repair.repair_after_production(produced)",
            "Yellow recipe repair missing")

    # Legacy recovery remains a compatibility adapter only.
    require(legacy_recovery, "self.manager = RecoveryManager(", "Legacy recovery is not a facade")
    require(legacy_recovery, "return self.manager.run_production(", "Legacy facade does not delegate")
    forbid(legacy_recovery, "except WrongProductionMachine", "Wrong-machine loop duplicated in legacy facade")
    forbid(legacy_recovery, "except InventoryFull", "Inventory-full loop duplicated in legacy facade")

    # Function 1 must now be recipe composition, not a second implementation of
    # planting/production/recovery. It may keep only Function-specific supply and
    # optimized movement that prepares a recipe entry state.
    require(function_one, "from ...recipes import RecipeBook", "Function 1 RecipeBook import missing")
    require(function_one, "self.recipes = RecipeBook(", "Function 1 recipe wiring missing")
    require(function_one, "self.recovery = self.recipes.recovery", "Function 1 does not share recipe recovery")
    require(function_one, "self.recipes.dried_apple.run_from_session(count=9)",
            "Function 1 does not call DriedAppleRecipe")
    require(function_one, "self.auto.function_one_navigation.floor_6_to_floor_2()",
            "Function 1 optimized floor6->floor2 candidate movement missing")
    require(function_one, "self.recipes.apple_juice.run_from_candidate_floor_2(count=9)",
            "Function 1 does not delegate Nước táo to recipe")
    require(function_one, "self.recipes.yellow_fabric.run_after_floor_2(count=9)",
            "Function 1 does not delegate Vải vàng to recipe")
    forbid(function_one, "self.recovery.run_production(",
           "Function 1 reintroduced production recovery details")
    forbid(function_one, "self.auto.machine_repair.repair_after_production(",
           "Function 1 reintroduced machine-repair transaction details")
    forbid(function_one, "go_down_one_toward_main(", "Function 1 contains recovery loop details")
    require(function_one, "progress_steps=3", "Function 1 progress contract changed")
    require(function_one, "total_steps=3", "Function 1 total contract changed")

    # Existing AppleDryerWorkflow remains compatible for external callers while
    # Function 1 itself uses the new recipe layer.
    require(workflow, "ProductionWarehouseRecovery", "Dried-apple compatibility recovery missing")
    require(workflow, "self.warehouse_recovery.run_production(", "Dried-apple compatibility recovery call missing")
    require(workflow, "self.auto.machine_repair.repair_after_production(produced)",
            "Dried-apple compatibility repair missing")

    # Proven navigation primitives stay unchanged under recovery/recipe layers.
    require(pass_nav, "FLOOR_4_POT_POINT = (257, 191)", "Floor-4 pot anchor changed")
    require(pass_nav, "self.vision.driver.click(*self.FLOOR_4_POT_POINT)",
            "Floor1->floor3 does not click proven pot anchor")
    forbid(pass_nav, "self.vision.driver.click(*self.LEGACY_AUTO_PRO_MODE2_POINT)",
           "Runtime regressed to old floor2-only point")
    require(pass_nav, "RECOVERY_DOWN_CHAIN_LIMIT = 10", "Upper-floor recovery bound changed")
    require(down_floor, "def find_down_floor_button(", "Visual XUỐNG detector missing")
    require(down_floor, "cv2.TM_CCOEFF_NORMED", "XUỐNG normalized matching missing")

    require(automation, "self.machine_repair = MachineRepairActions(", "Machine repair wiring missing")
    require(machine_repair, "def repair_after_production", "Machine repair action missing")
    require(cotton, 'COTTON_TEMPLATE = "cay_bong"', "Cotton template changed")
    require(function_nav, "def floor_6_to_floor_2", "Direct floor6->floor2 route missing")

    for token in ("clear_stall_probe_runtime", "adb_controller.pyc"):
        for text in (
            action, workflow, function_one, recovery_nav, recovery_production,
            recipe_dried, recipe_juice, recipe_fabric, yellow_fabric, cotton, pass_nav,
        ):
            forbid(text, token, f"Production path touches stable/legacy path: {token}")

    print("AUTO MULTI DEV FUNCTION ONE STATIC CONTRACT VERIFIED")
    print("runtime=isolated_worker_v3")
    print("architecture=function-business+recipes-reusable+actions-atomic+recovery-centralized")
    print("recipe_book=shared-recovery-per-function")
    print("recipe_dried_apple=plant-apples+produce9+repair")
    print("recipe_apple_juice=standalone-main-or-candidate-floor2+proof+recover+produce9+repair")
    print("recipe_yellow_fabric=optional-apple-juice-dependency+cotton27+floor3+produce9+repair")
    print("recovery_facade=RecoveryManager")
    print("recovery_events=typed+optional-nonblocking-function-hooks")
    print("wrong_machine=signal->central-recovery->exact-main->requested-floor-retry")
    print("warehouse_full=signal->central-recovery->function-vp-sale->same-floor-retry")
    print("generic_screen_timeout=fail-close-no-blind-retry")
    print("stable_sale_qc_and_clear_stall=untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
