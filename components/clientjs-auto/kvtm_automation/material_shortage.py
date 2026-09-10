from __future__ import annotations

from dataclasses import dataclass

from .errors import ScreenTimeout


__all__ = ["MaterialShortage", "MaterialShortageEvidence"]


@dataclass(frozen=True)
class MaterialShortageEvidence:
    """Visual/transaction evidence captured at the shortage popup boundary."""

    shortage_kind: str
    green_ratio: float
    completed_count: int
    target_count: int
    current_empty_slots: int
    drag_consumed_slot: bool


class MaterialShortage(ScreenTimeout):
    """Recoverable production stop caused by a crop/material shortage popup.

    ``material_template`` is the crop seed/template that must be replenished,
    while ``completed_count`` records how many production queue entries were
    individually verified before the popup. Recovery can therefore refill the
    correct crop and continue only the remaining production count instead of
    replaying the whole transaction.
    """

    def __init__(
        self,
        *,
        material_template: str,
        material_label: str,
        production_item_id: str,
        production_label: str,
        completed_count: int,
        target_count: int,
        evidence: MaterialShortageEvidence,
    ) -> None:
        self.material_template = str(material_template)
        self.material_label = str(material_label)
        self.production_item_id = str(production_item_id)
        self.production_label = str(production_label)
        self.completed_count = max(0, int(completed_count))
        self.target_count = max(0, int(target_count))
        self.evidence = evidence
        remaining = max(0, self.target_count - self.completed_count)
        super().__init__(
            f"{self.production_label}: {evidence.shortage_kind} • "
            f"thiếu/sắp hết {self.material_label} • "
            f"đã_xếp={self.completed_count}/{self.target_count} • còn={remaining}"
        )

    @property
    def remaining_count(self) -> int:
        return max(0, int(self.target_count) - int(self.completed_count))
