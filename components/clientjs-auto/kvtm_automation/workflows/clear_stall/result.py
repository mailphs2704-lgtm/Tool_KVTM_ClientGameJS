from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ClearStallResult:
    profile_id: str
    friend_ordinal: int
    resale_storage_id: int
    discovered_slots: int
    bought: int
    sold: int
    retained: int
    deferred: bool
    inventory_full: bool
    source_empty: bool
    probe_only: bool
    state: str
    planned_listings: int = 0
    planned_quantity: int = 0
    target_reached: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
