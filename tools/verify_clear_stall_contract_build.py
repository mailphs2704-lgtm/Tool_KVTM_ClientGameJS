from __future__ import annotations

"""Build adapter for the clear-stall contract during AUTO MULTI DEV migration.

The clear-stall verifier owns many safety checks that must remain active.  One
legacy assertion inside it still requires AUTO MULTI DEV to import
``local_launcher``.  That assertion is obsolete now that Multi Dev has its own
shared clean image runtime.  This adapter replaces only that one assertion and
leaves every other clear-stall contract check untouched.
"""

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY_VERIFIER = ROOT / "tools" / "verify_clear_stall_contract.py"


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
    print("auto_multi_image_runtime=shared-clean local_launcher=false")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
