from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...actions.auto_main_selling import AutoMainSellingActions
from ...automation import KVAutomation


__all__ = ["AutoVpSaleResult", "AutoVpSaleWorkflow"]
FILE_FUNCTIONS = (
    "Đưa clone về màn hình chính và mở quầy bán",
    "Theo từng view: thu vàng nếu có",
    "Treo lần lượt đúng VP do Function hiện tại cho phép vào mọi ô trống",
    "Kéo đúng hai swipe sang view kế tiếp",
    "Dừng an toàn khi kho hết VP được cho phép",
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
    """Callable sale module: collect, sell exact x10, two swipes, repeat.

    The old consolidated AUTO call remains source-compatible: without explicit
    arguments this is Function 1 and sells only Táo sấy/Vải vàng. AUTO Builder
    supplies the Function catalog item ids so sale policy is owned by the
    Function metadata rather than by Scheduler ordering.
    """

    VIEW_COUNT = 4
    MAX_SALES_PER_VIEW = 8

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

    def run(self, timeout: float = 120.0) -> AutoVpSaleResult:
        started = time.monotonic()
        self.context.stage(f"auto-vp-sale-{self.function_id}-start")
        self.auto.ensure_main_screen(timeout=timeout)
        self.auto.stall.open_own_stall()

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
                self.context.log(
                    f"AUTO bán VP • {self.function_id} • view {view}/{self.VIEW_COUNT} • "
                    "thu vàng rồi treo VP"
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
                        self.context.log(
                            f"AUTO bán VP • {self.function_id} không còn lựa chọn "
                            "đúng loại và đủ x10; dừng treo"
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
