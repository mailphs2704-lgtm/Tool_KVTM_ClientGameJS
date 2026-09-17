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
    app_src = text("app.py")
    main_src = text("main.py")
    store_src = text("profile_store.py")
    log_src = text("runtime_log.py")
    controller_src = text("runtime_controller.py")
    policy_src = text("runtime_policy.py")
    integration_src = text("runtime_integration.py")
    worker_src = text("standalone_clear_stall_worker.py")
    probe_src = (ROOT / "components" / "clientjs-auto" / "worker" / "clear_stall_probe_runtime.py").read_text(encoding="utf-8")

    for name, source in (
        ("app.py", app_src),
        ("main.py", main_src),
        ("profile_store.py", store_src),
        ("runtime_log.py", log_src),
        ("runtime_controller.py", controller_src),
        ("runtime_policy.py", policy_src),
        ("runtime_integration.py", integration_src),
        ("standalone_clear_stall_worker.py", worker_src),
    ):
        ast.parse(source, filename=name)

    require(store_src, 'APPDATA", Path.home())) / "KVTM Dọn Quầy"', "separate app data")
    require(store_src, 'APPDATA", Path.home())) / "KVTM Multi DEV"', "authoritative Multi DEV appdata")
    require(store_src, 'MULTI_PROFILE_FILE = MULTI_APP_DIR / "profiles.json"', "Multi DEV profile source")
    require(store_src, "multi_profile_file", "visible profile source path")
    require(store_src, 'status="stopped"', "startup state")
    require(store_src, "selected_profile_ids", "selected accounts persistence")
    require(store_src, "clear_stall_jobs", "standalone clear-stall settings")

    require(main_src, 'authoritative = appdata / "KVTM Multi DEV"', "deterministic Multi DEV binding")
    require(main_src, "legacy_candidates", "DEV-only migration fallback")
    require(main_src, "Never silently fall back", "no legacy/production profile ambiguity")

    require(integration_src, "available_profiles()", "profile-only add account")
    require(integration_src, 'selectmode="extended"', "profile chooser")
    require(integration_src, "Nguồn:", "profile source visible in GUI")
    if 'Tên tài khoản", name' in integration_src or "ttk.Entry(row, textvariable=profile" in integration_src:
        raise AssertionError("Add Account must not restore free-text account/profile fields")

    for label in (
        "Chọn VP dọn",
        "Số lượng nhà",
        "Số lượng VP dọn",
        "Thời gian chu kỳ",
        "Lưu cấu hình",
    ):
        require(integration_src, label, "per-account settings editor")
    for item_id in (
        "nuoc_hoa_hong",
        "tinh_dau_hh",
        "vai_vang",
        "tao_say",
        "tra_da",
    ):
        require(integration_src, item_id, "VP selector")
    require(integration_src, "profile_store.update_job", "per-account settings persistence")
    require(integration_src, "ttk.Entry(", "free numeric entry")
    if "Spinbox" in integration_src:
        raise AssertionError("Per-account/quick numeric settings must not use spinner +/- controls")

    require(app_src, '"LOG"', "table log column")
    require(app_src, "self.show_log", "per-account log button")
    if '"GHI CHÚ"' in app_src:
        raise AssertionError("Runtime progress must not be rendered in the old GHI CHÚ column")
    require(log_src, 'self.log_dir = Path(app_dir) / "logs"', "persistent log directory")
    require(log_src, "MAX_BYTES", "runtime log rotation")
    require(log_src, "read_tail", "runtime log reader")
    require(controller_src, "RuntimeLogStore", "controller log store")
    require(controller_src, '"worker_stdout"', "raw worker stdout logging")
    require(controller_src, '"worker_started"', "worker lifecycle logging")
    require(controller_src, '"client_started"', "client lifecycle logging")
    require(controller_src, "def log_path", "log path API")
    require(controller_src, "def read_log", "log reader API")
    require(integration_src, "def show_log", "live log viewer")
    require(integration_src, "runtime_controller.read_log", "viewer reads persistent log")
    require(integration_src, "Tự động làm mới log mỗi 0.7 giây", "live log refresh")
    require(integration_src, 'if event == "progress":', "no progress redraw in account table")
    require(app_src, "self._row_signature", "stable account-row identity")
    require(app_src, "self._row_value_labels", "in-place account-row updates")
    require(integration_src, "Chờ riêng cho phiên đầu", "manual Add first-session delay")
    require(integration_src, "Theo thời gian lần cuối thành công", "manual Add last-success mode")
    require(integration_src, "last_success_at", "last-success schedule lookup")
    require(store_src, 'raw.setdefault("last_success_at", {})', "last-success timestamp persistence")

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
    require(worker_src, "def _bootstrap_standalone_image_runtime", "standalone image bootstrap")
    require(worker_src, 'import_order="PIL_NUMPY_CV2"', "live fallback import order")
    require(worker_src, 'importlib.import_module("numpy")', "numpy preload")
    require(worker_src, 'importlib.import_module("cv2")', "opencv preload")
    require(worker_src, 'os.environ["KVTM_SKIP_RUNTIME_SYNC"] = "1"', "no legacy runtime sync")
    require(worker_src, "image_runtime_ready=True", "shared probe receives resident image runtime")
    require(policy_src, "first_delay_seconds", "first-cycle-only delay API")
    require(policy_src, 'env["KVTM_CLEAR_STALL_SEVEN_VIEW_SCAN_BUY"] = "1"', "standalone seven-view mode")
    require(probe_src, "STANDALONE_FRIEND_STALL_SCAN_COUNT = 7", "seven scan-buy views")
    require(probe_src, '"SCAN_BUY_THEN_ONE_SWIPE"', "one-swipe view order")
    require(probe_src, 'expected=1000x1000 actual=', "per-view resolution fail-close")
    if worker_src.index('importlib.import_module("numpy")') > worker_src.index('importlib.import_module("cv2")'):
        raise AssertionError("Standalone image runtime must make NumPy resident before cv2")
    if "class ClearStallWorkflow" in worker_src:
        raise AssertionError("Standalone worker must not duplicate ClearStallWorkflow")

    require(main_src, "ProfileStore()", "real profile store")
    require(main_src, "ClearStallController", "real runtime controller")
    require(main_src, "bind_runtime", "GUI runtime binding")

    print("CLEAR STALL STANDALONE RUNTIME CONTRACT PASS")
    print("profile_source=%APPDATA%\\KVTM Multi DEV\\profiles.json")
    print("account_settings=VP+HOUSE_COUNT+VP_QUANTITY+INTERVAL")
    print("numeric_input=PLAIN_ENTRY_NO_SPINNER")
    print("runtime_log=PERSISTENT_PER_ACCOUNT+LIVE_VIEWER")
    print("table_progress=LOG_BUTTON_ONLY")
    print("image_bootstrap=PIL_NUMPY_CV2_RESIDENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
