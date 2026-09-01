from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ClearStallRequest:
    """Validated business input for one clone Dọn quầy session.

    `resale_storage_id` is the clean name for the historical UI/Auto Pro
    `stall_id` / `buy_sell_friend_kho_id` field. It selects the clone inventory
    category used when locating purchased VP for resale; it does not select a
    second physical friend stall.
    """

    profile_id: str
    friend_ordinal: int
    resale_storage_id: int
    buy_quantity: int
    work_dir: Path
    probe_only: bool = False

    def __post_init__(self) -> None:
        profile_id = str(self.profile_id).strip()
        if not profile_id:
            raise ValueError("Thiếu profile clone")
        friend = int(self.friend_ordinal)
        storage = int(self.resale_storage_id)
        quantity = int(self.buy_quantity)
        if not 1 <= friend <= 7:
            raise ValueError(
                "Bản clean hiện xác nhận an toàn bạn bè số 1..7 theo đúng "
                "specific_friend_pos của Auto Pro"
            )
        if not 1 <= storage <= 4:
            raise ValueError("Kho bán lại phải trong khoảng 1..4")
        if not 1 <= quantity <= 999:
            raise ValueError("Số lượng mua phải trong khoảng 1..999")
        object.__setattr__(self, "profile_id", profile_id)
        object.__setattr__(self, "friend_ordinal", friend)
        object.__setattr__(self, "resale_storage_id", storage)
        object.__setattr__(self, "buy_quantity", quantity)
        object.__setattr__(self, "work_dir", Path(self.work_dir).resolve())
        object.__setattr__(self, "probe_only", bool(self.probe_only))

    @property
    def legacy_stall_id(self) -> int:
        """Compatibility alias used only at worker/UI boundaries."""
        return self.resale_storage_id
