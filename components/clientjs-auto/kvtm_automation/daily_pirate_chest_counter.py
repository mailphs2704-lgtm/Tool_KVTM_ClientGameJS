from __future__ import annotations

"""Persistent per-profile Pirate Chest OPENED counter.

Only a proven OPENED result increments the counter. Checks, cooldowns,
warehouse-full branches and SAFE_ABORT do not count. The stable profile id owns
state across ClientJS/tool restarts and a new local calendar day reads as zero.
"""

from datetime import datetime
import json
import os
from pathlib import Path
import re
import threading


__all__ = [
    "counter_file_for_profile",
    "read_daily_pirate_chest_count",
    "record_pirate_chest_opened",
]

_COUNTER_DIRNAME = "daily-pirate-chest-counters"
_COUNTER_VERSION = 1
_SAFE_PROFILE_RE = re.compile(r"[^A-Za-z0-9_.-]+")
_PROCESS_LOCK = threading.RLock()


def _local_now(now: datetime | None = None) -> datetime:
    value = now or datetime.now().astimezone()
    if value.tzinfo is None:
        value = value.astimezone()
    return value


def _safe_profile_id(profile_id: str) -> str:
    value = _SAFE_PROFILE_RE.sub("_", str(profile_id or "").strip())
    return value or "unknown-profile"


def counter_file_for_profile(app_dir: Path, profile_id: str) -> Path:
    root = Path(app_dir).resolve() / _COUNTER_DIRNAME
    return root / f"{_safe_profile_id(profile_id)}.json"


def _read_payload(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _payload_count(payload: dict) -> int:
    try:
        return max(0, int(payload.get("opened_count", 0) or 0))
    except (TypeError, ValueError):
        return 0


def read_daily_pirate_chest_count(
    app_dir: Path,
    profile_id: str,
    *,
    now: datetime | None = None,
) -> int:
    current = _local_now(now)
    payload = _read_payload(counter_file_for_profile(app_dir, profile_id))
    if str(payload.get("date") or "") != current.date().isoformat():
        return 0
    return _payload_count(payload)


def _app_dir_from_context(context) -> Path:
    profile_file = getattr(context, "profile_file", None)
    if profile_file is not None:
        return Path(profile_file).resolve().parent
    work_dir = Path(getattr(context, "work_dir")).resolve()
    for parent in (work_dir, *work_dir.parents):
        if parent.name.lower() == "auto-multi-dev":
            return parent.parent
    return work_dir


def record_pirate_chest_opened(
    context,
    *,
    now: datetime | None = None,
) -> int:
    """Record exactly one proven OPENED and return today's profile count."""
    current = _local_now(now)
    today = current.date().isoformat()
    profile_id = str(getattr(context, "profile_id", "") or "")
    path = counter_file_for_profile(_app_dir_from_context(context), profile_id)

    with _PROCESS_LOCK:
        payload = _read_payload(path)
        previous = _payload_count(payload) if str(payload.get("date") or "") == today else 0
        count = previous + 1
        data = {
            "version": _COUNTER_VERSION,
            "profile_id": profile_id,
            "date": today,
            "opened_count": count,
            "updated_at": current.isoformat(timespec="seconds"),
            "last_client_pid": int(getattr(context, "pid", 0) or 0),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(
            f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        try:
            temporary.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, path)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        return count
