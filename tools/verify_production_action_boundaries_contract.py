from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTIONS = ROOT / "components/clientjs-auto/kvtm_automation/actions"
PRODUCTION_PANEL = ACTIONS / "production_panel.py"
DRIED_APPLE = ACTIONS / "production.py"
APPLE_JUICE = ACTIONS / "apple_juice_production.py"
YELLOW_FABRIC = ACTIONS / "yellow_fabric_production.py"
ROSE_OIL = ACTIONS / "rose_oil_production.py"
DRIED_TEA = ACTIONS / "dried_tea_production.py"
MATERIAL_AWARE = ACTIONS / "material_shortage_production.py"
WAREHOUSE_GUARD = ACTIONS / "warehouse_full_guard.py"
ACTIONS_INIT = ACTIONS / "__init__.py"


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing production boundary file: {path}")
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
    panel = read(PRODUCTION_PANEL)
    dried = read(DRIED_APPLE)
    apple = read(APPLE_JUICE)
    yellow = read(YELLOW_FABRIC)
    rose = read(ROSE_OIL)
    tea = read(DRIED_TEA)
    material = read(MATERIAL_AWARE)
    guard = read(WAREHOUSE_GUARD)
    actions_init = read(ACTIONS_INIT)

    # Shared panel engine owns only reusable panel/slot mechanics and typed
    # panel-state signals. Product queue transactions stay outside it.
    require(panel, "class ProductionPanelActions:", "Shared ProductionPanelActions missing")
    for token in (
        "def _count_matches(",
        "def _count_empty_slots(",
        "def _find_product_match(",
        "def _find_wrong_product_match(",
        "def _panel_state(",
        "def _raise_inventory_full(",
        "def _raise_wrong_machine(",
        "def _send_collect_burst(",
        "def collect_vp_before_machine_panel(",
        "def _click_until_panel_open(",
        "def _wait_for_idle_open_panel(",
    ):
        require(panel, token, f"Shared production primitive missing: {token}")
    for token in (
        "COLLECT_CLICK_BURST = 5",
        "COLLECT_MIN_BURSTS = 4",
        "COLLECT_MIN_CLICKS = COLLECT_CLICK_BURST * COLLECT_MIN_BURSTS",
        "click_count += self.collect_vp_before_machine_panel(",
    ):
        require(panel, token, f"Shared >=20-click VP collection contract missing: {token}")
    forbid(panel, "produce_9_dried_apples", "Shared panel engine contains Dried Apple transaction")
    forbid(panel, "produce_9_apple_juices", "Shared panel engine contains Apple Juice transaction")
    forbid(panel, "produce_9_yellow_fabrics", "Shared panel engine contains Yellow Fabric transaction")
    forbid(panel, "produce_7_rose_oils", "Shared panel engine contains TDHH transaction")

    # Dried Apple becomes one product transaction over the shared engine; generic
    # panel methods must not be duplicated back into production.py.
    require(
        dried,
        "class ProductionActions(ProductionPanelActions):",
        "Dried Apple ProductionActions does not inherit the shared panel engine",
    )
    require(dried, "def produce_9_dried_apples(", "Dried Apple transaction missing")
    for token in (
        "def _count_matches(",
        "def _panel_state(",
        "def _click_until_panel_open(",
        "def _wait_for_idle_open_panel(",
    ):
        forbid(dried, token, f"Dried Apple duplicated shared panel primitive: {token}")

    # Nước táo and Vải vàng hold a neutral panel helper, never instantiate the
    # Dried Apple product transaction merely to borrow slot methods.
    require(apple, "from .production_panel import ProductionPanelActions", "Apple Juice shared panel import missing")
    require(apple, "self.slots = ProductionPanelActions(", "Apple Juice still borrows a product transaction as slot helper")
    require(
        apple,
        "self.slots.collect_vp_before_machine_panel(",
        "Apple Juice direct floor probe bypasses the shared >=20-click collector",
    )
    forbid(apple, "self.slots._send_collect_burst(", "Apple Juice probe regressed to private x5 burst")
    forbid(apple, "self.slots = ProductionActions(", "Apple Juice regressed to Dried Apple helper")

    require(yellow, "from .production_panel import ProductionPanelActions", "Yellow Fabric shared panel import missing")
    require(yellow, "self.slots = ProductionPanelActions(", "Yellow Fabric still borrows a product transaction as slot helper")
    forbid(yellow, "self.slots = ProductionActions(", "Yellow Fabric regressed to Dried Apple helper")

    # Trà sấy has paged product selection. Collection still belongs to the shared
    # machine collector and the page arrow is forbidden until panel-open proof.
    require(
        tea,
        "click_count += self.collect_vp_before_machine_panel(",
        "Dried Tea bypasses the shared >=20-click collector",
    )
    require(
        tea,
        "if not empty_ready:",
        "Dried Tea page turn is not gated by production-panel proof",
    )
    require(
        tea,
        "KHÔNG chuyển trang",
        "Dried Tea panel-loss branch no longer fail-closes page movement",
    )
    forbid(
        tea,
        "self._send_collect_burst(machine_point=self.MACHINE_POINT)",
        "Dried Tea regressed to a single private x5 collection burst",
    )

    # TDHH directly subclasses the shared engine. Its 7-item and retry constants
    # are explicit so they are not inherited accidentally from Dried Apple.
    require(
        rose,
        "class RoseOilProductionActions(ProductionPanelActions):",
        "TDHH production still inherits Dried Apple transaction",
    )
    forbid(rose, "class RoseOilProductionActions(ProductionActions):", "TDHH regressed to Dried Apple inheritance")
    for token in (
        "TARGET_COUNT = 7",
        "REQUIRED_COUNT = TARGET_COUNT",
        "DRAG_ATTEMPTS = 3",
        "VERIFY_RECHECKS = 4",
        "VERIFY_RECHECK_SECONDS = 0.18",
        "MATERIAL_ERROR_TEMPLATE = \"x\"",
    ):
        require(rose, token, f"TDHH explicit production contract missing: {token}")

    # No product Action may own a private collect-click count. All machine-opening
    # paths must reach the shared collector, directly or through _click_until_panel_open.
    for name, product_text in (
        ("Dried Apple", dried),
        ("Apple Juice", apple),
        ("Yellow Fabric", yellow),
        ("Rose Oil", rose),
        ("Dried Tea", tea),
    ):
        forbid(
            product_text,
            "._send_collect_burst(",
            f"{name} contains a direct private collect burst instead of shared collector",
        )

    # Live warehouse-full detection must patch the shared panel engine once, so
    # every product path keeps the same visual proof and typed InventoryFull.
    require(
        guard,
        "from .production_panel import ProductionPanelActions",
        "Warehouse-full guard does not target shared panel engine",
    )
    require(guard, "ProductionPanelActions._panel_state = panel_state", "Warehouse-full panel patch missing")
    require(guard, "ProductionPanelActions._raise_inventory_full = raise_inventory_full", "Warehouse-full typed raise patch missing")
    forbid(guard, "ProductionActions._panel_state", "Warehouse-full guard regressed to Dried Apple-only patch")

    # Material-aware Dried Apple remains layered over the Dried Apple transaction;
    # this preserves resume behavior while the common panel mechanics sit below.
    require(
        material,
        "class MaterialAwareProductionActions(_MaterialShortageMixin, BaseProductionActions):",
        "Material-aware Dried Apple no longer preserves its product-specific resume layer",
    )
    require(material, "class _ResumeState:", "Material resume checkpoint state missing")

    require(actions_init, "from .production_panel import ProductionPanelActions", "Shared panel Action is not exported")
    require(actions_init, '"ProductionPanelActions"', "Shared panel Action missing from __all__")
    if actions_init.index("install_warehouse_full_guard()") > actions_init.index("from .material_shortage_production import"):
        raise AssertionError("Warehouse-full guard must install before product Action imports")

    print("AUTO PRODUCTION ACTION BOUNDARY CONTRACT VERIFIED")
    print("panel-engine=shared+product-agnostic+vp-collector-min-20")
    print("dried-apple=product-subclass")
    print("apple-juice=shared-panel-helper+shared-probe-collector")
    print("yellow-fabric=shared-panel-helper")
    print("dried-tea=shared-collector+panel-proof-before-page-turn")
    print("tdhh=shared-panel-subclass+explicit-7-count")
    print("warehouse-full=shared-panel-guard")
    print("material-shortage=resume-layer-preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
