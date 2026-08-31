from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
import time
from typing import Any


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

    def complete(self) -> None:
        if self.sold_total != self.purchased_total:
            raise RuntimeError("Chưa bán lại đủ số lượng đã mua")
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
