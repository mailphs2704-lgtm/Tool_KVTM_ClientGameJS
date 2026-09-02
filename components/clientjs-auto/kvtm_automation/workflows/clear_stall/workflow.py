from __future__ import annotations

from pathlib import Path
from typing import Callable

from ...automation import KVAutomation
from ...errors import (
    AutomationStopped,
    InsufficientBatch,
    InventoryFull,
    NoEmptyStallSlot,
)
from ...models import StallSlotObservation
from .config import ClearStallRequest, LISTING_QUANTITY
from .manifest import ClearStallManifest, PurchasedRecord
from .result import ClearStallResult
from .state import CarryoverStore


class ClearStallWorkflow:
    """Standalone Dọn quầy state machine built only on clean KVAutomation APIs.

    Business contract:
    1. enter the selected clone and recover to the farm screen;
    2. visit configured friend houses sequentially until the target is met;
    3. re-enter/scroll stalls as needed; account slot capacity is never assumed;
    4. count each verified x10 listing as ten VP toward `buy_quantity`;
    5. return to the clone home;
    6. group identical VP with carryover from previous runs;
    7. sell only full groups of ten into empty own-stall slots;
    8. keep every remainder below ten (or temporarily unsellable batch) for a later run.
    """

    def __init__(
        self,
        request: ClearStallRequest,
        automation: KVAutomation,
        *,
        result_reporter: Callable[[dict], None] | None = None,
    ) -> None:
        self.request = request
        self.automation = automation
        self.context = automation.context
        self.result_reporter = result_reporter

        self.work_dir = Path(request.work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.template_dir = self.work_dir / "templates"
        self.capture_dir = self.work_dir / "captures"
        self.manifest_path = self.work_dir / "transaction.json"

        # Preferred layout is <profile>/runs/<timestamp>. Accept a direct run
        # directory as well so tests/tools do not depend on filesystem naming.
        if self.work_dir.parent.name.lower() == "runs":
            self.profile_root = self.work_dir.parent.parent
        else:
            self.profile_root = self.work_dir.parent
        self.carryover = CarryoverStore(self.profile_root)

        self.manifest = ClearStallManifest(
            profile_id=request.profile_id,
            friend_ordinal=request.friend_ordinal,
            resale_storage_id=request.resale_storage_id,
            requested_total=request.buy_quantity,
        )
        if not request.probe_only:
            loaded = self.carryover.load(request.profile_id)
            for record in loaded:
                self.manifest.add_carryover(record)
            if loaded:
                self.context.log(
                    f"Đã nạp {sum(item.remaining_quantity for item in loaded)} "
                    "VP carryover từ phiên trước"
                )
        self._save_manifest()

    def probe(self) -> ClearStallResult:
        """Read-only navigation/20-slot scan. Never purchases, sells or writes carryover."""
        if not self.request.probe_only:
            raise RuntimeError("probe() chỉ dùng với request.probe_only=True")
        observations = self._discover_source()
        # Leave the shop in a predictable first-view position for diagnostics.
        self.automation.stall.rewind_to_first(4)
        planned_listings = min(
            len(observations), self.request.target_listing_count
        )
        planned_quantity = planned_listings * 10
        target_reached = planned_listings == self.request.target_listing_count
        self.context.log(
            "GATE 1 kế hoạch READ-ONLY: "
            f"{planned_listings}/{self.request.target_listing_count} ô x10 • "
            f"{planned_quantity}/{self.request.buy_quantity} VP • "
            f"target={'ĐỦ' if target_reached else 'THIẾU'}"
        )
        self.manifest.complete()
        self._save_manifest()
        return self._result(
            discovered_slots=len(observations),
            bought=0,
            sold=0,
            retained=0,
            deferred=False,
            inventory_full=False,
            source_empty=not observations,
            state="PROBE_COMPLETED",
            planned_listings=planned_listings,
            planned_quantity=planned_quantity,
            target_reached=target_reached,
        )

    def run(self) -> ClearStallResult:
        if self.request.probe_only:
            return self.probe()

        inventory_full = False
        deferred = False
        source_empty = False
        observations: list[StallSlotObservation] = []
        bought = 0
        sold = 0

        try:
            observations = self._discover_source()
            source_empty = not observations
            bought, inventory_full = self._purchase(observations)

            self._checkpoint("RETURNING_TO_CLONE")
            self.automation.navigation.return_home()

            sold, deferred = self._resell()
            self.manifest.complete(deferred=deferred)
            self._persist_state()
            self._checkpoint(
                "COMPLETED_DEFERRED" if deferred else "COMPLETED",
                save_state=False,
            )
            return self._result(
                discovered_slots=len(observations),
                bought=bought,
                sold=sold,
                retained=self.manifest.remaining_total,
                deferred=deferred,
                inventory_full=inventory_full,
                source_empty=source_empty,
                state=self.manifest.state,
            )
        except AutomationStopped:
            # Purchases/sales already confirmed before the stop stay persisted.
            self.manifest.state = "STOPPED"
            self._persist_state()
            self._save_manifest()
            raise
        except Exception as exc:
            self.manifest.fail(exc)
            self._persist_state()
            self._save_manifest()
            raise

    def _discover_source(self) -> list[StallSlotObservation]:
        self._checkpoint("WAITING_MAIN_SCREEN", save_state=False)
        self.automation.ensure_main_screen(timeout=90.0)

        self._checkpoint("NAVIGATING_FRIEND", save_state=False)
        self.automation.navigation.go_to_friend(self.request.friend_ordinal)

        self._checkpoint("OPENING_SOURCE_STALL", save_state=False)
        self.automation.stall.open_friend_stall()

        self._checkpoint("SCANNING_20_SLOTS", save_state=False)
        observations = list(
            self.automation.stall.scan_all_20(
                self.template_dir,
                capture_dir=self.capture_dir,
            )
        )
        self.context.log(
            f"Quét xong 20 ô vật lý • phát hiện {len(observations)} ô có VP"
        )
        self._checkpoint("SOURCE_SCAN_COMPLETE", save_state=False)
        return observations

    def _purchase(
        self,
        observations: list[StallSlotObservation],
    ) -> tuple[int, bool]:
        """Buy verified x10 listings and report quantities in VP, not clicks."""
        # scan_all_20 leaves the physical shop at view four.
        self.automation.stall.rewind_to_first(4)
        if not observations:
            self._checkpoint("PURCHASE_SKIPPED_SOURCE_EMPTY")
            return 0, False

        source_records: dict[int, PurchasedRecord] = {
            observation.physical_slot: self.manifest.add_source(observation)
            for observation in observations
        }
        self._persist_state()
        self._checkpoint("PURCHASE_STARTED", save_state=False)

        current_view = 1
        purchased_quantity = 0
        inventory_full = False
        for observation in sorted(observations, key=lambda item: item.physical_slot):
            self.context.ensure_running()
            remaining_quantity = self.request.buy_quantity - purchased_quantity
            remaining_listings = remaining_quantity // LISTING_QUANTITY
            if remaining_listings <= 0:
                break
            while current_view < observation.view:
                self.automation.stall.next_view()
                current_view += 1

            record = source_records[observation.physical_slot]

            def on_unit(_listing_count: int, record: PurchasedRecord = record) -> None:
                nonlocal purchased_quantity
                # buy_from_listing reports verified listing clicks. Every
                # Dọn-quầy listing is one batch of exactly ten VP.
                record.record_purchase(LISTING_QUANTITY)
                purchased_quantity += LISTING_QUANTITY
                self._persist_state()
                self._checkpoint(
                    f"PURCHASED_{purchased_quantity}_OF_{self.request.buy_quantity}",
                    save_state=False,
                )

            try:
                self.automation.buying.buy_from_listing(
                    observation,
                    maximum=remaining_listings,
                    on_unit=on_unit,
                )
            except InventoryFull:
                inventory_full = True
                self.context.log(
                    f"Kho clone đã đạt giới hạn sau {purchased_quantity} VP; "
                    "chuyển sang treo bán"
                )
                break

        self._checkpoint("PURCHASE_COMPLETE")
        self.context.log(
            f"Kết thúc mua: {purchased_quantity}/{self.request.buy_quantity} VP trong phiên"
        )
        return purchased_quantity, inventory_full

    def _resell(self) -> tuple[int, bool]:
        batches = self.manifest.resale_batches()
        if not batches:
            remainder = self.manifest.remaining_total
            self.context.log(
                f"Không có loại VP nào đủ 10; giữ {remainder} VP trong kho và hoàn thành"
            )
            self._checkpoint("RESALE_SKIPPED_NO_FULL_BATCH")
            return 0, False

        self._checkpoint("OPENING_CLONE_STALL")
        self.automation.stall.open_own_stall()
        self._checkpoint("RESELLING")

        sold = 0
        deferred = False
        skipped_groups: set[str] = set()
        for index, batch in enumerate(batches, start=1):
            self.context.ensure_running()
            key = batch.fingerprint.group_key
            if key in skipped_groups:
                continue
            self._checkpoint(f"SELLING_BATCH_{index}_QTY_10", save_state=False)
            try:
                self.automation.selling.sell_batch_of_ten(
                    batch.fingerprint,
                    storage_id=self.request.resale_storage_id,
                )
            except InsufficientBatch:
                # User rule: if the end remainder for this VP is not enough ten,
                # skip it and complete the clone session normally.
                deferred = True
                skipped_groups.add(key)
                self.context.log(
                    "VP này không còn đủ 10 theo xác nhận của game; "
                    "giữ lại và bỏ qua trong phiên hiện tại"
                )
                continue
            except NoEmptyStallSlot:
                deferred = True
                self.context.log(
                    "Quầy clone không còn ô trống; giữ lại các VP chưa treo cho phiên sau"
                )
                break

            self.manifest.record_group_sale(batch.fingerprint, batch.quantity)
            sold += batch.quantity
            self._persist_state()
            self._checkpoint(f"SOLD_TOTAL_{sold}", save_state=False)

        remaining = self.manifest.remaining_total
        if remaining:
            self.context.log(f"Còn {remaining} VP trong kho sau giai đoạn treo bán")
        self._checkpoint("RESALE_COMPLETE")
        return sold, deferred

    def _checkpoint(self, state: str, *, save_state: bool = True) -> None:
        self.manifest.state = str(state)
        self._save_manifest()
        if save_state and not self.request.probe_only:
            self.carryover.save(self.manifest)
        self.context.stage(str(state))

    def _persist_state(self) -> None:
        self._save_manifest()
        if not self.request.probe_only:
            self.carryover.save(self.manifest)

    def _save_manifest(self) -> None:
        self.manifest.save(self.manifest_path)

    def _result(
        self,
        *,
        discovered_slots: int,
        bought: int,
        sold: int,
        retained: int,
        deferred: bool,
        inventory_full: bool,
        source_empty: bool,
        state: str,
        planned_listings: int = 0,
        planned_quantity: int = 0,
        target_reached: bool = False,
    ) -> ClearStallResult:
        result = ClearStallResult(
            profile_id=self.request.profile_id,
            friend_ordinal=self.request.friend_ordinal,
            resale_storage_id=self.request.resale_storage_id,
            discovered_slots=int(discovered_slots),
            bought=int(bought),
            sold=int(sold),
            retained=int(retained),
            deferred=bool(deferred),
            inventory_full=bool(inventory_full),
            source_empty=bool(source_empty),
            probe_only=self.request.probe_only,
            state=str(state),
            planned_listings=int(planned_listings),
            planned_quantity=int(planned_quantity),
            target_reached=bool(target_reached),
        )
        if self.result_reporter is not None:
            self.result_reporter(result.to_dict())
        return result
