from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "packaging/suite-v0.15/START_MULTI_DEV_SILENT.ps1"
HOST = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_host.py"
OWNED_HOST = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_owned_host.py"
AUTO_MAIN_PROFILE_SETTINGS = (
    ROOT
    / "source-archive/multi-current/kvtm_multi_tool/auto_main_profile_settings.py"
)
OPTIONAL_FEATURES = (
    ROOT
    / "source-archive/multi-current/kvtm_multi_tool/optional_features_integration.py"
)
PIRATE_CHEST_WORKFLOW = (
    ROOT
    / "components/clientjs-auto/kvtm_automation/workflows/pirate_chest/workflow.py"
)
PIRATE_CHEST_SCHEDULE = (
    ROOT
    / "components/clientjs-auto/kvtm_automation/workflows/auto_main/pirate_chest_schedule.py"
)
AUTO_MAIN_INIT = (
    ROOT
    / "components/clientjs-auto/kvtm_automation/workflows/auto_main/__init__.py"
)
DAILY_SALE_UI = (
    ROOT
    / "source-archive/multi-current/kvtm_multi_tool/daily_sale_counter_integration.py"
)
DAILY_SALE_COUNTER = (
    ROOT / "components/clientjs-auto/kvtm_automation/daily_sale_counter.py"
)
AUTO_VP_SALE_INIT = (
    ROOT
    / "components/clientjs-auto/kvtm_automation/workflows/auto_vp_sale/__init__.py"
)


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def forbid(text: str, token: str, message: str) -> None:
    if token in text:
        raise AssertionError(message)


def main() -> int:
    required = (
        (LAUNCHER, "persistent settings launcher"),
        (HOST, "Multi DEV host"),
        (OWNED_HOST, "owned Multi DEV host"),
        (AUTO_MAIN_PROFILE_SETTINGS, "AUTO Main per-profile settings layer"),
        (OPTIONAL_FEATURES, "AUTO Main optional-features layer"),
        (PIRATE_CHEST_WORKFLOW, "Pirate Chest workflow"),
        (PIRATE_CHEST_SCHEDULE, "Pirate Chest safe-boundary scheduler"),
        (AUTO_MAIN_INIT, "AUTO Main package entry"),
        (DAILY_SALE_UI, "daily sale counter UI integration"),
        (DAILY_SALE_COUNTER, "daily sale counter storage"),
        (AUTO_VP_SALE_INIT, "AUTO VP sale package hook"),
    )
    for path, label in required:
        if not path.is_file():
            raise AssertionError(f"Missing {label}: {path}")

    launcher = LAUNCHER.read_text(encoding="utf-8")
    host = HOST.read_text(encoding="utf-8")
    owned_host = OWNED_HOST.read_text(encoding="utf-8")
    profile_settings = AUTO_MAIN_PROFILE_SETTINGS.read_text(encoding="utf-8")
    optional_features = OPTIONAL_FEATURES.read_text(encoding="utf-8")
    pirate_chest_workflow = PIRATE_CHEST_WORKFLOW.read_text(encoding="utf-8")
    pirate_chest_schedule = PIRATE_CHEST_SCHEDULE.read_text(encoding="utf-8")
    auto_main_init = AUTO_MAIN_INIT.read_text(encoding="utf-8")
    daily_sale_ui = DAILY_SALE_UI.read_text(encoding="utf-8")
    daily_sale_counter = DAILY_SALE_COUNTER.read_text(encoding="utf-8")
    auto_vp_sale_init = AUTO_VP_SALE_INIT.read_text(encoding="utf-8")

    for path, text in (
        (HOST, host),
        (OWNED_HOST, owned_host),
        (AUTO_MAIN_PROFILE_SETTINGS, profile_settings),
        (OPTIONAL_FEATURES, optional_features),
        (PIRATE_CHEST_WORKFLOW, pirate_chest_workflow),
        (PIRATE_CHEST_SCHEDULE, pirate_chest_schedule),
        (AUTO_MAIN_INIT, auto_main_init),
        (DAILY_SALE_UI, daily_sale_ui),
        (DAILY_SALE_COUNTER, daily_sale_counter),
        (AUTO_VP_SALE_INIT, auto_vp_sale_init),
    ):
        ast.parse(text, filename=str(path))

    # Settings/profile data must be outside dist so package rebuild cannot erase it.
    require(
        launcher,
        '$DataRoot = Join-Path $env:APPDATA "KVTM Multi DEV"',
        "Multi DEV settings are not stored in persistent APPDATA",
    )
    require(
        launcher,
        '$LegacyDataRoot = Join-Path $PackageRoot "data-dev"',
        "Legacy data-dev migration source missing",
    )
    for name in ("profiles.json", "settings.json", "clear-stall-history.jsonl"):
        require(launcher, name, f"Persistent migration missing {name}")
    require(
        launcher,
        "-not (Test-Path -LiteralPath $persistent -PathType Leaf)",
        "Migration may overwrite persistent DEV settings",
    )
    require(
        launcher,
        "$env:KVTM_MULTI_APP_DIR = $DataRoot",
        "Multi DEV runtime is not bound to persistent APPDATA",
    )
    require(
        launcher,
        '$HostScript = Join-Path $MultiRoot "kvtm_multi_owned_host.py"',
        "DEV launcher no longer starts the owned integration host",
    )

    # Source-controlled fallback values: proven operator tuning + stable Dọn quầy.
    require(host, '"floor_swipe_duration": 0.350', "Pinned floor speed changed")
    require(host, '"plant_harvest_duration": 0.035', "Pinned plant speed changed")
    require(host, '"vp_production_delay": 0.070', "Pinned VP production speed changed")
    require(host, '"crop_check_interval": 0.100', "Pinned crop check interval changed")
    require(host, '"target_friend_ordinal": 1', "Pinned clear-stall friend default changed")
    require(host, '"target_stall_id": 2', "Pinned clear-stall storage default changed")
    require(host, '"buy_quantity": 10', "Pinned clear-stall quantity default changed")
    require(host, '"max_scan_pages": 4', "Pinned clear-stall page default changed")
    require(host, '"interval_minutes": 65', "Pinned clear-stall interval changed")
    require(host, '"close_client_after_run": True', "Pinned close-after-run default changed")
    require(host, "merged.update(current)", "Saved Dọn quầy values no longer override defaults")
    require(host, "core.save_settings(self.settings)", "Self-healed Dọn quầy settings are not persisted")
    require(host, "core.DEFAULT_AUTO_TUNING.update(_PINNED_MULTI_DEV_TUNING)", "Pinned speed defaults not installed")
    require(host, "_install_pinned_dev_settings(kvtm_multi_dev_entry.core)", "Pinned settings installer is not wired")

    # AUTO Main scheduler settings belong to each account/profile.
    require(
        host,
        "from auto_main_profile_settings import install_auto_main_profile_settings",
        "AUTO Main per-profile settings module is not imported by DEV host",
    )
    require(
        host,
        "install_auto_main_profile_settings(",
        "AUTO Main per-profile settings installer is not wired",
    )
    require(
        profile_settings,
        '_PROFILE_SETTINGS_KEY = "auto_multi_dev_profiles"',
        "AUTO Main profile settings map key changed",
    )
    for key in (
        '"sale_every_loops"',
        '"function_loop_delay_seconds"',
        '"friend_refresh_enabled"',
    ):
        require(
            profile_settings,
            key,
            f"AUTO Main per-profile scheduler setting missing: {key}",
        )
    require(
        profile_settings,
        "self.settings.setdefault(_PROFILE_SETTINGS_KEY, {})[profile_id] = saved",
        "AUTO Main scheduler settings are not saved by profile id",
    )
    require(
        profile_settings,
        "self._save_auto_multi_dev_profile_settings()\n        result = original_account_click",
        "Account switch does not flush old profile settings before switching",
    )
    require(
        profile_settings,
        "self._refresh_auto_multi_dev_profile_settings()",
        "Account switch does not reload profile-specific AUTO Main settings",
    )
    require(
        profile_settings,
        "command=self._save_auto_multi_dev_profile_settings",
        "AUTO Main scheduler spinboxes are not persistence-bound",
    )
    require(
        profile_settings,
        "saved = self._auto_multi_dev_profile_settings(profile_id)",
        "AUTO Main start does not read each selected profile's settings",
    )
    require(
        profile_settings,
        "self._auto_main_pending_config[profile_id] = dict(config)",
        "AUTO Main per-profile frozen pending config missing",
    )
    require(
        profile_settings,
        "self._auto_main_active_config[profile_id] = dict(config)",
        "AUTO Main per-profile active snapshot missing",
    )
    require(
        profile_settings,
        "if not store and _LEGACY_FRIEND_REFRESH_KEY in raw:",
        "Legacy global friend-refresh migration missing",
    )

    # Optional Features now own the old Function-selector slot. Pirate Chest is
    # the first option and must be persistent per profile but frozen per run.
    require(
        owned_host,
        "import optional_features_integration",
        "Owned DEV host does not import Optional Features integration",
    )
    require(
        owned_host,
        "optional_features_integration.install_optional_features_integration(",
        "Owned DEV host does not install Optional Features after scheduler layers",
    )
    require(
        optional_features,
        '_OPTIONAL_FEATURES_KEY = "auto_multi_dev_optional_features"',
        "Optional Features per-profile settings key changed",
    )
    require(
        optional_features,
        '"pirate_chest_enabled": False',
        "Pirate Chest option must default OFF",
    )
    require(
        optional_features,
        'text="TÙY CHỌN"',
        "Old Function-selector slot is not relabeled as TÙY CHỌN",
    )
    require(
        optional_features,
        '"Mở rương hải tặc"',
        "Pirate Chest toggle is missing from Optional Features UI",
    )
    require(
        optional_features,
        "self.settings.setdefault(_OPTIONAL_FEATURES_KEY, {})[profile_id] = saved",
        "Pirate Chest option is not saved by profile id",
    )
    require(
        optional_features,
        "self._optional_features_run_snapshot",
        "Optional Features are not frozen per run",
    )
    require(
        optional_features,
        'config["pirate_chest_enabled"] = enabled',
        "Pirate Chest flag is not injected into AUTO Main run config",
    )
    require(
        optional_features,
        'getattr(self, "_auto_main_active_config", None)',
        "Pirate Chest flag is not preserved in active config for scheduled restart",
    )

    # Pirate Chest scheduler: first check after sale #1. Only OPENED starts
    # the 20-minute timer; every non-OPENED result retries after the next sale.
    require(
        auto_main_init,
        "from .pirate_chest_schedule import AutoMainResult, AutoMainWorkflow",
        "AUTO Main package is not wired through Pirate Chest scheduler",
    )
    require(
        pirate_chest_schedule,
        "PIRATE_CHEST_INTERVAL_SECONDS = 1200.0",
        "Pirate Chest successful-open interval changed from 20 minutes",
    )
    require(
        pirate_chest_schedule,
        '"pirate_chest_enabled"',
        "Pirate Chest scheduler does not read the run config flag",
    )
    require(
        pirate_chest_schedule,
        "or self._pirate_chest_retry_after_sale",
        "Non-opened Pirate Chest results do not retry after the next sale",
    )
    require(
        pirate_chest_schedule,
        'if str(status) == "OPENED":',
        "Pirate Chest timer is not restricted to a proven OPENED result",
    )
    require(
        pirate_chest_schedule,
        "self._pirate_chest_next_check_at = 0.0",
        "Non-opened Pirate Chest result may retain a 20-minute deadline",
    )
    require(
        pirate_chest_schedule,
        "self._schedule_next_pirate_chest_check(status=status)",
        "Pirate Chest result is not routed into status-aware scheduling",
    )
    require(
        pirate_chest_schedule,
        '"sau-lần-bán-VP-kế-tiếp"',
        "Pirate Chest retry-after-sale diagnostic is missing",
    )
    require(
        pirate_chest_schedule,
        'reason="post-function-boundary"',
        "Successful-open 20-minute due check is not consumed post-Function",
    )
    require(
        pirate_chest_schedule,
        'status = "SAFE_ABORT"',
        "Optional Pirate Chest failure is no longer non-blocking",
    )
    require(
        pirate_chest_schedule,
        'if status == "SAFE_ABORT":',
        "Pirate Chest scene reset is no longer limited to SAFE_ABORT",
    )
    require(
        pirate_chest_schedule,
        "self._reset_scene_after_pirate_chest_abort(reason=detail or reason)",
        "Pirate Chest SAFE_ABORT no longer owns its recovery",
    )

    # Pirate Chest click safety: coordinate/hitbox entry, slot 0 only, no image
    # template dependency for the variable farm background and no paid-slot map.
    require(
        pirate_chest_workflow,
        "ENTRY_POINT =",
        "Pirate Chest logical entry hitbox is missing",
    )
    require(
        pirate_chest_workflow,
        "SLOT_ZERO_POINT =",
        "Pirate Chest slot-0 coordinate is missing",
    )
    require(
        pirate_chest_workflow,
        "self._panel_normal(frame) or self._open_prompt(frame)",
        "Pirate Chest entry no longer accepts the persisted tap-to-open modal",
    )
    require(
        pirate_chest_workflow,
        "if self._open_prompt(entry_frame):",
        "Pirate Chest persisted modal resume branch is missing",
    )
    require(
        pirate_chest_workflow,
        "bỏ qua chọn slot và MỞ NGAY",
        "Pirate Chest persisted modal may replay slot selection or MỞ NGAY",
    )
    for forbidden_slot in (
        "SLOT_ONE_POINT",
        "SLOT_TWO_POINT",
        "SLOT_THREE_POINT",
        "SLOT_FOUR_POINT",
        "PAID_CHEST_POINT",
    ):
        forbid(
            pirate_chest_workflow,
            forbidden_slot,
            f"Paid chest coordinate must not exist: {forbidden_slot}",
        )
    for forbidden_image_call in (
        "find_template(",
        "match_template(",
        "locate_template(",
        "template_path=",
    ):
        forbid(
            pirate_chest_workflow,
            forbidden_image_call,
            f"Pirate Chest must not depend on background templates: {forbidden_image_call}",
        )
    require(
        pirate_chest_workflow,
        "if not self._ready(frame):",
        "Pirate Chest no longer fail-closes an unclassified slot-0 state",
    )
    require(
        pirate_chest_workflow,
        "PirateChestStatus.STORAGE_FULL",
        "Pirate Chest storage-full branch missing",
    )
    require(
        pirate_chest_workflow,
        "self._exit_after_storage_full()",
        "Storage-full modal no longer exits the Pirate Chest flow",
    )
    require(
        pirate_chest_workflow,
        "PirateChestStatus.COOLDOWN",
        "Pirate Chest cooldown branch missing",
    )

    # Exact operator sequence: three capture-free 3s waits around two single
    # taps, then center-chest return, panel close and MAIN proof.
    require(
        pirate_chest_workflow,
        "CHEST_CENTER_POINT = (486, 603)",
        "Pirate Chest open tap no longer matches the operator-marked point",
    )
    require(
        pirate_chest_workflow,
        "REWARD_CLAIM_POINT = (500, 702)",
        "Pirate Chest claim tap no longer matches the operator-marked point",
    )
    require(
        pirate_chest_workflow,
        "OPERATOR_ANIMATION_WAIT_SECONDS = 3.0",
        "Pirate Chest does not use the exact operator-approved 3s waits",
    )
    for state in (
        'state="modal-open-before-chest-tap"',
        'state="reward-open-before-claim"',
        'state="claim-before-panel-check"',
    ):
        require(
            pirate_chest_workflow,
            state,
            f"Pirate Chest fixed animation wait missing: {state}",
        )
    require(
        pirate_chest_workflow,
        '"không CAPTURE/check"',
        "Pirate Chest animation waits no longer exclude CAPTURE/check",
    )
    require(
        pirate_chest_workflow,
        'self._tap(self.CHEST_CENTER_POINT, "pirate-chest-tap-chest")',
        "Pirate Chest does not tap the marked chest point exactly once",
    )
    require(
        pirate_chest_workflow,
        'self._tap(self.REWARD_CLAIM_POINT, "pirate-chest-claim-reward-once")',
        "Pirate Chest does not claim at the marked blank point",
    )
    if pirate_chest_workflow.count("pirate-chest-claim-reward-once") != 1:
        raise AssertionError("Pirate Chest reward claim may be retried or duplicated")
    require(
        pirate_chest_workflow,
        "proof=center-chest-visible-again",
        "Pirate Chest does not prove the center chest returned after claim",
    )
    require(
        pirate_chest_workflow,
        "def _close_panel_and_prove_main(",
        "Pirate Chest does not close the panel and prove MAIN",
    )
    require(
        pirate_chest_workflow,
        '"Pirate chest panel closed | proof=exact-main"',
        "Pirate Chest exact-main close proof log is missing",
    )
    for obsolete_animation_gate in (
        "_wait_open_prompt_animation",
        "_wait_for_reward_claimable",
        "proof=claim-text-stable",
        "REWARD_TEXT_STABLE_SECONDS",
        "POST_CLAIM_QUIET_SECONDS",
        "ANIMATION_SETTLE_SECONDS",
    ):
        forbid(
            pirate_chest_workflow,
            obsolete_animation_gate,
            f"Obsolete moving-animation gate remains: {obsolete_animation_gate}",
        )
    require(
        pirate_chest_workflow,
        "không dùng nút quay lại",
        "Pirate Chest reward timeout may incorrectly use the Back button",
    )
    forbid(
        pirate_chest_workflow,
        "pirate-chest-safe-abort-back",
        "Pirate Chest reward overlay must not be dismissed with Back",
    )

    # Daily VP sale-turn counter. One successfully posted x10 listing equals one
    # game sale turn: a workflow result sold_listings=N must add exactly +N.
    require(
        daily_sale_counter,
        '_COUNTER_DIRNAME = "daily-sale-counters"',
        "Daily sale counter directory contract changed",
    )
    require(
        daily_sale_counter,
        "datetime.now().astimezone()",
        "Daily sale counter does not use local calendar time",
    )
    require(
        daily_sale_counter,
        '"successful_listings": count',
        "Daily sale counter payload missing successful_listings",
    )
    require(
        daily_sale_counter,
        "count = previous + sold",
        "Daily sale counter no longer increments by every posted listing",
    )
    require(
        daily_sale_counter,
        "if str(payload.get(\"date\") or \"\") != today:\n        return 0",
        "Daily sale counter does not reset logically after local midnight",
    )
    require(
        daily_sale_counter,
        "os.replace(temporary, path)",
        "Daily sale counter write is not atomic",
    )
    require(
        auto_vp_sale_init,
        "if sold <= 0:\n            return result",
        "Zero-listing sale scans may incorrectly increment the counter",
    )
    require(
        auto_vp_sale_init,
        "record_successful_listings(",
        "Successful VP listings are not wired to the daily counter",
    )
    require(
        auto_vp_sale_init,
        "non-blocking write failed",
        "Counter persistence failure is no longer non-blocking",
    )
    require(
        daily_sale_ui,
        'sales_var = detail_vars.get("sales")',
        "Daily sale count is not bound to the existing LƯỢT BÁN AUTO field",
    )
    require(
        daily_sale_ui,
        'text = f"{count} / {_GAME_DAILY_SALE_LIMIT}"',
        "Daily sale field does not show current count against the 1000-turn limit",
    )
    require(
        daily_sale_ui,
        "app_class._show_account_details = show_account_details",
        "Account switch/detail refresh does not update the daily sale field",
    )
    require(
        daily_sale_ui,
        "_REFRESH_MS = 1000",
        "Daily sale UI is not refreshed across midnight/account switches",
    )
    require(
        owned_host,
        "daily_sale_counter_integration.install_daily_sale_counter_integration(",
        "Daily sale counter UI integration is not installed by owned DEV host",
    )

    print("AUTO MULTI DEV PERSISTENT SETTINGS CONTRACT VERIFIED")
    print("storage=%APPDATA%/KVTM Multi DEV")
    print("migration=package-data-dev-to-appdata-once-no-overwrite")
    print("speed=0.350,0.035,0.070,0.100")
    print("clear_stall_defaults=friend1,storage2,x10,pages4,interval65m")
    print("saved_clear_stall_values=authoritative")
    print(
        "auto_main_profile_settings="
        "sale_every_loops,function_loop_delay_seconds,friend_refresh_enabled"
    )
    print("auto_main_profile_switch=save-old+load-new")
    print("auto_main_multi_start=per-profile-frozen-snapshot")
    print("optional_features=old-function-slot-replaced+per-profile")
    print("pirate_chest=default-off+slot0-only+safe-boundary+20m")
    print("pirate_chest_storage_full=close-and-continue-next-function")
    print("daily_sale_counter=per-profile+restart-persistent+local-midnight-reset")
    print("daily_sale_success=one-turn-per-sold-listing-x10")
    print("daily_sale_ui=account-detail-LƯỢT-BÁN-AUTO-current/1000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
