from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Iterable

APP_DIR = Path(os.environ.get("KVTM_CLEAR_STALL_APP_DIR") or (Path(os.environ.get("APPDATA", Path.home())) / "KVTM Dọn Quầy"))
PROFILE_FILE = APP_DIR / "profiles.json"
SETTINGS_FILE = APP_DIR / "settings.json"
MULTI_APP_DIR = Path(os.environ.get("KVTM_MULTI_APP_DIR") or (Path(os.environ.get("APPDATA", Path.home())) / "KVTM Multi DEV"))
MULTI_PROFILE_FILE = MULTI_APP_DIR / "profiles.json"
MULTI_SETTINGS_FILE = MULTI_APP_DIR / "settings.json"

DEFAULT_ALLOWED_ITEM_IDS = ("nuoc_hoa_hong", "tinh_dau_hh", "vai_vang", "tao_say", "tra_da")
DEFAULT_JOB = {
    "schema_version": 1,
    "target_friend_ordinal": 1,
    "target_stall_id": 2,
    "buy_quantity": 10,
    "max_scan_pages": 10,
    "interval_minutes": 65,
    "allowed_item_ids": list(DEFAULT_ALLOWED_ITEM_IDS),
    "clear_stall_drag_speed": 0.35,
}


def _read_json(path: Path, default):
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default
    return value


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


class ProfileStore:
    """Private Dọn quầy profile snapshot + settings.

    `profiles.json` is a local mirror of AUTO MULTI DEV profiles. The source
    file is never modified by this tool. Runtime state (running/stopped) is
    intentionally not persisted; every application start is STOPPED.
    """

    def __init__(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        self._settings = self._load_settings()
        self._profiles = self._load_profiles()
        # Keep the chooser tied to the current authoritative Multi DEV profile
        # on every tool start. Standalone settings/jobs are separate and survive
        # this refresh; deleted DEV profiles are removed from the local mirror.
        if MULTI_PROFILE_FILE.is_file():
            self.sync_from_multi()
        else:
            self._normalize_selected()

    @property
    def profile_file(self) -> Path:
        return PROFILE_FILE

    @property
    def multi_profile_file(self) -> Path:
        return MULTI_PROFILE_FILE

    @property
    def app_dir(self) -> Path:
        return APP_DIR

    def _load_profiles(self) -> list[dict]:
        raw = _read_json(PROFILE_FILE, [])
        if not isinstance(raw, list):
            return []
        result = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            profile_id = str(item.get("id") or "").strip()
            if not profile_id:
                continue
            result.append(dict(item))
        return result

    def _load_settings(self) -> dict:
        raw = _read_json(SETTINGS_FILE, {})
        if not isinstance(raw, dict):
            raw = {}
        raw.setdefault("schema_version", 1)
        raw.setdefault("selected_profile_ids", [])
        raw.setdefault("clear_stall_jobs", {})
        raw.setdefault("last_clean", {})
        raw.setdefault("last_success_at", {})
        return raw

    def _save_settings(self) -> None:
        _write_json(SETTINGS_FILE, self._settings)

    def _normalize_selected(self) -> None:
        valid = {str(p.get("id") or "") for p in self._profiles}
        selected = []
        for value in self._settings.get("selected_profile_ids", []):
            pid = str(value or "")
            if pid in valid and pid not in selected:
                selected.append(pid)
        if selected != self._settings.get("selected_profile_ids"):
            self._settings["selected_profile_ids"] = selected
            self._save_settings()

    def profiles(self) -> list[dict]:
        return [dict(item) for item in self._profiles]

    def profile(self, profile_id: str) -> dict | None:
        wanted = str(profile_id or "")
        item = next((p for p in self._profiles if str(p.get("id") or "") == wanted), None)
        return dict(item) if item is not None else None

    def selected_ids(self) -> list[str]:
        return [str(x) for x in self._settings.get("selected_profile_ids", [])]

    def selected_profiles(self) -> list[dict]:
        by_id = {str(p.get("id") or ""): p for p in self._profiles}
        return [dict(by_id[pid]) for pid in self.selected_ids() if pid in by_id]

    def available_profiles(self) -> list[dict]:
        selected = set(self.selected_ids())
        return [dict(p) for p in self._profiles if str(p.get("id") or "") not in selected]

    def add_selected(self, profile_ids: Iterable[str]) -> None:
        valid = {str(p.get("id") or "") for p in self._profiles}
        current = self.selected_ids()
        for profile_id in profile_ids:
            pid = str(profile_id or "")
            if pid in valid and pid not in current:
                current.append(pid)
                self.ensure_job(pid)
        self._settings["selected_profile_ids"] = current
        self._save_settings()

    def remove_selected(self, profile_id: str) -> None:
        wanted = str(profile_id or "")
        self._settings["selected_profile_ids"] = [pid for pid in self.selected_ids() if pid != wanted]
        self._save_settings()

    def sync_from_multi(self) -> int:
        raw = _read_json(MULTI_PROFILE_FILE, None)
        if not isinstance(raw, list):
            raise FileNotFoundError(f"Không đọc được profile AUTO MULTI DEV: {MULTI_PROFILE_FILE}")
        profiles = [dict(item) for item in raw if isinstance(item, dict) and str(item.get("id") or "").strip()]
        _write_json(PROFILE_FILE, profiles)
        self._profiles = profiles

        # Seed only missing standalone jobs from Multi. Existing standalone
        # setup remains authoritative after the first import.
        multi_settings = _read_json(MULTI_SETTINGS_FILE, {})
        multi_jobs = multi_settings.get("clear_stall_jobs", {}) if isinstance(multi_settings, dict) else {}
        if not isinstance(multi_jobs, dict):
            multi_jobs = {}
        own_jobs = self._settings.setdefault("clear_stall_jobs", {})
        multi_tuning = multi_settings.get("auto_tuning", {}) if isinstance(multi_settings, dict) else {}
        try:
            multi_drag_speed = float(
                multi_tuning.get("shop_drag_speed", DEFAULT_JOB["clear_stall_drag_speed"])
                if isinstance(multi_tuning, dict)
                else DEFAULT_JOB["clear_stall_drag_speed"]
            )
        except (TypeError, ValueError):
            multi_drag_speed = float(DEFAULT_JOB["clear_stall_drag_speed"])
        for profile in profiles:
            pid = str(profile.get("id") or "")
            if pid in own_jobs:
                continue
            source = multi_jobs.get(pid)
            seed = dict(source) if isinstance(source, dict) else {}
            seed.setdefault("clear_stall_drag_speed", multi_drag_speed)
            own_jobs[pid] = self._sanitize_job(seed)
        self._settings["profiles_synced_at"] = time.time()
        self._save_settings()
        self._normalize_selected()
        return len(profiles)

    @staticmethod
    def _sanitize_job(source: dict | None) -> dict:
        source = source or {}
        result = dict(DEFAULT_JOB)
        try:
            result["target_friend_ordinal"] = max(1, min(7, int(source.get("target_friend_ordinal", 1) or 1)))
        except (TypeError, ValueError):
            pass
        try:
            result["target_stall_id"] = max(1, min(5, int(source.get("target_stall_id", 2) or 2)))
        except (TypeError, ValueError):
            pass
        try:
            quantity = max(10, min(1000, int(source.get("buy_quantity", 10) or 10)))
            result["buy_quantity"] = max(10, (quantity // 10) * 10)
        except (TypeError, ValueError):
            pass
        try:
            result["max_scan_pages"] = max(1, min(10, int(source.get("max_scan_pages", 10) or 10)))
        except (TypeError, ValueError):
            pass
        try:
            result["interval_minutes"] = max(5, min(1440, int(source.get("interval_minutes", 65) or 65)))
        except (TypeError, ValueError):
            pass
        allowed = source.get("allowed_item_ids", DEFAULT_ALLOWED_ITEM_IDS)
        if isinstance(allowed, (list, tuple)):
            clean = [str(x) for x in allowed if str(x) in DEFAULT_ALLOWED_ITEM_IDS]
            if clean:
                result["allowed_item_ids"] = list(dict.fromkeys(clean))
        try:
            result["clear_stall_drag_speed"] = max(0.05, min(3.0, float(source.get("clear_stall_drag_speed", source.get("shop_drag_speed", 0.35)) or 0.35)))
        except (TypeError, ValueError):
            pass
        return result

    def ensure_job(self, profile_id: str) -> dict:
        pid = str(profile_id or "")
        jobs = self._settings.setdefault("clear_stall_jobs", {})
        existing = jobs.get(pid)
        if not isinstance(existing, dict):
            multi_settings = _read_json(MULTI_SETTINGS_FILE, {})
            source_jobs = multi_settings.get("clear_stall_jobs", {}) if isinstance(multi_settings, dict) else {}
            source = source_jobs.get(pid) if isinstance(source_jobs, dict) else None
            seed = dict(source) if isinstance(source, dict) else {}
            tuning = multi_settings.get("auto_tuning", {}) if isinstance(multi_settings, dict) else {}
            if isinstance(tuning, dict):
                seed.setdefault("clear_stall_drag_speed", tuning.get("shop_drag_speed", 0.35))
            existing = self._sanitize_job(seed)
            jobs[pid] = existing
            self._save_settings()
        return dict(self._sanitize_job(existing))

    def set_interval_all(self, minutes: int) -> int:
        value = max(5, min(1440, int(minutes)))
        for pid in self.selected_ids():
            job = self.ensure_job(pid)
            job["interval_minutes"] = value
            self._settings.setdefault("clear_stall_jobs", {})[pid] = job
        self._save_settings()
        return value

    def update_job(self, profile_id: str, updates: dict) -> dict:
        job = self.ensure_job(profile_id)
        job.update(dict(updates or {}))
        job = self._sanitize_job(job)
        self._settings.setdefault("clear_stall_jobs", {})[str(profile_id)] = job
        self._save_settings()
        return dict(job)

    def last_clean(self, profile_id: str) -> str:
        value = self._settings.get("last_clean", {}).get(str(profile_id))
        return str(value or "—")

    def mark_clean(self, profile_id: str, text: str) -> None:
        pid = str(profile_id)
        self._settings.setdefault("last_clean", {})[pid] = str(text)
        self._settings.setdefault("last_success_at", {})[pid] = time.time()
        self._save_settings()

    def last_success_at(self, profile_id: str) -> float:
        pid = str(profile_id)
        value = self._settings.get("last_success_at", {}).get(pid, 0)
        try:
            timestamp = max(0.0, float(value or 0))
        except (TypeError, ValueError):
            timestamp = 0.0
        if timestamp > 0:
            return timestamp

        # Migrate successful runs recorded before last_success_at existed.
        legacy = str(self._settings.get("last_clean", {}).get(pid) or "").strip()
        if not legacy or legacy == "—":
            return 0.0
        try:
            timestamp = time.mktime(time.strptime(legacy, "%H:%M %d/%m/%Y"))
        except (OverflowError, ValueError):
            return 0.0
        if timestamp <= 0:
            return 0.0
        self._settings.setdefault("last_success_at", {})[pid] = timestamp
        self._save_settings()
        return timestamp

    def account_rows(self):
        # Import lazily to avoid a circular import when unit-testing the store.
        try:
            from .app import AccountRecord
        except ImportError:
            from app import AccountRecord
        rows = []
        for profile in self.selected_profiles():
            pid = str(profile.get("id") or "")
            job = self.ensure_job(pid)
            name = str(profile.get("name") or pid)
            rows.append(
                AccountRecord(
                    pid,
                    name,
                    name,
                    status="stopped",
                    last_clean=self.last_clean(pid),
                    cycle_minutes=int(job.get("interval_minutes", 65)),
                    note="—",
                )
            )
        return rows
