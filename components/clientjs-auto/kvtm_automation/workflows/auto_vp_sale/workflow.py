from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...actions.stall_advertising import StallAdvertisingActions
from ...actions.vp_sale_transaction import VpSaleTransactionActions
from ...automation import KVAutomation
from ...errors import AutomationStopped, ScreenTimeout
from ..auto_builder.catalog import get_function_spec


__all__ = ["AutoVpSaleResult", "AutoVpSaleWorkflow"]
FILE_FUNCTIONS = (
    "Yêu cầu caller bàn giao camera exact-main; sale không tự goDown để sửa trạng thái",
    "Mở quầy và bắt đầu tại 8 ô mặc định của View 1",
    "Mỗi View chạy thu vàng nếu có → QC nếu có → tìm ô trống → Kho 2 → VP Function → đủ x10 mới đăng",
    "Không đủ 10 thì thử VP hợp lệ tiếp theo; hết VP hợp lệ thì đóng sale và trả caller",
    "Nếu View hết ô trống thì chuyển View bằng Action stall.next_view() = đúng hai swipe",
    "Quét đủ 5 View; View 5 là final boundary/overlap check để bắt các ô cuối",
    "View 5 không coi việc camera ít/không dịch ở biên phải là lỗi",
    "Dùng VpSaleTransactionActions cho từng listing; không phụ thuộc tên AUTO Main",
    "Đóng Kho/quầy theo owner Action và trả kết quả cho caller, không giả định caller là Scheduler",
)


@dataclass(frozen=True)
class AutoVpSaleResult:
    profile_id: str
    sold_listings: int
    collected_gold_slots: int
    views_scanned: int
    inventory_depleted: bool
    sold_by_item: dict[str, int]
    elapsed_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


class AutoVpSaleWorkflow:
    """Reusable VP sale Module for every Function.

    Sale policy comes from Function metadata (allowed item ids), while all UI
    interaction stays inside Actions/this Module. The Module never decides that a
    Function completed and never performs a hidden farm-camera recovery.
    """

    VIEW_COUNT = 5
    MAX_SALES_PER_VIEW = 8
    OWN_STALL_OPEN_ATTEMPTS = 6

    AD_CHECKPOINTS = {
        1: ("view-1", 1, 1),
        2: ("view-2", 5, 2),
        3: ("view-3", 9, 3),
        4: ("view-4", 13, 4),
        5: ("final-boundary", 20, 4),
    }

    INVENTORY_DEPLETED_STATUSES = {
        "NO_ALLOWED_ITEM",
        "NO_EXACT_TEN_ITEMS",
        "NO_SAFE_EXACT_TEN_ITEMS",
    }

    def __init__(
        self,
        automation: KVAutomation,
        *,
        function_id: str = "function_1",
        allowed_item_ids: tuple[str, ...] | None = None,
    ) -> None:
        self.auto = automation
        self.context = automation.context
        self.function_spec = get_function_spec(function_id)
        self.function_id = self.function_spec.function_id
        requested_order = tuple(
            allowed_item_ids or self.function_spec.sale_item_ids
        )
        self.sale = VpSaleTransactionActions(
            automation.selling,
            automation.auto_vp,
            item_order=requested_order,
        )
        self.advertising = StallAdvertisingActions(
            automation.context,
            automation.vision,
            automation.wait,
            automation.stall,
        )

    def _require_function_resolution(self) -> None:
        if self.function_id != "function_2":
            return
        native = self.auto.selling.native_size()
        if native != (1000, 1000):
            raise ScreenTimeout(
                "AUTO bán VP Function 2 hiện chỉ cho native ClientJS 1000x1000; "
                f"capture={native[0]}x{native[1]}. Không thao tác quầy ở 500x500."
            )
        self.context.detail(
            "AUTO Function 2 sale | native=1000x1000 | resolution_gate=PASS"
        )

    def _require_sale_entry_main(self, *, timeout: float) -> None:
        self.context.ensure_running()
        if not self.auto.popup.is_own_main_screen():
            self.auto.ensure_main_screen(timeout=float(timeout))

        if not self.auto.popup.is_own_exact_main_screen():
            raise ScreenTimeout(
                "AUTO bán VP cần exact-main từ Startup/Function boundary; "
                "Sale không tự goDown(1) để sửa camera"
            )
        self.context.log(
            "AUTO bán VP • entry exact-main READY • không gửi navigation ẩn"
        )

    def _open_own_stall_from_exact_main(self) -> None:
        stall = self.auto.stall
        zone = stall.OWN_STALL_ACTIVE_ZONE
        if self.auto.vision.find(
            "quay_hang_on", threshold=0.80, zone=zone
        ) is not None:
            return

        if not self.auto.popup.is_own_exact_main_screen():
            raise ScreenTimeout(
                "AUTO bán VP từ chối mở quầy khi chưa có exact-main"
            )

        for attempt in range(1, self.OWN_STALL_OPEN_ATTEMPTS + 1):
            self.context.ensure_running()
            self.auto.vision.driver.click(*stall.OWN_STALL_ENTRY_POINT)
            self.auto.wait.sleep(0.45)
            if self.auto.vision.find(
                "quay_hang_on", threshold=0.80, zone=zone
            ) is not None:
                self.context.log(
                    "AUTO bán VP • mở quầy PASS • quay_hang_on verified"
                )
                return
            self.context.detail(
                "AUTO bán VP mở quầy | "
                f"attempt={attempt}/{self.OWN_STALL_OPEN_ATTEMPTS} | "
                "entry=logical-fixed"
            )

        raise ScreenTimeout(
            "Không vào được quầy bán từ exact-main; không click mù"
        )

    def _check_advertisement_checkpoint(self, view: int) -> None:
        checkpoint, target_physical, geometry_view = self.AD_CHECKPOINTS[int(view)]
        self.context.stage(
            f"auto-vp-sale-advert-{checkpoint}-view-{int(view)}"
        )
        try:
            result = self.advertising.check_checkpoint(
                view=int(geometry_view),
                checkpoint=checkpoint,
                target_physical_slot=int(target_physical),
            )
            self.context.detail(
                "AUTO quảng cáo checkpoint | "
                f"checkpoint={checkpoint} | scan_view={view} | "
                f"geometry_view={geometry_view} | target_physical={target_physical} | "
                f"status={result.status} | physical_slot={result.physical_slot}"
            )
        except AutomationStopped:
            raise
        except Exception as exc:
            self.context.log(
                "AUTO quảng cáo • "
                f"{checkpoint} lỗi non-blocking: {type(exc).__name__}: {exc} • "
                "tiếp tục xử lý vàng/ô trống/VP"
            )

    def run(self, timeout: float = 120.0) -> AutoVpSaleResult:
        started = time.monotonic()
        self._require_function_resolution()
        self.context.stage(f"auto-vp-sale-{self.function_id}-start")
        self._require_sale_entry_main(timeout=timeout)
        self._open_own_stall_from_exact_main()

        sold = 0
        sold_by_item = {item_id: 0 for item_id in self.sale.ITEM_ORDER}
        collected = 0
        views_scanned = 0
        depleted = False
        try:
            for view in range(1, self.VIEW_COUNT + 1):
                self.context.ensure_running()
                views_scanned = view
                final_boundary = view == self.VIEW_COUNT
                self.context.stage(f"auto-vp-sale-view-{view}")
                self.context.log(
                    f"AUTO bán VP • {self.function_id} • view {view}/{self.VIEW_COUNT}"
                    + (" • FINAL BOUNDARY CHECK" if final_boundary else "")
                )

                collected += self.auto.stall.collect_own_stall_gold(maximum=8)
                self._check_advertisement_checkpoint(view)

                for _slot in range(self.MAX_SALES_PER_VIEW):
                    attempt = self.sale.sell_next_allowed(storage_id=2)
                    if attempt.status == "SOLD":
                        sold += 1
                        sold_by_item[attempt.item_id] += 1
                        self.context.log(
                            f"AUTO bán VP • đã treo {attempt.label} x10 • tổng={sold}"
                        )
                        continue

                    if attempt.status in self.INVENTORY_DEPLETED_STATUSES:
                        depleted = True
                        self.context.stage(
                            "auto-vp-sale-inventory-depleted-return-caller"
                        )
                        self.context.log(
                            f"AUTO bán VP • {self.function_id} không còn VP hợp lệ đủ x10 • "
                            "đóng sale và trả caller hiện tại"
                        )
                    else:
                        self.context.log(
                            f"AUTO bán VP • view {view} hiện không còn ô trống dùng được"
                        )
                    break

                if depleted:
                    break

                if view < self.VIEW_COUNT:
                    self.context.stage(
                        f"auto-vp-sale-next-view-{view}-to-{view + 1}-two-swipes"
                    )
                    self.auto.stall.next_view()
                    if view == self.VIEW_COUNT - 1:
                        self.context.log(
                            "AUTO bán VP • đã gửi 2 swipe vào View 5 final boundary • "
                            "không yêu cầu camera phải dịch thêm ở biên phải"
                        )
        finally:
            self.auto.stall.close_own_stall()

        self.context.ensure_running()
        summary = " | ".join(
            f"{item_id}={sold_by_item[item_id]}" for item_id in self.sale.ITEM_ORDER
        )
        self.context.log("AUTO bán VP • tổng kết x10 | " + summary)
        self.context.stage(f"auto-vp-sale-{self.function_id}-finished")
        return AutoVpSaleResult(
            profile_id=self.context.profile_id,
            sold_listings=sold,
            collected_gold_slots=collected,
            views_scanned=views_scanned,
            inventory_depleted=depleted,
            sold_by_item=sold_by_item,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )
