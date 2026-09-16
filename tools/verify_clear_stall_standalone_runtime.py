from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "components" / "clear_stall_tool"


def text(name: str) -> str:
    path = TOOL / name
    if not path.is_file():
        raise AssertionError(f"missing {path}")
    return path.read_text(encoding="utf-8")


def require(source: str, needle: str, label: str) -> None:
    if needle not in source:
        raise AssertionError(f"{label}: missing {needle!r}")


def main() -> int:
    main_src = text("main.py")
    store_src = text("profile_store.py")
    controller_src = text("runtime_controller.py")
    integration_src = text("runtime_integration.py")
    worker_src = text("standalone_clear_stall_worker.py")

    for name, source in (("main.py", main_src), ("profile_store.py", store_src), ("runtime_controller.py", controller_src), ("runtime_integration.py", integration_src), ("standalone_clear_stall_worker.py", worker_src)):
        ast.parse(source, filename=name)

    require(store_src, 'APPDATA", Path.home())) / "KVTM Dọn Quầy"', "separate app data")
    require(store_src, 'MULTI_PROFILE_FILE = MULTI_APP_DIR / "profiles.json"', "Multi profile source")
    require(store_src, 'status="stopped"', "startup state")
    require(store_src, "selected_profile_ids", "selected accounts persistence")
    require(store_src, "clear_stall_jobs", "standalone clear-stall settings")

    require(integration_src, "available_profiles()", "profile-only add account")
    require(integration_src, 'selectmode="extended"', "profile chooser")
    if 'Tên tài khoản", name' in integration_src or "ttk.Entry(row, textvariable=profile" in integration_src:
        raise AssertionError("Add Account must not restore free-text account/profile fields")

    require(controller_src, "MAX_CONCURRENCY = 2", "clear-stall concurrency")
    require(controller_src, "ClientOwnershipRegistry", "ownership safety")
    require(controller_src, "Dọn quầy không giành quyền điều khiển", "no ownership stealing")
    require(controller_src, "standalone_clear_stall_worker.py", "worker launch")
    require(controller_src, '"command": "stop"', "worker stop channel")
    require(controller_src, "client.terminate()", "close standalone ClientJS after run")

    require(worker_src, "from clear_stall_probe_runtime import ProbeConfig, run_probe", "shared runtime reuse")
    require(worker_src, "purchase_limit=purchase_limit", "full purchase target")
    require(worker_src, "resale_batch_limit=purchase_limit", "full resale target")
    require(worker_src, "return run_probe(", "shared business workflow")
    if "class ClearStallWorkflow" in worker_src:
        raise AssertionError("Standalone worker must not duplicate ClearStallWorkflow")

    require(main_src, "ProfileStore()", "real profile store")
    require(main_src, "ClearStallController", "real runtime controller")
    require(main_src, "bind_runtime", "GUI runtime binding")

    print("CLEAR STALL STANDALONE RUNTIME CONTRACT PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
