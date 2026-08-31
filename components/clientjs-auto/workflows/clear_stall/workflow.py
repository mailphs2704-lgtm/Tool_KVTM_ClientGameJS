from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
from typing import Callable

from .adapter import AutoProNavigationAdapter
from .detector import DetectedSlot, StallScanner
from .manifest import PurchasedItem, TransactionManifest
from .transaction import VisualTransactionExecutor


@dataclass(frozen=True)
class ClearStallRequest:
    profile_id: str
    friend_ordinal: int
    stall_id: int
    buy_quantity: int
    max_scan_pages: int
    work_dir: Path

    def validate(self) -> None:
        if not str(self.profile_id).strip():
            raise ValueError("Thiếu profile clone")
        if not 1 <= int(self.friend_ordinal) <= 500:
            raise ValueError("Bạn bè số phải trong khoảng 1..500")
        if not 1 <= int(self.stall_id) <= 4:
            raise ValueError("Quầy phải trong khoảng 1..4")
        if not 1 <= int(self.buy_quantity) <= 999:
            raise ValueError("Số lượng mua phải trong khoảng 1..999")
        if not 1 <= int(self.max_scan_pages) <= 50:
            raise ValueError("Số trang quét phải trong khoảng 1..50")


class ClearStallWorkflow:
    """Own the Dọn quầy state machine; legacy AUTO PRO never owns the loop."""

    def __init__(
        self,
        request: ClearStallRequest,
        adapter: AutoProNavigationAdapter,
        *,
        stop_event: threading.Event,
        logger: Callable[[str], None],
    ) -> None:
        request.validate()
        self.request = request
        self.adapter = adapter
        self.stop_event = stop_event
        self.log = logger
        self.manifest_path = Path(request.work_dir) / "transaction.json"
        self.scanner = StallScanner(Path(request.work_dir) / "templates")
        self.manifest = TransactionManifest(
            profile_id=request.profile_id,
            target_friend_ordinal=int(request.friend_ordinal),
            target_stall_id=int(request.stall_id),
            requested_total=int(request.buy_quantity),
        )
        self.last_unique_page = 0

    def discover_source_items(self) -> list[DetectedSlot]:
        """Enter the target stall and scan pages before allowing a purchase."""
        self._checkpoint("NAVIGATING_FRIEND")
        self.adapter.configure_target(
            self.request.friend_ordinal, self.request.stall_id
        )
        self.adapter.go_to_friend_home(self.request.friend_ordinal)
        self._checkpoint("OPENING_SOURCE_STALL")
        self.adapter.open_target_stall(self.request.stall_id)

        detected: list[DetectedSlot] = []
        for page in range(1, int(self.request.max_scan_pages) + 1):
            self._ensure_running()
            self._checkpoint(f"SCANNING_PAGE_{page}")
            scan = self.scanner.scan_page(self.adapter.screenshot(), page)
            if self.scanner.page_was_seen(scan):
                self.log(f"Dừng quét: trang {page} đã xuất hiện trước đó")
                break
            detected.extend(scan.slots)
            self.last_unique_page = page
            self.log(
                f"Trang {page}: nhận dạng {len(scan.slots)} vật phẩm mới"
            )
            if not scan.slots and page > 1:
                self.log(f"Dừng quét: trang {page} không còn vật phẩm")
                break
            self.adapter.swipe_next_stall_page()
        if not detected:
            raise RuntimeError("Không nhận dạng được vật phẩm nào trên quầy nguồn")
        self._checkpoint("SOURCE_SCAN_COMPLETE")
        return detected

    def prepare_manifest_items(
        self, detected: list[DetectedSlot]
    ) -> list[PurchasedItem]:
        """Create pending records; quantities remain zero until purchase proof."""
        remaining = int(self.request.buy_quantity)
        pending = []
        for slot in detected:
            if remaining <= 0:
                break
            requested = remaining
            item = PurchasedItem(
                fingerprint=slot.fingerprint,
                source_page=slot.page,
                source_slot=slot.slot,
                requested_quantity=requested,
            )
            self.manifest.add_item(item)
            pending.append(item)
            # The exact amount available in a stall slot is unknown until the
            # purchase dialog/inventory delta is read. Do not decrement here.
        self.manifest.save(self.manifest_path)
        return pending

    def execute_purchases(
        self,
        pending: list[PurchasedItem],
        executor: VisualTransactionExecutor,
    ) -> int:
        """Buy at most requested_total listings and prove every accepted click."""
        for _ in range(max(0, self.last_unique_page - 1)):
            self.adapter.swipe_previous_stall_page()
        current_page = 1
        purchased = 0
        for item in pending:
            self._ensure_running()
            if purchased >= int(self.request.buy_quantity):
                break
            while current_page < item.source_page:
                self.adapter.swipe_next_stall_page()
                current_page += 1
            self._checkpoint(
                f"BUYING_PAGE_{item.source_page}_SLOT_{item.source_slot}"
            )
            executor.purchase_listing(item)
            # One confirmed source listing counts as one requested VP. The
            # manifest never assumes the contents of an unconfirmed click.
            self.mark_purchase_verified(
                item,
                inventory_before=purchased,
                inventory_after=purchased + 1,
            )
            purchased += 1
        if purchased <= 0:
            raise RuntimeError("Không có giao dịch mua nào được xác nhận")
        self._checkpoint("PURCHASE_COMPLETE")
        return purchased

    def mark_purchase_verified(
        self,
        item: PurchasedItem,
        *,
        inventory_before: int,
        inventory_after: int,
    ) -> None:
        item.record_purchase(inventory_before, inventory_after)
        self.manifest.save(self.manifest_path)
        self.log(
            f"Đã xác nhận mua {item.purchased_quantity} tại "
            f"trang {item.source_page}, ô {item.source_slot}"
        )

    def begin_resale(self) -> None:
        self.manifest.begin_resale()
        self.manifest.save(self.manifest_path)
        self._checkpoint("RETURNING_TO_CLONE")
        self.adapter.return_to_clone_home()
        self._checkpoint("READY_TO_RESELL")

    def execute_resale(
        self,
        executor: VisualTransactionExecutor,
    ) -> int:
        """Return home and sell only manifest fingerprints, one proof at a time."""
        self.begin_resale()
        self.adapter.open_clone_stall_for_sale(self.request.stall_id)
        sold = 0
        for item in self.manifest.items:
            self._ensure_running()
            while item.remaining_to_sell > 0:
                self._checkpoint(
                    f"SELLING_SOURCE_PAGE_{item.source_page}_SLOT_{item.source_slot}"
                )
                executor.sell_manifest_item(item)
                self.mark_sale_verified(item, 1)
                sold += 1
        if sold != self.manifest.purchased_total:
            raise RuntimeError(
                f"Số lượng bán {sold} không khớp số đã mua "
                f"{self.manifest.purchased_total}"
            )
        self.complete()
        return sold

    def mark_sale_verified(self, item: PurchasedItem, quantity: int) -> None:
        item.record_sale(quantity)
        self.manifest.save(self.manifest_path)

    def complete(self) -> None:
        self.manifest.complete()
        self.manifest.save(self.manifest_path)
        self._checkpoint("COMPLETED")

    def fail(self, error: Exception) -> None:
        self.manifest.fail(error)
        self.manifest.save(self.manifest_path)
        self.log(f"Dọn quầy dừng an toàn: {error}")

    def _checkpoint(self, state: str) -> None:
        self.manifest.state = state
        self.manifest.save(self.manifest_path)
        self.log(state)

    def _ensure_running(self) -> None:
        if self.stop_event.is_set():
            raise InterruptedError("Dọn quầy đã được yêu cầu dừng")
