from __future__ import annotations

from ..context import AutomationContext
from ..errors import ScreenTimeout
from ..runtime.auto_speed_config import AutoSpeedConfig
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter
from .production import ProductionActions, ProductionResult


__all__ = ["YellowFabricProductionActions"]
FILE_FUNCTIONS = (
    "Mở máy tầng 3 và xác minh đúng ảnh sản xuất Vải vàng",
    "Thu VP/mở panel theo tốc độ thu VP cấu hình riêng",
    "Dùng bộ đếm chín ô trống đã live-pass của hai pass trước",
    "Kéo Vải vàng xuống ô top động đúng chín lần",
    "Hậu kiểm mỗi lần kéo làm giảm đúng bộ đếm ô trống",
)


class YellowFabricProductionActions:
    """Queue exactly nine yellow fabrics on the verified floor-3 panel."""

    MACHINE_POINT = (262, 917)
    PRODUCT_TEMPLATE = "vai_vang"
    CLOSE_POINT = (965, 198)
    MATERIAL_ERROR_TEMPLATE = "x"
    MATERIAL_ERROR_ZONE = (682, 337, 142, 120)
    REQUIRED_COUNT = 9
    MAX_OPEN_CLICKS = 30

    def __init__(
        self,
        context: AutomationContext,
        vision: VisionEngine,
        waiter: Waiter,
        speed_config: AutoSpeedConfig | None = None,
    ) -> None:
        self.context = context
        self.vision = vision
        self.waiter = waiter
        self.speed_config = speed_config or AutoSpeedConfig()
        self.slots = ProductionActions(context, vision, waiter, self.speed_config)

    def _close_panel(self) -> None:
        self.vision.driver.click(*self.CLOSE_POINT)

    def _open_verified(self) -> tuple[int, tuple[int, int], tuple[int, int]]:
        click_count = 0
        panel_ready = False
        for click_count in range(1, self.MAX_OPEN_CLICKS + 1):
            self.context.ensure_running()
            self.vision.driver.click(*self.MACHINE_POINT)
            self.waiter.sleep(self.speed_config.vp_collect_delay)
            warehouse_full, panel_ready = self.slots._panel_state()
            if click_count == 1 or click_count % 5 == 0 or panel_ready:
                self.context.log(
                    "AUTO Vải vàng • click thu VP/mở máy tầng 3 "
                    f"• clicks={click_count} • panel={panel_ready} • "
                    f"fullkho={warehouse_full} • "
                    f"delay={self.speed_config.vp_collect_delay:.3f}s"
                )
            if warehouse_full:
                self._close_panel()
                raise ScreenTimeout(
                    "Đã thu VP trước máy Vải vàng nhưng kho đang đầy"
                )
            if panel_ready:
                break

        if not panel_ready:
            self._close_panel()
            raise ScreenTimeout(
                "Không mở/xác minh được panel Vải vàng sau "
                f"{self.MAX_OPEN_CLICKS} lần click; dừng fail-close"
            )

        product = None
        for attempt in range(1, 4):
            self.context.ensure_running()
            product = self.vision.find(
                self.PRODUCT_TEMPLATE,
                threshold=0.70,
                zone=None,
                scales=(0.75, 0.90, 1.00, 1.10, 1.25),
                click=False,
            )
            if product is not None:
                break
            self.context.log(
                "AUTO Vải vàng • panel đã mở nhưng chưa khớp vai_vang "
                f"• lần {attempt}/3"
            )
            self.waiter.sleep(0.20)

        top = self.slots._find_top_empty_slot()
        if product is None or top is None:
            self._close_panel()
            raise ScreenTimeout(
                "Panel tầng 3 đã mở nhưng chưa xác minh được vai_vang hoặc ô top"
            )

        empty = self.slots._count_empty_slots()
        if empty != self.REQUIRED_COUNT:
            self._close_panel()
            raise ScreenTimeout(
                f"Máy Vải vàng có {empty}/9 ô trống; yêu cầu đúng 9"
            )

        self.context.log(
            "AUTO Vải vàng • panel đã mở, dừng click • "
            f"clicks={click_count} • score={product.score:.3f} • "
            f"đường kéo={product.center} → {top.center}"
        )
        return empty, product.center, top.center

    def produce_9_yellow_fabrics(
        self, *, close_after_success: bool = True
    ) -> ProductionResult:
        empty_before, product_point, top_point = self._open_verified()
        empty_after = empty_before

        for ordinal in range(1, self.REQUIRED_COUNT + 1):
            self.context.ensure_running()
            self.vision.driver.swipe_points(
                (product_point, top_point), duration=0.02
            )
            self.waiter.sleep(self.speed_config.vp_production_delay)

            missing = self.vision.find(
                self.MATERIAL_ERROR_TEMPLATE,
                threshold=0.80,
                zone=self.MATERIAL_ERROR_ZONE,
                scales=(0.90, 1.00, 1.10),
                click=False,
            )
            if missing is not None:
                self.vision.driver.click(*missing.center)
                self._close_panel()
                raise ScreenTimeout(
                    f"Thiếu nguyên liệu khi xếp Vải vàng {ordinal}/9"
                )

            current = self.slots._count_empty_slots()
            if current >= empty_after:
                self._close_panel()
                raise ScreenTimeout(
                    f"Kéo Vải vàng {ordinal}/9 không làm giảm ô trống: "
                    f"trước={empty_after}, sau={current}"
                )
            empty_after = current
            self.context.log(
                f"AUTO Vải vàng • đã xác minh xếp {ordinal}/9 • ô trống còn={current}"
            )

        if empty_before - empty_after != self.REQUIRED_COUNT:
            self._close_panel()
            raise ScreenTimeout("Hậu kiểm Vải vàng không đạt đúng 9/9 ô")
        if close_after_success:
            self._close_panel()
        else:
            self.context.log(
                "AUTO Vải vàng • giữ panel mở để bàn giao sang Sửa máy"
            )

        self.context.log("AUTO sản xuất Vải vàng hoàn tất • đã xác minh đủ 9/9 ô")
        return ProductionResult(
            item_id=self.PRODUCT_TEMPLATE,
            requested_count=self.REQUIRED_COUNT,
            queued_count=self.REQUIRED_COUNT,
            empty_before=empty_before,
            empty_after=empty_after,
        )
