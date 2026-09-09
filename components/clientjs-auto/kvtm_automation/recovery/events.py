from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class RecoveryEventKind(str, Enum):
    """Stable recovery events emitted around recoverable runtime transitions."""

    UNKNOWN_CAMERA = "unknown_camera"
    WRONG_PRODUCTION_MACHINE = "wrong_production_machine"
    INVENTORY_FULL = "inventory_full"
    MAIN_PROVEN = "main_proven"
    FLOOR_REENTERED = "floor_reentered"
    RECOVERY_EXHAUSTED = "recovery_exhausted"


@dataclass(frozen=True)
class RecoveryEvent:
    """Read-only event passed to optional Function/Recipe recovery hooks.

    Event hooks are observers, not policy overrides. They are useful for a future
    Function that needs extra logging/state bookkeeping at one recovery position
    without copying navigation or production-recovery logic into the Function.
    """

    kind: RecoveryEventKind
    label: str
    floor: int | None = None
    attempt: int | None = None
    error: str | None = None
    details: Mapping[str, object] = field(default_factory=dict)
