from __future__ import annotations

"""Build adapter for the clear-stall contract during AUTO MULTI DEV migration.

The clear-stall verifier owns many safety checks that must remain active. A few
legacy assertions inside it describe older AUTO MULTI DEV integration details:
legacy ``local_launcher`` image bootstrap, the old zero-argument
``AutoMainWorkflow(automation).run`` call, and a prose-only Gate 4 assertion
that disappeared when ``SellingActions`` gained the dual-resolution sale state
machine. Those details changed without changing Dọn quầy runtime. This adapter
replaces only those migration assertions and leaves every other clear-stall
contract check untouched.
"""

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY_VERIFIER = ROOT / "tools" / "verify_clear_stall_contract.py"


def _verify_gate4_inventory_order(source: str) -> None:
    """Prove Gate 4 still opens a slot before any inventory fingerprint scan."""
    try:
        method = source.split("def sell_one_of_exact_purchases", 1)[1]
        method = method.split("def _cancel_dialog", 1)[0]
    except IndexError as exc:
        raise AssertionError(
            "Gate 4 exact purchased-fingerprint selector missing"
        ) from exc

    required = (
        "if not self._find_empty_slot():",
        "self.inventory.select_storage(storage_id)",
        "self.inventory.best_fingerprint_match(fingerprint)",
    )
    missing = [token for token in required if token not in method]
    if missing:
        raise AssertionError(
            "Gate 4 inventory-open ordering contract missing: "
            + ", ".join(missing)
        )

    empty_index = method.index(required[0])
    storage_index = method.index(required[1])
    scan_index = method.index(required[2])
    if not empty_index < storage_index < scan_index:
        raise AssertionError(
            "Gate 4 inventory must open empty slot -> select storage -> scan fingerprint"
        )


def main() -> int:
    spec = importlib.util.spec_from_file_location(
        "kvtm_verify_clear_stall_contract_legacy",
        LEGACY_VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Không nạp được verifier: {LEGACY_VERIFIER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    original_require = module.require

    def migration_aware_require(source: str, needle: str, message: str) -> None:
        if message == "Gate 4 inventory must be scanned only after opening a stall slot":
            _verify_gate4_inventory_order(source)
            return
        if message == "Isolated AUTO Main wiring missing":
            required = (
                "AutoMainWorkflow(",
                "function_id=function_id",
                "sale_every_loops=sale_every",
                ").run()",
            )
            missing = [token for token in required if token not in source]
            if missing:
                raise AssertionError(
                    "Isolated selectable AUTO Main wiring missing: "
                    + ", ".join(missing)
                )
            return
        if message == "AUTO MULTI DEV worker must use the proven AUTO image bootstrap":
            expected = "from shared_runtime.image_runtime import install_binary_dependencies"
            if expected not in source:
                raise AssertionError(
                    "AUTO MULTI DEV worker must use shared clean image runtime"
                )
            if 'importlib.import_module("local_launcher")' in source:
                raise AssertionError(
                    "AUTO MULTI DEV worker must not return to legacy local_launcher bootstrap"
                )
            return
        original_require(source, needle, message)

    module.require = migration_aware_require
    result = int(module.main())
    print("CLEAR-STALL CONTRACT MIGRATION ADAPTER VERIFIED")
    print("gate4_inventory_order=empty-slot->storage->fingerprint-scan")
    print("auto_multi_image_runtime=shared-clean local_launcher=false")
    print("auto_main_wiring=selectable-function recurring-sale-schedule")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
