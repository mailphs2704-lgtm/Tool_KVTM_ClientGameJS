from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
import time
from typing import Any


RESALE_BATCH_SIZE = 10


@dataclass(frozen=True)
class ItemFingerprint:
    """Stable identity derived from the item icon captured at the source stall."""

    sha256: str
    perceptual_hash: str
    width: int
    height: int
    template_file: str

    @classmethod
    def from_bgra(
        cls,
        raw: bytes,
        width: int,
        height: int,
        template_file: str,
    ) -> "ItemFingerprint":
        if width <= 0 or height <= 0 or not raw:
            raise ValueError("Ảnh vật phẩm không hợp lệ")
        return cls(
            sha256=hashlib.sha256(raw).hexdigest(),
            perceptual_hash=_average_hash_bgr(raw, width, height),
            width=int(width),
            height=int(height),
            template_file=str(template_file),
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ItemFingerprint":
        if not isinstance(payload, dict):
            raise ValueError("Fingerprint carryover không hợp lệ")
        sha256 = str(payload.get("sha256") or "")
        perceptual_hash = str(payload.get("perceptual_hash") or "")
        width = int(payload.get("width") or 0)
        height = int(payload.get("height") or 0)
        if len(sha256) != 64 or len(perceptual_hash) != 16:
            raise ValueError("Fingerprint carryover thiếu mã nhận dạng")
        if width <= 0 or height <= 0:
            raise ValueError("Fingerprint carryover thiếu kích thước")
        return cls(
            sha256=sha256,
            perceptual_hash=perceptual_hash,
            width=width,
            height=height,
            template_file=str(payload.get("template_file") or ""),
        )

    @property
    def group_key(self) -> str:
        """Conservative item-type key: never combine visually different VP."""
        return self.perceptual_hash


@dataclass
class PurchasedItem:
    fingerprint: ItemFingerprint
    source_page: int
    source_slot: int
    requested_quantity: int
    inventory_before: int | None = None
    inventory_after: int | None = None
    purchased_quantity: int = 0
    sold_quantity: int = 0

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PurchasedItem":
        if not isinstance(payload, dict):
            raise ValueError("Vật phẩm carryover không hợp lệ")
        item = cls(
            fingerprint=ItemFingerprint.from_dict(payload.get("fingerprint") or {}),
            source_page=max(1, int(payload.get("source_page") or 1)),
            source_slot=max(1, int(payload.get("source_slot") or 1)),
            requested_quantity=max(1, int(payload.get("requested_quantity") or 1)),
            inventory_before=None,
            inventory_after=None,
            purchased_quantity=max(0, int(payload.get("purchased_quantity") or 0)),
            sold_quantity=max(0, int(payload.get("sold_quantity") or 0)),
        )
        if item.purchased_quantity <= 0:
            raise ValueError("Carryover không có số lượng đã mua")
        if item.sold_quantity > item.purchased_quantity:
            raise ValueError("Carryover có số lượng đã bán vượt số đã mua")
        return item

    def record_purchase(self, before: int, after: int) -> None:
        before_value, after_value = int(before), int(after)
        delta = after_value - before_value
        if delta <= 0:
            raise RuntimeError("Không xác nhận được số lượng vật phẩm vừa mua")
        if delta > self.requested_quantity:
            raise RuntimeError("Số lượng tăng vượt mức đã yêu cầu")
        self.inventory_before = before_value
        self.inventory_after = after_value
        self.purchased_quantity = delta

    @property
    def remaining_to_sell(self) -> int:
        return max(0, self.purchased_quantity - self.sold_quantity)

    def record_sale(self, quantity: int) -> None:
        value = int(quantity)
        if value <= 0 or value > self.remaining_to_sell:
            raise RuntimeError("Số lượng bán không khớp manifest giao dịch")
        self.sold_quantity += value

    def carryover_copy(self) -> "PurchasedItem | None":
        remaining = self.remaining_to_sell
        if remaining <= 0:
            return None
        return PurchasedItem(
            fingerprint=self.fingerprint,
            source_page=self.source_page,
            source_slot=self.source_slot,
            requested_quantity=remaining,
            purchased_quantity=remaining,
        )


@dataclass(frozen=True)
class ResaleBatch:
    """One own-stall slot: exactly ten VP of one fingerprint group."""

    fingerprint: ItemFingerprint
    quantity: int = RESALE_BATCH_SIZE

    def __post_init__(self) -> None:
        if int(self.quantity) != RESALE_BATCH_SIZE:
            raise ValueError("Một ô quầy Dọn quầy phải bán đúng 10 VP")


@dataclass
class TransactionManifest:
    profile_id: str
    target_friend_ordinal: int
    target_stall_id: int
    requested_total: int
    created_at: float = field(default_factory=time.time)
    state: str = "CREATED"
    items: list[PurchasedItem] = field(default_factory=list)
    error: str | None = None

    @property
    def purchased_total(self) -> int:
        return sum(item.purchased_quantity for item in self.items)

    @property
    def sold_total(self) -> int:
        return sum(item.sold_quantity for item in self.items)

    @property
    def remaining_total(self) -> int:
        return max(0, self.purchased_total - self.sold_total)

    def _groups(self) -> list[tuple[ItemFingerprint, list[PurchasedItem]]]:
        """Group only exact perceptual hashes; false merging is worse than deferring."""
        ordered: list[tuple[ItemFingerprint, list[PurchasedItem]]] = []
        by_key: dict[str, list[PurchasedItem]] = {}
        representatives: dict[str, ItemFingerprint] = {}
        for item in self.items:
            key = item.fingerprint.group_key
            if key not in by_key:
                by_key[key] = []
                representatives[key] = item.fingerprint
                ordered.append((item.fingerprint, by_key[key]))
            by_key[key].append(item)
        return ordered

    @property
    def sellable_total(self) -> int:
        """Count full groups of ten independently for each VP type."""
        total = 0
        for _fingerprint, items in self._groups():
            quantity = sum(item.purchased_quantity for item in items)
            total += (quantity // RESALE_BATCH_SIZE) * RESALE_BATCH_SIZE
        return total

    @property
    def planned_remainder_total(self) -> int:
        return max(0, self.purchased_total - self.sellable_total)

    @property
    def retained_total(self) -> int:
        """Actual unsold VP after the current resale attempt."""
        return self.remaining_total

    def resale_batches(self) -> list[ResaleBatch]:
        batches: list[ResaleBatch] = []
        for fingerprint, items in self._groups():
            purchased = sum(item.purchased_quantity for item in items)
            sold = sum(item.sold_quantity for item in items)
            available = max(0, purchased - sold)
            batch_count = available // RESALE_BATCH_SIZE
            batches.extend(
                ResaleBatch(fingerprint=fingerprint)
                for _ in range(batch_count)
            )
        return batches

    def add_item(self, item: PurchasedItem) -> None:
        if self.state not in {"CREATED", "BUYING"}:
            raise RuntimeError("Không thể thêm vật phẩm sau giai đoạn mua")
        if item.source_page < 1 or item.source_slot < 1:
            raise ValueError("Trang và ô vật phẩm phải bắt đầu từ 1")
        self.items.append(item)
        self.state = "BUYING"

    def begin_resale(self) -> None:
        if self.purchased_total <= 0:
            raise RuntimeError("Không có giao dịch mua đã xác nhận")
        self.state = "RESELLING"

    def record_group_sale(
        self,
        fingerprint: ItemFingerprint,
        quantity: int = RESALE_BATCH_SIZE,
    ) -> None:
        remaining = int(quantity)
        if remaining <= 0 or remaining % RESALE_BATCH_SIZE != 0:
            raise RuntimeError("Lô bán lại phải là bội số của 10 VP")
        matching = [
            item for item in self.items
            if item.fingerprint.group_key == fingerprint.group_key
        ]
        available = sum(item.remaining_to_sell for item in matching)
        if available < remaining:
            raise RuntimeError(
                f"Nhóm VP chỉ còn {available}, không đủ xác nhận bán {remaining}"
            )
        for item in matching:
            if remaining <= 0:
                break
            take = min(item.remaining_to_sell, remaining)
            if take > 0:
                item.record_sale(take)
                remaining -= take
        if remaining:
            raise RuntimeError("Không phân bổ hết số lượng đã bán vào manifest")

    def complete(self) -> None:
        if self.sold_total != self.sellable_total:
            raise RuntimeError(
                "Chưa bán lại đủ các lô 10 VP đã xác nhận theo từng loại"
            )
        self.state = "COMPLETED"

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


def _average_hash_bgr(raw: bytes, width: int, height: int) -> str:
    """Dependency-free 8x8 average hash for BGR or BGRA ClientJS captures."""
    pixels = int(width) * int(height)
    channels = len(raw) // pixels if pixels else 0
    if channels not in {3, 4} or len(raw) < pixels * channels:
        raise ValueError("Ảnh BGR/BGRA không đủ dữ liệu")
    values = []
    for out_y in range(8):
        source_y = min(height - 1, int((out_y + 0.5) * height / 8))
        for out_x in range(8):
            source_x = min(width - 1, int((out_x + 0.5) * width / 8))
            offset = (source_y * width + source_x) * channels
            blue, green, red = raw[offset : offset + 3]
            values.append((int(red) * 30 + int(green) * 59 + int(blue) * 11) // 100)
    average = sum(values) / len(values)
    bits = 0
    for value in values:
        bits = (bits << 1) | int(value >= average)
    return f"{bits:016x}"


def hamming_distance(first: str, second: str) -> int:
    return (int(first, 16) ^ int(second, 16)).bit_count()
