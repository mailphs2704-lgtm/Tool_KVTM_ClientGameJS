from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...actions.auto_main_selling import AutoMainSellingActions
from ...automation import KVAutomation


__all__ = ["AutoVpSaleResult", "AutoVpSaleWorkflow"]
FILE_FUNCTIONS = (
    "Đưa clone về màn hình chính và mở quầy bán",
    "Theo từng view: thu vàng nếu có",
    "Treo lần lượt đúng VP AUTO vào mọi ô trống",
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
    elapsed_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


class AutoVpSaleWorkflow:
    """Main AUTO sale flow: collect, sell, two swipes, then repeat."""

    VIEW_COUNT = 4
    MAX_SALES_PER_VIEW = 8

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context
        self.sale = AutoMainSellingActions(
            automation.selling,
            automation.auto_vp,
        )

    def run(self, timeout: float = 120.0) -> AutoVpSaleResult:
        started = time.monotonic()
        self.context.stage("auto-vp-sale-start")
        self.auto.ensure_main_screen(timeout=timeout)
        self.auto.stall.open_own_stall()

        sold = 0
        collected = 0
        views_scanned = 0
        depleted = False
        try:
            for view in range(1, self.VIEW_COUNT + 1):
                self.context.ensure_running()
                views_scanned = view
                self.context.stage(f"auto-vp-sale-view-{view}")
                self.context.log(
                    f"AUTO bán VP • view {view}/{self.VIEW_COUNT} • "
                    "thu vàng rồi treo VP"
                )
                collected += self.auto.stall.collect_own_stall_gold(maximum=8)

                for _slot in range(self.MAX_SALES_PER_VIEW):
                    attempt = self.sale.sell_next_allowed(storage_id=2)
                    if attempt.status == "SOLD":
                        sold += 1
                        self.context.log(
                            f"AUTO bán VP • đã treo {attempt.label} • "
                            f"tổng {sold} ô"
                        )
                        continue
                    if attempt.status == "NO_ALLOWED_ITEM":
                        depleted = True
                        self.context.log(
                            "AUTO bán VP • kho không còn VP đúng danh sách; "
                            "dừng treo"
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
        self.context.stage("auto-vp-sale-finished")
        return AutoVpSaleResult(
            profile_id=self.context.profile_id,
            sold_listings=sold,
            collected_gold_slots=collected,
            views_scanned=views_scanned,
            inventory_depleted=depleted,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )
