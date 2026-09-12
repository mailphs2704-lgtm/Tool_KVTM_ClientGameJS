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


def main() -> int:
    required = (
        (LAUNCHER, "persistent settings launcher"),
        (HOST, "Multi DEV host"),
        (OWNED_HOST, "owned Multi DEV host"),
        (AUTO_MAIN_PROFILE_SETTINGS, "AUTO Main per-profile settings layer"),
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
    daily_sale_ui = DAILY_SALE_UI.read_text(encoding="utf-8")
    daily_sale_counter = DAILY_SALE_COUNTER.read_text(encoding="utf-8")
    auto_vp_sale_init = AUTO_VP_SALE_INIT.read_text(encoding="utf-8")

    for path, text in (
        (HOST, host),
        (OWNED_HOST, owned_host),
        (AUTO_MAIN_PROFILE_SETTINGS, profile_settings),
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
    print("daily_sale_counter=per-profile+restart-persistent+local-midnight-reset")
    print("daily_sale_success=one-turn-per-sold-listing-x10")
    print("daily_sale_ui=account-detail-LƯỢT-BÁN-AUTO-current/1000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
