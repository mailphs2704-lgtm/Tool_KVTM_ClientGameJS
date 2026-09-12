from __future__ import annotations

"""Composite static gate for standardized AUTO production / Function 1."""

import ast
import hashlib
from pathlib import Path

from verify_production_action_boundaries_contract import main as verify_production_boundaries
from verify_recipe_function_standardization_contract import main as verify_recipe_function
from verify_recovery_architecture_contract import main as verify_recovery_architecture


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "components/clientjs-auto/kvtm_automation"
PRODUCTION_PANEL = CLEAN / "actions/production_panel.py"
WAREHOUSE_GUARD = CLEAN / "actions/warehouse_full_guard.py"
NAVIGATION_RECOVERY = CLEAN / "recovery/navigation.py"
DRIED_APPLE = CLEAN / "actions/production.py"
APPLE_JUICE = CLEAN / "actions/apple_juice_production.py"
YELLOW_FABRIC = CLEAN / "actions/yellow_fabric_production.py"
ROSE_OIL = CLEAN / "actions/rose_oil_production.py"
COTTON = CLEAN / "actions/cotton_planting.py"
MACHINE_REPAIR = CLEAN / "actions/machine_repair.py"
FUNCTION_ONE = CLEAN / "workflows/auto_function_one/workflow.py"
RECIPE_BOOK = CLEAN / "recipes/book.py"
LEGACY_RECOVERY = CLEAN / "workflows/production_warehouse_recovery.py"
AUTOMATION = CLEAN / "automation.py"

MULTI_DEV_DRIED_APPLE = ROOT / "components/clientjs-auto/assets/items/tao_say.png"
MULTI_DEV_EMPTY_SLOT = ROOT / "components/clientjs-auto/assets/items/o_trong.png"
MULTI_DEV_COTTON = ROOT / "components/clientjs-auto/assets/items/cay_bong.png"
MULTI_DEV_YELLOW_FABRIC = ROOT / "components/clientjs-auto/assets/items/vai_vang.png"
MULTI_DEV_WAREHOUSE_YELLOW_FABRIC = ROOT / "components/clientjs-auto/assets/items/kho_vai_vang.png"
EXPECTED_COTTON_BLOB_SHA = "a828d5a796579f58de77989a80bd92d1122336d3"
EXPECTED_YELLOW_FABRIC_BLOB_SHA = "e963be3a5c33b85732f1b611b6801a741a4837ec"
EXPECTED_WAREHOUSE_YELLOW_FABRIC_BLOB_SHA = "f1d6135fa1af9725897f8a5b046e6fd2e5220754"


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing production contract file: {path}")
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path))
    return text


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def forbid(text: str, token: str, message: str) -> None:
    if token in text:
        raise AssertionError(message)


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def main() -> int:
    # First run the canonical architecture gates. This old package verifier now
    # composes them instead of duplicating pre-standardization ownership rules.
    if verify_production_boundaries() != 0:
        raise AssertionError("Shared production Action boundary contract failed")
    if verify_recipe_function() != 0:
        raise AssertionError("Recipe/Function standardization contract failed")
    if verify_recovery_architecture() != 0:
        raise AssertionError("Recovery architecture contract failed")

    panel = read(PRODUCTION_PANEL)
    warehouse_guard = read(WAREHOUSE_GUARD)
    navigation_recovery = read(NAVIGATION_RECOVERY)
    dried = read(DRIED_APPLE)
    apple = read(APPLE_JUICE)
    yellow = read(YELLOW_FABRIC)
    rose = read(ROSE_OIL)
    cotton = read(COTTON)
    repair = read(MACHINE_REPAIR)
    function_one = read(FUNCTION_ONE)
    recipe_book = read(RECIPE_BOOK)
    legacy_recovery = read(LEGACY_RECOVERY)
    automation = read(AUTOMATION)

    # Canonical assets used by live-calibrated production remain present and the
    # three historically locked blobs remain byte-identical.
    for asset in (
        MULTI_DEV_DRIED_APPLE,
        MULTI_DEV_EMPTY_SLOT,
        MULTI_DEV_COTTON,
        MULTI_DEV_YELLOW_FABRIC,
        MULTI_DEV_WAREHOUSE_YELLOW_FABRIC,
    ):
        if not asset.is_file():
            raise AssertionError(f"Multi DEV production asset missing: {asset.name}")
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

    # Product-agnostic mechanics stay in ProductionPanelActions.
    require(panel, "class ProductionPanelActions:", "Shared production panel engine missing")
    require(panel, "COLLECT_CLICK_BURST = 5", "Five-click VP collect burst missing")
    require(panel, "PRODUCT_SEARCH_ZONE = (420, 550, 170, 120)", "Product search zone changed")
    require(panel, "def _find_wrong_product_match", "Wrong-machine scanner missing")
    require(panel, "raise WrongProductionMachine(", "Wrong-machine typed signal missing")
    require(panel, "raise InventoryFull(", "InventoryFull typed signal missing")
    require(panel, "def _click_until_panel_open", "Shared panel opener missing")
    require(panel, "def _wait_for_idle_open_panel", "Shared capacity waiter missing")

    # Warehouse-full is a global typed interruption. Live observation proved the
    # board may blink while the x5 collect burst is still landing. The guard must
    # stop business clicks, dismiss via a neutral backdrop point and prove the
    # board absent on consecutive fresh frames before InventoryFull reaches
    # RecoveryManager. Navigation must also use the generic floor-3 recovery path
    # rather than the Function-1 end-of-loop route/error text.
    for token in (
        "WAREHOUSE_FULL_DISMISS_POINT = (500, 185)",
        "WAREHOUSE_FULL_CLEAR_STABLE_FRAMES = 2",
        "def warehouse_full_visible(self, frame) -> bool:",
        "def dismiss_warehouse_full_popup(self, label: str) -> None:",
        "popup CLOSED PASS",
        "dừng trước khi điều hướng để giữ nguyên checkpoint",
        "dismiss_warehouse_full_popup(self, label)",
    ):
        require(
            warehouse_guard,
            token,
            f"Warehouse popup stable-dismiss contract missing: {token}",
        )
    dismiss_call = warehouse_guard.find("dismiss_warehouse_full_popup(self, label)")
    inventory_raise = warehouse_guard.rfind("raise InventoryFull(")
    if dismiss_call < 0 or inventory_raise < 0 or dismiss_call > inventory_raise:
        raise AssertionError(
            "Warehouse popup must be dismissed/proven closed before InventoryFull handoff"
        )
    require(
        navigation_recovery,
        "known_upper_floor_to_main_via_down_floor(",
        "Floor-3 recovery is not using the generic deterministic route",
    )
    forbid(
        navigation_recovery,
        "self.auto.farm_boundary_routes.floor_3_to_main_via_down_floor()",
        "Global floor-3 recovery still uses Function-1 end-loop route/error text",
    )

    # Product transactions stay separate and explicit.
    require(dried, "class ProductionActions(ProductionPanelActions):", "Dried Apple does not use shared panel engine")
    require(dried, "def produce_9_dried_apples", "Dried Apple x9 transaction missing")
    require(apple, 'PRODUCT_TEMPLATE = "nuoc_tao"', "Apple Juice target missing")
    require(apple, "self.slots = ProductionPanelActions(", "Apple Juice does not use neutral panel helper")
    require(apple, "def produce_9_apple_juices", "Apple Juice x9 transaction missing")
    require(yellow, 'PRODUCT_TEMPLATE = "vai_vang"', "Yellow Fabric target missing")
    require(yellow, "self.slots = ProductionPanelActions(", "Yellow Fabric does not use neutral panel helper")
    require(yellow, "def produce_9_yellow_fabrics", "Yellow Fabric x9 transaction missing")
    require(rose, "class RoseOilProductionActions(ProductionPanelActions):", "TDHH does not use shared panel engine")
    require(rose, "TARGET_COUNT = 7", "TDHH x7 contract changed")
    forbid(rose, "class RoseOilProductionActions(ProductionActions):", "TDHH regressed to Dried Apple inheritance")

    # Repair/crop handoffs remain semantic Actions.
    require(repair, "def repair_after_production", "Machine repair Action missing")
    require(cotton, 'COTTON_TEMPLATE = "cay_bong"', "Cotton template changed")
    require(cotton, "def wait_harvest_and_replant_27_cotton", "Neutral cotton batch Action missing")
    require(automation, "self.machine_repair = MachineRepairActions(", "Machine repair facade missing")
    require(automation, "self.rose_oil_production = RoseOilProductionActions(", "TDHH production facade missing")

    # Function 1 is business composition over one RecipeBook / shared recovery.
    require(recipe_book, "class RecipeBook:", "RecipeBook facade missing")
    require(recipe_book, "self.recovery = recovery or RecoveryManager(", "RecipeBook shared recovery missing")
    require(function_one, "from ...recipes import RecipeBook", "Function 1 RecipeBook import missing")
    require(function_one, "self.recipes = RecipeBook(", "Function 1 RecipeBook wiring missing")
    require(function_one, "self.recovery = self.recipes.recovery", "Function 1 does not share recipe recovery")
    require(function_one, "self.recipes.dried_apple.run_from_session(count=9)", "Function 1 dried recipe call missing")
    require(function_one, "self.auto.farm_routes.floor_6_to_floor_2()", "Function 1 generic floor6->floor2 route missing")
    require(function_one, "self.recipes.apple_juice.run_from_candidate_floor_2(count=9)", "Function 1 apple-juice recipe call missing")
    require(function_one, "self.recipes.yellow_fabric.run_after_floor_2(count=9)", "Function 1 yellow-fabric recipe call missing")
    require(function_one, "progress_steps=3", "Function 1 progress contract changed")
    require(function_one, "total_steps=3", "Function 1 total contract changed")
    forbid(function_one, "self.recovery.run_production(", "Function 1 reintroduced product transaction recovery details")

    # Historical recovery workflow is facade-only.
    require(legacy_recovery, "self.manager = RecoveryManager(", "Legacy recovery is not a facade")
    require(legacy_recovery, "return self.manager.run_production(", "Legacy recovery does not delegate")
    forbid(legacy_recovery, "except WrongProductionMachine", "Wrong-machine loop duplicated in legacy facade")
    forbid(legacy_recovery, "except InventoryFull", "Inventory-full loop duplicated in legacy facade")

    for text in (panel, warehouse_guard, navigation_recovery, dried, apple, yellow, rose, function_one, legacy_recovery):
        forbid(text, "clear_stall_probe_runtime", "Production path touches Dọn quầy runtime")
        forbid(text, ".pyc", "Production path loads legacy pyc")

    print("AUTO MULTI DEV FUNCTION ONE / PRODUCTION STATIC CONTRACT VERIFIED")
    print("production_engine=shared-ProductionPanelActions")
    print("warehouse_popup=dismiss-backdrop+2-stable-clear-frames-before-recovery")
    print("floor3_recovery=generic-route-not-function1-end-loop")
    print("transactions=dried9+juice9+fabric9+tdhh7")
    print("function1=RecipeBook+shared-RecoveryManager+generic-farm-routes")
    print("recovery=typed+checkpointed+fail-close-for-unregistered")
    print("assets=canonical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
