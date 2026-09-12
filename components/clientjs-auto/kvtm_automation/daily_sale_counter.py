from __future__ import annotations

"""Persistent per-profile counter for successful VP sale sessions.

A successful sale session is counted once when AutoVpSaleWorkflow returns with
at least one newly posted x10 listing. The counter is tied to the stable KVTM
profile id, not the transient ClientJS PID, so scheduled ClientJS restarts and
tool restarts do not reset it. A new local calendar day starts from zero.
"""

from datetime import datetime
import json
import os
from pathlib import Path
import re
import threading


__all__ = [
    "counter_file_for_profile",
    "read_daily_sale_count",
    "record_successful_sale",
]

_COUNTER_DIRNAME = "daily-sale-counters"
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


def read_daily_sale_count(
    app_dir: Path,
    profile_id: str,
    *,
    now: datetime | None = None,
) -> int:
    current = _local_now(now)
    today = current.date().isoformat()
    payload = _read_payload(counter_file_for_profile(app_dir, profile_id))
    if str(payload.get("date") or "") != today:
        return 0
    try:
        count = int(payload.get("successful_sales", 0) or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, count)


def _app_dir_from_context(context) -> Path:
    profile_file = getattr(context, "profile_file", None)
    if profile_file is not None:
        return Path(profile_file).resolve().parent
    work_dir = Path(getattr(context, "work_dir")).resolve()
    # Normal worker layout is APP_DIR/auto-multi-dev/<profile>/run. Keep a
    # conservative fallback for diagnostics where profile_file is not supplied.
    for parent in (work_dir, *work_dir.parents):
        if parent.name.lower() == "auto-multi-dev":
            return parent.parent
    return work_dir


def record_successful_sale(
    context,
    *,
    sold_listings: int,
    now: datetime | None = None,
) -> int:
    """Increment one successful sale session for the context's stable profile.

    ``sold_listings`` is evidence only. Zero-listing scans are not successful
    sale sessions and therefore never increment the daily counter.
    """
    sold = int(sold_listings)
    app_dir = _app_dir_from_context(context)
    profile_id = str(getattr(context, "profile_id", "") or "")
    if sold <= 0:
        return read_daily_sale_count(app_dir, profile_id, now=now)

    current = _local_now(now)
    today = current.date().isoformat()
    path = counter_file_for_profile(app_dir, profile_id)

    # One AUTO worker owns one profile in normal Multi DEV operation. The
    # process lock protects nested/re-entrant calls; one-file-per-profile avoids
    # cross-account read/modify/write contention completely.
    with _PROCESS_LOCK:
        payload = _read_payload(path)
        previous = 0
        if str(payload.get("date") or "") == today:
            try:
                previous = max(0, int(payload.get("successful_sales", 0) or 0))
            except (TypeError, ValueError):
                previous = 0
        count = previous + 1
        data = {
            "version": _COUNTER_VERSION,
            "profile_id": profile_id,
            "date": today,
            "successful_sales": count,
            "updated_at": current.isoformat(timespec="seconds"),
            "last_client_pid": int(getattr(context, "pid", 0) or 0),
            "last_sold_listings": sold,
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
