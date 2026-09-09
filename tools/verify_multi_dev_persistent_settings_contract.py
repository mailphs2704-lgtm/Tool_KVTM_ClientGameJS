from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "packaging/suite-v0.15/START_MULTI_DEV_SILENT.ps1"
HOST = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_host.py"


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def main() -> int:
    if not LAUNCHER.is_file():
        raise AssertionError(f"Missing persistent settings launcher: {LAUNCHER}")
    if not HOST.is_file():
        raise AssertionError(f"Missing Multi DEV host: {HOST}")

    launcher = LAUNCHER.read_text(encoding="utf-8")
    host = HOST.read_text(encoding="utf-8")
    ast.parse(host, filename=str(HOST))

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

    # Source-controlled fallback values: proven operator tuning + stable Dọn quầy
    # baseline. Existing per-profile clear-stall settings must win over defaults.
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

    print("AUTO MULTI DEV PERSISTENT SETTINGS CONTRACT VERIFIED")
    print("storage=%APPDATA%/KVTM Multi DEV")
    print("migration=package-data-dev-to-appdata-once-no-overwrite")
    print("speed=0.350,0.035,0.070,0.100")
    print("clear_stall_defaults=friend1,storage2,x10,pages4,interval65m")
    print("saved_clear_stall_values=authoritative")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
