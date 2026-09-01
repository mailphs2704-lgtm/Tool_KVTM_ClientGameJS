from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


MIN_FRIEND_ORDINAL = 1
MAX_VERIFIED_FRIEND_ORDINAL = 7
MIN_RESALE_STORAGE_ID = 1
MAX_RESALE_STORAGE_ID = 5
MIN_BUY_QUANTITY = 1
MAX_BUY_QUANTITY = 999
STALL_VIEW_COUNT = 4
TOTAL_FRIEND_STALL_SLOTS = 20


@dataclass(frozen=True)
class ClearStallRequest:
    """Validated business input for one clone Dọn quầy session.

    ``resale_storage_id`` is the clean name for the historical UI field
    ``stall_id`` / ``buy_sell_friend_kho_id``. Reverse-engineered call flow
    shows that value is passed to the clone resale/storage selector; the friend
    side has one 20-slot stall. The old CLI name remains only at the worker/UI
    boundary so existing settings can migrate without data loss.
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
        if not MIN_FRIEND_ORDINAL <= friend <= MAX_VERIFIED_FRIEND_ORDINAL:
            raise ValueError(
                "Bản clean chỉ cho phép bạn bè số 1..7 vì đây là 7 vị trí "
                "đã xác nhận từ logic gốc; chưa suy đoán paging ngoài vùng này"
            )
        if not MIN_RESALE_STORAGE_ID <= storage <= MAX_RESALE_STORAGE_ID:
            raise ValueError("Kho VP bán lại phải trong khoảng 1..5")
        if not MIN_BUY_QUANTITY <= quantity <= MAX_BUY_QUANTITY:
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
