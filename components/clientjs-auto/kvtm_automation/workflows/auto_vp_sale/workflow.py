from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...actions.auto_main_selling import AutoMainSellingActions
from ...actions.stall_advertising import StallAdvertisingActions
from ...automation import KVAutomation
from ...errors import AutomationStopped, ScreenTimeout


__all__ = ["AutoVpSaleResult", "AutoVpSaleWorkflow"]
FILE_FUNCTIONS = (
    "Đưa clone về farm, chứng minh exact-main bằng runtime boundary rồi mở quầy bán",
    "Mở quầy bằng entry point chuẩn sau exact-main proof; không dùng quay_hang background làm runtime gate",
    "Mỗi lượt bán kiểm tra QC ba mốc đầu/giữa/cuối quầy trước thao tác bán tại mốc đó",
    "Không click ô đã có QC; nếu QC miễn phí hồi thì bật, còn cooldown thì đóng X",
    "Theo từng view: thu vàng nếu có",
    "Treo lần lượt đúng VP do Function hiện tại cho phép vào mọi ô trống",
    "Nếu Kho thành phẩm không còn VP hợp lệ thì đóng kho, kết thúc sale pass ngay và trả scheduler chạy Function",
    "Chỉ kéo sang view kế tiếp khi sale pass vẫn còn việc cần quét",
    "Đóng quầy và tổng hợp số VP đã treo",
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
    """Callable sale module: advertise, collect, sell exact x10, swipe, repeat.

    The old consolidated AUTO call remains source-compatible: without explicit
    arguments this is Function 1 and sells only Táo sấy/Vải vàng. AUTO Builder
    supplies the Function catalog item ids so sale policy is owned by the
    Function metadata rather than by Scheduler ordering.

    Advertisement is opportunistic and non-blocking. If finished-goods inventory
    is genuinely depleted, sale returns immediately to AUTO Main instead of
    walking the remaining stall views and reopening UI that has no sellable VP.
    """

    VIEW_COUNT = 4
    MAX_SALES_PER_VIEW = 8
    EXACT_MAIN_NAV_ATTEMPTS = 8
    OWN_STALL_OPEN_ATTEMPTS = 6

    AD_CHECKPOINTS = {
        1: ("đầu", 1),
        2: ("giữa", 10),
        4: ("cuối", 20),
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
        self.function_id = str(function_id or "function_1")
        self.sale = AutoMainSellingActions(
            automation.selling,
            automation.auto_vp,
            item_order=allowed_item_ids,
        )
        self.advertising = StallAdvertisingActions(
            automation.context,
            automation.vision,
            automation.wait,
            automation.stall,
        )

    def _normalize_exact_main_for_sale(self) -> None:
        """Prove the lower farm boundary without depending on account artwork."""
        if self.auto.popup.is_own_exact_main_screen():
            return

        for attempt in range(1, self.EXACT_MAIN_NAV_ATTEMPTS + 1):
            self.context.ensure_running()
            change = self.auto.function_one_pass_three_navigation.go_down_one_toward_main(
                f"auto-vp-sale-exact-main-{attempt}-of-{self.EXACT_MAIN_NAV_ATTEMPTS}"
            )
            self.context.detail(
                "AUTO bán VP exact-main | "
                f"attempt={attempt}/{self.EXACT_MAIN_NAV_ATTEMPTS} | "
                f"frame_change={float(change):.2f}"
            )
            if self.auto.popup.is_own_exact_main_screen():
                self.context.log(
                    "AUTO bán VP • exact-main runtime proof READY trước mở quầy"
                )
                return

        raise ScreenTimeout(
            "AUTO bán VP không chứng minh được exact-main sau "
            f"{self.EXACT_MAIN_NAV_ATTEMPTS} nhịp goDown"
        )

    def _open_own_stall_from_exact_main(self) -> None:
        """Open own stall from a proven main boundary and verify the active panel."""
        stall = self.auto.stall
        zone = stall.OWN_STALL_ACTIVE_ZONE
        if self.auto.vision.find(
            "quay_hang_on", threshold=0.80, zone=zone
        ) is not None:
            return

        if not self.auto.popup.is_own_exact_main_screen():
            raise ScreenTimeout(
                "AUTO bán VP từ chối mở quầy khi chưa có exact-main runtime proof"
            )

        for attempt in range(1, self.OWN_STALL_OPEN_ATTEMPTS + 1):
            self.context.ensure_running()
            self.auto.vision.driver.click(*stall.OWN_STALL_ENTRY_POINT)
            self.auto.wait.sleep(0.45)
            if self.auto.vision.find(
                "quay_hang_on", threshold=0.80, zone=zone
            ) is not None:
                self.context.log(
                    "Đã vào quầy bán của clone • exact-main proof + quay_hang_on PASS"
                )
                return
            self.context.detail(
                "AUTO bán VP mở quầy | "
                f"attempt={attempt}/{self.OWN_STALL_OPEN_ATTEMPTS} | "
                "entry=logical-fixed | background_gate=disabled"
            )

        raise ScreenTimeout(
            "Không vào được quầy bán của clone sau exact-main proof; "
            "không dùng quay_hang background để click mù"
        )

    def _check_advertisement_checkpoint(self, view: int) -> None:
        spec = self.AD_CHECKPOINTS.get(int(view))
        if spec is None:
            return
        checkpoint, target_physical = spec
        self.context.stage(
            f"auto-vp-sale-advert-{checkpoint}-view-{int(view)}"
        )
        try:
            result = self.advertising.check_checkpoint(
                view=int(view),
                checkpoint=checkpoint,
                target_physical_slot=int(target_physical),
            )
            self.context.detail(
                "AUTO quảng cáo checkpoint | "
                f"checkpoint={checkpoint} | view={view} | "
                f"target_physical={target_physical} | status={result.status} | "
                f"physical_slot={result.physical_slot}"
            )
        except AutomationStopped:
            raise
        except Exception as exc:
            self.context.log(
                "AUTO quảng cáo • "
                f"mốc {checkpoint} lỗi non-blocking: {type(exc).__name__}: {exc} • "
                "bỏ qua QC và tiếp tục bán"
            )

    def run(self, timeout: float = 120.0) -> AutoVpSaleResult:
        started = time.monotonic()
        self.context.stage(f"auto-vp-sale-{self.function_id}-start")
        self.auto.ensure_main_screen(timeout=timeout)
        self._normalize_exact_main_for_sale()
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
                self.context.stage(f"auto-vp-sale-view-{view}")

                self._check_advertisement_checkpoint(view)

                self.context.log(
                    f"AUTO bán VP • {self.function_id} • view {view}/{self.VIEW_COUNT} • "
                    "QC nếu tới mốc → thu vàng → treo VP nếu còn hàng"
                )
                collected += self.auto.stall.collect_own_stall_gold(maximum=8)

                for _slot in range(self.MAX_SALES_PER_VIEW):
                    attempt = self.sale.sell_next_allowed(storage_id=2)
                    if attempt.status == "SOLD":
                        sold += 1
                        sold_by_item[attempt.item_id] += 1
                        self.context.log(
                            f"AUTO bán VP • đã treo {attempt.label} x10 • "
                            f"tổng {sold} ô"
                        )
                        continue
                    if attempt.status in (
                        "NO_ALLOWED_ITEM",
                        "NO_EXACT_TEN_ITEMS",
                        "NO_SAFE_EXACT_TEN_ITEMS",
                    ):
                        depleted = True
                        self.context.stage(
                            "auto-vp-sale-inventory-depleted-return-scheduler"
                        )
                        self.context.log(
                            f"AUTO bán VP • {self.function_id} không còn VP hợp lệ/x10 • "
                            "Kho thành phẩm đã đóng • KẾT THÚC SALE PASS NGAY → "
                            "trả scheduler chạy Function"
                        )
                    else:
                        self.context.log(
                            f"AUTO bán VP • view {view} không còn ô trống"
                        )
                    break

                if depleted:
                    break

                if view < self.VIEW_COUNT:
                    self.context.stage("auto-vp-sale-two-swipes")
                    self.auto.stall.next_view()
        finally:
            self.auto.stall.close_own_stall()

        self.context.ensure_running()
        summary = " | ".join(
            f"{item_id}={sold_by_item[item_id]}" for item_id in self.sale.ITEM_ORDER
        )
        self.context.log(
            "AUTO bán VP • tổng kết x10 | " + summary
        )
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
