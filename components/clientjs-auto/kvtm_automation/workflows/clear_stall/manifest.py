from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import time
from typing import Any

from ...models import StallSlotObservation, VisualFingerprint


RESALE_BATCH_SIZE = 10


@dataclass
class PurchasedRecord:
    """One physical source listing or one persisted carryover VP group."""

    fingerprint: VisualFingerprint
    source_view: int
    source_local_slot: int
    source_physical_slot: int
    purchased_quantity: int = 0
    sold_quantity: int = 0

    @classmethod
    def from_observation(cls, observation: StallSlotObservation) -> "PurchasedRecord":
        return cls(
            fingerprint=observation.fingerprint,
            source_view=int(observation.view),
            source_local_slot=int(observation.local_slot),
            source_physical_slot=int(observation.physical_slot),
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PurchasedRecord":
        if not isinstance(payload, dict):
            raise ValueError("Record Dọn quầy không hợp lệ")
        record = cls(
            fingerprint=VisualFingerprint.from_dict(payload.get("fingerprint") or {}),
            source_view=max(0, int(payload.get("source_view") or 0)),
            source_local_slot=max(0, int(payload.get("source_local_slot") or 0)),
            source_physical_slot=max(0, int(payload.get("source_physical_slot") or 0)),
            purchased_quantity=max(0, int(payload.get("purchased_quantity") or 0)),
            sold_quantity=max(0, int(payload.get("sold_quantity") or 0)),
        )
        if record.sold_quantity > record.purchased_quantity:
            raise ValueError("Record Dọn quầy bán vượt số đã mua")
        return record

    @property
    def remaining_quantity(self) -> int:
        return max(0, self.purchased_quantity - self.sold_quantity)

    def record_purchase(self, quantity: int = 1) -> None:
        value = int(quantity)
        if value <= 0:
            raise ValueError("Số lượng mua xác nhận phải > 0")
        self.purchased_quantity += value

    def record_sale(self, quantity: int) -> None:
        value = int(quantity)
        if value <= 0 or value > self.remaining_quantity:
            raise RuntimeError("Số lượng bán không khớp record Dọn quầy")
        self.sold_quantity += value

    def carryover_copy(self) -> "PurchasedRecord | None":
        remaining = self.remaining_quantity
        if remaining <= 0:
            return None
        return PurchasedRecord(
            fingerprint=self.fingerprint,
            source_view=0,
            source_local_slot=0,
            source_physical_slot=0,
            purchased_quantity=remaining,
            sold_quantity=0,
        )


@dataclass(frozen=True)
class ResaleBatch:
    fingerprint: VisualFingerprint
    quantity: int = RESALE_BATCH_SIZE

    def __post_init__(self) -> None:
        if int(self.quantity) != RESALE_BATCH_SIZE:
            raise ValueError("Mỗi ô quầy phải treo đúng 10 VP")


@dataclass
class ClearStallManifest:
    profile_id: str
    friend_ordinal: int
    resale_storage_id: int
    requested_total: int
    created_at: float = field(default_factory=time.time)
    state: str = "CREATED"
    records: list[PurchasedRecord] = field(default_factory=list)
    error: str | None = None

    @property
    def purchased_total(self) -> int:
        return sum(record.purchased_quantity for record in self.records)

    @property
    def sold_total(self) -> int:
        return sum(record.sold_quantity for record in self.records)

    @property
    def remaining_total(self) -> int:
        return sum(record.remaining_quantity for record in self.records)

    @property
    def purchased_this_run(self) -> int:
        return sum(
            record.purchased_quantity
            for record in self.records
            if record.source_view > 0
        )

    def add_source(self, observation: StallSlotObservation) -> PurchasedRecord:
        record = PurchasedRecord.from_observation(observation)
        self.records.append(record)
        return record

    def add_carryover(self, record: PurchasedRecord) -> None:
        copy = record.carryover_copy()
        if copy is not None:
            self.records.append(copy)

    def _groups(self) -> list[tuple[VisualFingerprint, list[PurchasedRecord]]]:
        ordered: list[tuple[VisualFingerprint, list[PurchasedRecord]]] = []
        by_key: dict[str, list[PurchasedRecord]] = {}
        for record in self.records:
            if record.remaining_quantity <= 0:
                continue
            key = record.fingerprint.group_key
            if key not in by_key:
                by_key[key] = []
                ordered.append((record.fingerprint, by_key[key]))
            by_key[key].append(record)
        return ordered

    @property
    def sellable_remaining_total(self) -> int:
        total = 0
        for _fingerprint, records in self._groups():
            available = sum(record.remaining_quantity for record in records)
            total += (available // RESALE_BATCH_SIZE) * RESALE_BATCH_SIZE
        return total

    @property
    def planned_remainder_total(self) -> int:
        return max(0, self.remaining_total - self.sellable_remaining_total)

    def resale_batches(self) -> list[ResaleBatch]:
        batches: list[ResaleBatch] = []
        for fingerprint, records in self._groups():
            available = sum(record.remaining_quantity for record in records)
            batches.extend(
                ResaleBatch(fingerprint=fingerprint)
                for _ in range(available // RESALE_BATCH_SIZE)
            )
        return batches

    def record_group_sale(
        self,
        fingerprint: VisualFingerprint,
        quantity: int = RESALE_BATCH_SIZE,
    ) -> None:
        remaining = int(quantity)
        if remaining <= 0 or remaining % RESALE_BATCH_SIZE != 0:
            raise RuntimeError("Lô bán phải là bội số của 10 VP")
        matching = [
            record
            for record in self.records
            if record.fingerprint.group_key == fingerprint.group_key
            and record.remaining_quantity > 0
        ]
        available = sum(record.remaining_quantity for record in matching)
        if available < remaining:
            raise RuntimeError(
                f"Nhóm VP chỉ còn {available}, không đủ xác nhận bán {remaining}"
            )
        for record in matching:
            if remaining <= 0:
                break
            take = min(record.remaining_quantity, remaining)
            if take:
                record.record_sale(take)
                remaining -= take
        if remaining:
            raise RuntimeError("Không phân bổ hết lô bán vào manifest")

    def complete(self, *, deferred: bool = False) -> None:
        self.state = "COMPLETED_DEFERRED" if deferred else "COMPLETED"
        self.error = None

    def fail(self, error: Any) -> None:
        self.state = "FAILED"
        self.error = str(error)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)
