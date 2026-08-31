from __future__ import annotations

from dataclasses import asdict, dataclass
import time
from typing import Any

MIN_FRIEND_ORDINAL = 1
MAX_FRIEND_ORDINAL = 500
MIN_STALL_ID = 1
MAX_STALL_ID = 4
MIN_INTERVAL_MINUTES = 5
MAX_INTERVAL_MINUTES = 1440


@dataclass(frozen=True)
class ClearStallJob:
    schema_version: int
    job_id: str
    clone_profile_id: str
    target_mode: str
    target_friend_ordinal: int
    target_stall_id: int
    buy_quantity: int
    max_scan_pages: int
    interval_minutes: int
    next_run_at: float
    close_client_after_run: bool
    enabled: bool
    last_checkpoint: str
    last_result: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def is_due(self, now: float | None = None) -> bool:
        current = time.time() if now is None else float(now)
        return self.enabled and self.next_run_at > 0 and self.next_run_at <= current


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def normalize_job(
    clone_profile_id: str,
    payload: Any = None,
    *,
    now: float | None = None,
) -> ClearStallJob:
    profile_id = str(clone_profile_id or "").strip()
    if not profile_id:
        raise ValueError("clone_profile_id không được trống")
    raw = payload if isinstance(payload, dict) else {}
    interval = _bounded_int(
        raw.get("interval_minutes", 65),
        65,
        MIN_INTERVAL_MINUTES,
        MAX_INTERVAL_MINUTES,
    )
    enabled = bool(raw.get("enabled", False))
    current = time.time() if now is None else float(now)
    try:
        next_run_at = float(raw.get("next_run_at", 0) or 0)
    except (TypeError, ValueError):
        next_run_at = 0
    if enabled and next_run_at <= 0:
        next_run_at = current + interval * 60
    if not enabled:
        next_run_at = 0
    return ClearStallJob(
        schema_version=2,
        job_id=str(raw.get("job_id") or f"clear-stall-{profile_id}"),
        clone_profile_id=profile_id,
        target_mode="friend_ordinal",
        target_friend_ordinal=_bounded_int(
            raw.get("target_friend_ordinal", 1),
            1,
            MIN_FRIEND_ORDINAL,
            MAX_FRIEND_ORDINAL,
        ),
        target_stall_id=_bounded_int(
            raw.get("target_stall_id", 2),
            2,
            MIN_STALL_ID,
            MAX_STALL_ID,
        ),
        buy_quantity=_bounded_int(raw.get("buy_quantity", 8), 8, 1, 999),
        max_scan_pages=_bounded_int(raw.get("max_scan_pages", 10), 10, 1, 50),
        interval_minutes=interval,
        next_run_at=next_run_at,
        close_client_after_run=bool(raw.get("close_client_after_run", True)),
        enabled=enabled,
        last_checkpoint=str(raw.get("last_checkpoint") or "WAITING"),
        last_result=raw.get("last_result"),
    )


def schedule_next(job: ClearStallJob, *, now: float | None = None) -> ClearStallJob:
    current = time.time() if now is None else float(now)
    payload = job.to_dict()
    payload["next_run_at"] = current + job.interval_minutes * 60
    payload["last_checkpoint"] = "WAITING"
    return normalize_job(job.clone_profile_id, payload, now=current)


def checkpoint(
    job: ClearStallJob,
    state: str,
    *,
    result: Any = None,
) -> ClearStallJob:
    state_name = str(state or "").strip().upper()
    if not state_name:
        raise ValueError("checkpoint không được trống")
    payload = job.to_dict()
    payload["last_checkpoint"] = state_name
    payload["last_result"] = result
    return normalize_job(job.clone_profile_id, payload)
