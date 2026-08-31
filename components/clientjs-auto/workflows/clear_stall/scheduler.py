from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Iterable

from .config import ClearStallJob, checkpoint, normalize_job, schedule_next

RUNNING_STATES = {
    "RESOLVING_CLONE",
    "OPENING_FRIEND_LIST",
    "LOCATING_FRIEND",
    "VERIFYING_TARGET",
    "OPENING_STALL",
    "CLEARING_STALL",
    "RETURNING_HOME",
    "CLOSING_CLIENT",
}
TERMINAL_STATES = {"COMPLETED", "FAILED", "CANCELLED"}


@dataclass(frozen=True)
class DueClearStallJob:
    profile_id: str
    job: ClearStallJob


def collect_due_jobs(
    raw_jobs: Any,
    *,
    now: float | None = None,
) -> list[DueClearStallJob]:
    """Normalize stored jobs and return enabled jobs whose schedule is due."""
    current = time.time() if now is None else float(now)
    if not isinstance(raw_jobs, dict):
        return []
    due: list[DueClearStallJob] = []
    for profile_id, payload in raw_jobs.items():
        try:
            job = normalize_job(str(profile_id), payload, now=current)
        except (TypeError, ValueError):
            continue
        if job.is_due(current):
            due.append(DueClearStallJob(profile_id=str(profile_id), job=job))
    return sorted(due, key=lambda item: (item.job.next_run_at, item.profile_id))


def mark_started(job: ClearStallJob) -> ClearStallJob:
    return checkpoint(job, "RESOLVING_CLONE")


def mark_failed(job: ClearStallJob, error: Any) -> ClearStallJob:
    return checkpoint(job, "FAILED", result={"ok": False, "error": str(error)})


def mark_completed(
    job: ClearStallJob,
    *,
    result: Any = None,
    now: float | None = None,
) -> ClearStallJob:
    completed = checkpoint(job, "COMPLETED", result={"ok": True, "data": result})
    return schedule_next(completed, now=now)


def any_profile_running(
    jobs: Iterable[ClearStallJob],
    profile_id: str,
) -> bool:
    target = str(profile_id)
    return any(
        job.clone_profile_id == target and job.last_checkpoint in RUNNING_STATES
        for job in jobs
    )
