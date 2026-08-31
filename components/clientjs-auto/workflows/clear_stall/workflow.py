from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import threading
import time
from typing import Callable

from .adapter import AutoProNavigationAdapter
from .detector import (
    DetectedSlot,
    StallScanner,
    TOTAL_STALL_SLOTS,
    VISIBLE_STALL_SLOTS,
)
from .manifest import ItemFingerprint, PurchasedItem, TransactionManifest
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
            raise ValueError("Số lượt quét an toàn phải trong khoảng 1..50")


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
        self.work_dir = Path(request.work_dir)
        self.manifest_path = self.work_dir / "transaction.json"
        self.carryover_path = self.work_dir.parent / "carryover.json"
        self.scanner = StallScanner(self.work_dir / "templates")
        self.manifest = TransactionManifest(
            profile_id=request.profile_id,
            target_friend_ordinal=int(request.friend_ordinal),
            target_stall_id=int(request.stall_id),
            requested_total=int(request.buy_quantity),
        )
        self.last_unique_page = 0
        self.forward_swipes = 0
        carryover = self._load_carryover()
        if carryover > 0:
            self.log(f"Đã nạp {carryover} VP lẻ từ lượt Dọn quầy trước")

    def discover_source_items(self) -> list[DetectedSlot]:
        """Scan the twenty physical friend-stall positions without overlap duplicates."""
        self._checkpoint("WAITING_MAIN_SCREEN")
        self.adapter.ensure_main_screen()
        self._checkpoint("NAVIGATING_FRIEND")
        self.adapter.configure_target(
            self.request.friend_ordinal, self.request.stall_id
        )
        self.adapter.go_to_friend_home(self.request.friend_ordinal)
        self._checkpoint("OPENING_SOURCE_STALL")
        self.adapter.open_target_stall(self.request.stall_id)

        detected: list[DetectedSlot] = []
        previous_scan = None
        covered_slots = 0
        self.forward_swipes = 0
        max_views = max(TOTAL_STALL_SLOTS, int(self.request.max_scan_pages))

        for view in range(1, max_views + 1):
            self._ensure_running()
            self._checkpoint(f"SCANNING_VIEW_{view}")
            scan = self.scanner.scan_page(self.adapter.screenshot(), view)

            if previous_scan is None:
                new_local_slots = list(range(1, VISIBLE_STALL_SLOTS + 1))
                covered_slots = min(TOTAL_STALL_SLOTS, VISIBLE_STALL_SLOTS)
                self.last_unique_page = 1
            else:
                shift = self.scanner.infer_forward_shift(previous_scan, scan)
                if shift == 0:
                    if not previous_scan.slots and not scan.slots:
                        # Identical empty windows are visually ambiguous. Count
                        # only one conservative physical position so we keep
                        # swiping instead of pretending eight unseen slots moved.
                        shift = 1
                        self.log(
                            "Hai cửa sổ quầy đều trống; tính tiến tối thiểu 1 ô để tiếp tục quét"
                        )
                    elif covered_slots < TOTAL_STALL_SLOTS:
                        raise RuntimeError(
                            f"Quầy không dịch sau swipe khi mới phủ {covered_slots}/20 ô"
                        )
                    else:
                        break

                overlap = VISIBLE_STALL_SLOTS - shift
                needed = min(shift, TOTAL_STALL_SLOTS - covered_slots)
                new_local_slots = list(
                    range(overlap + 1, overlap + needed + 1)
                )
                covered_slots += needed
                self.forward_swipes += 1
                self.last_unique_page = view

            new_local_set = set(new_local_slots)
            new_items = [slot for slot in scan.slots if slot.slot in new_local_set]
            detected.extend(new_items)
            self.log(
                f"Cửa sổ {view}: thêm {len(new_local_slots)} vị trí, "
                f"{len(new_items)} VP • đã phủ {covered_slots}/{TOTAL_STALL_SLOTS} ô"
            )

            if covered_slots >= TOTAL_STALL_SLOTS:
                break

            previous_scan = scan
            self.adapter.swipe_next_stall_page()
        else:
            raise RuntimeError(
                f"Vượt {max_views} lượt swipe nhưng chưa phủ đủ 20 ô quầy"
            )

        if covered_slots < TOTAL_STALL_SLOTS:
            raise RuntimeError(
                f"Chỉ xác nhận được {covered_slots}/{TOTAL_STALL_SLOTS} ô quầy nguồn"
            )
        if not detected:
            if self.manifest.purchased_total > 0:
                self.log(
                    "20 ô quầy nguồn không có VP mới; tiếp tục xử lý carryover trong kho"
                )
                self._checkpoint("SOURCE_SCAN_EMPTY_CARRYOVER_ONLY")
                return []
            raise RuntimeError("20 ô quầy nguồn không có vật phẩm để mua")
        self._checkpoint("SOURCE_SCAN_COMPLETE_20_SLOTS")
        return detected

    def prepare_manifest_items(
        self, detected: list[DetectedSlot]
    ) -> list[PurchasedItem]:
        """Create pending records; quantities remain zero until purchase proof."""
        pending = []
        for slot in detected:
            item = PurchasedItem(
                fingerprint=slot.fingerprint,
                source_page=slot.page,
                source_slot=slot.slot,
                requested_quantity=int(self.request.buy_quantity),
            )
            self.manifest.add_item(item)
            pending.append(item)
        self.manifest.save(self.manifest_path)
        return pending

    def execute_purchases(
        self,
        pending: list[PurchasedItem],
        executor: VisualTransactionExecutor,
    ) -> int:
        """Buy at most requested_total unique physical listings."""
        if not pending and self.manifest.purchased_total > 0:
            self._checkpoint("PURCHASE_SKIPPED_CARRYOVER_ONLY")
            return 0

        # Return from the final scanned window to the first one using exactly
        # the number of forward windows that were confirmed as moving.
        for _ in range(self.forward_swipes):
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
                f"BUYING_VIEW_{item.source_page}_SLOT_{item.source_slot}"
            )
            executor.purchase_listing(item)
            # One confirmed source listing counts as one configured VP unit.
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
        self._save_carryover()
        self.log(
            f"Đã xác nhận mua {item.purchased_quantity} tại "
            f"cửa sổ {item.source_page}, ô {item.source_slot}"
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
        """Place one own-stall slot for each complete group of ten of one VP type."""
        self.begin_resale()
        batches = self.manifest.resale_batches()
        planned_remainder = self.manifest.planned_remainder_total
        if not batches:
            self.log(
                f"Giữ lại {self.manifest.retained_total} VP trong kho; "
                "chưa có loại VP nào đủ 10"
            )
            self.complete()
            return 0

        self.adapter.open_clone_stall_for_sale(self.request.stall_id)
        sold = 0
        for index, batch in enumerate(batches, start=1):
            self._ensure_running()
            self._checkpoint(f"SELLING_BATCH_{index}_QTY_{batch.quantity}")
            executor.sell_manifest_batch(batch.fingerprint, batch.quantity)
            self.mark_sale_verified(batch.fingerprint, batch.quantity)
            sold += batch.quantity

        if sold != self.manifest.sellable_total:
            raise RuntimeError(
                f"Số lượng bán {sold} không khớp kế hoạch "
                f"{self.manifest.sellable_total} theo từng loại VP"
            )
        if planned_remainder > 0:
            self.log(
                f"Giữ lại {planned_remainder} VP lẻ (<10 theo từng loại) cho lượt sau"
            )
        self.complete()
        return sold

    def mark_sale_verified(
        self,
        fingerprint: ItemFingerprint,
        quantity: int,
    ) -> None:
        self.manifest.record_group_sale(fingerprint, quantity)
        self.manifest.save(self.manifest_path)
        self._save_carryover()

    def complete(self) -> None:
        self.manifest.complete()
        self.manifest.save(self.manifest_path)
        self._save_carryover()
        self._checkpoint("COMPLETED")

    def fail(self, error: Exception) -> None:
        self.manifest.fail(error)
        self.manifest.save(self.manifest_path)
        self._save_carryover()
        self.log(f"Dọn quầy dừng an toàn: {error}")

    def _load_carryover(self) -> int:
        try:
            payload = json.loads(self.carryover_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return 0
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Không đọc được carryover Dọn quầy: {exc}") from exc
        if not isinstance(payload, dict) or int(payload.get("version") or 0) != 1:
            raise RuntimeError("Carryover Dọn quầy sai phiên bản")
        if str(payload.get("profile_id") or "") != str(self.request.profile_id):
            raise RuntimeError("Carryover Dọn quầy không thuộc profile hiện tại")
        raw_items = payload.get("items")
        if not isinstance(raw_items, list):
            raise RuntimeError("Carryover Dọn quầy thiếu danh sách vật phẩm")
        loaded = 0
        for raw in raw_items:
            item = PurchasedItem.from_dict(raw)
            copy = item.carryover_copy()
            if copy is None:
                continue
            self.manifest.items.append(copy)
            loaded += copy.purchased_quantity
        return loaded

    def _save_carryover(self) -> None:
        pending = []
        for item in self.manifest.items:
            copy = item.carryover_copy()
            if copy is not None:
                pending.append(copy)
        if not pending:
            try:
                self.carryover_path.unlink(missing_ok=True)
            except OSError:
                pass
            return
        payload = {
            "version": 1,
            "profile_id": str(self.request.profile_id),
            "updated_at": time.time(),
            "items": [asdict(item) for item in pending],
        }
        self.carryover_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.carryover_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.carryover_path)

    def _checkpoint(self, state: str) -> None:
        self.manifest.state = state
        self.manifest.save(self.manifest_path)
        self.log(state)

    def _ensure_running(self) -> None:
        if self.stop_event.is_set():
            raise InterruptedError("Dọn quầy đã được yêu cầu dừng")
