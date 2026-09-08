from __future__ import annotations

from ..context import AutomationContext
from ..errors import ScreenTimeout
from ..runtime.auto_speed_config import AutoSpeedConfig
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter
from .production import ProductionActions, ProductionResult


__all__ = ["AppleJuiceProductionActions"]
FILE_FUNCTIONS = (
    "Mở máy tầng 2 và xác minh đúng ảnh sản xuất Nước táo",
    "Dùng bộ đếm chín ô trống đã live-pass của máy sấy",
    "Kéo Nước táo xuống ô top động đúng chín lần",
    "Hậu kiểm mỗi lần kéo làm giảm đúng bộ đếm ô trống",
)


class AppleJuiceProductionActions:
    """Queue exactly nine apple juices on the verified floor-2 panel."""

    MACHINE_POINT = (262, 917)
    PRODUCT_TEMPLATE = "nuoc_tao"
    CLOSE_POINT = (965, 198)
    REQUIRED_COUNT = 9

    def __init__(self, context: AutomationContext, vision: VisionEngine,
                 waiter: Waiter, speed_config: AutoSpeedConfig | None = None) -> None:
        self.context = context
        self.vision = vision
        self.waiter = waiter
        self.speed_config = speed_config or AutoSpeedConfig()
        self.slots = ProductionActions(context, vision, waiter, self.speed_config)

    def _open_verified(self):
        click_count = 0
        while True:
            self.context.ensure_running()
            click_count += 1
            self.vision.driver.click(*self.MACHINE_POINT)
            self.waiter.sleep(0.30)
            warehouse_full, panel_ready = self.slots._panel_state()
            if click_count == 1 or click_count % 5 == 0 or panel_ready:
                self.context.log(
                    "AUTO Nước táo • click thu VP/mở máy tầng 2 "
                    f"• clicks={click_count} • panel={panel_ready}"
                )
            if warehouse_full:
                self.vision.driver.click(*self.CLOSE_POINT)
                raise ScreenTimeout(
                    "Đã thu VP trước máy Nước táo nhưng kho đang đầy"
                )
            if panel_ready:
                break

        product = None
        for attempt in range(1, 4):
            product = self.vision.find(
                self.PRODUCT_TEMPLATE, threshold=0.70, zone=None,
                scales=(0.75, 0.90, 1.00, 1.10, 1.25), click=False,
            )
            if product is not None:
                break
            self.waiter.sleep(0.20)
        top = self.slots._find_top_empty_slot()
        if product is None or top is None:
            self.vision.driver.click(*self.CLOSE_POINT)
            raise ScreenTimeout(
                "Panel tầng 2 đã mở nhưng chưa xác minh được nuoc_tao hoặc ô top"
            )
        empty = self.slots._count_empty_slots()
        if empty != self.REQUIRED_COUNT:
            self.vision.driver.click(*self.CLOSE_POINT)
            raise ScreenTimeout(
                f"Máy Nước táo có {empty}/9 ô trống; yêu cầu đúng 9"
            )
        self.context.log(
            "AUTO Nước táo • panel đã mở, dừng click • "
            f"clicks={click_count} • score={product.score:.3f} • "
            f"đường kéo={product.center} → {top.center}"
        )
        return empty, product.center, top.center

    def produce_9_apple_juices(
        self, *, close_after_success: bool = True
    ) -> ProductionResult:
        empty_before, product_point, top_point = self._open_verified()
        empty_after = empty_before
        for ordinal in range(1, self.REQUIRED_COUNT + 1):
            self.context.ensure_running()
            self.vision.driver.swipe_points((product_point, top_point), duration=0.02)
            self.waiter.sleep(self.speed_config.vp_production_delay)
            current = self.slots._count_empty_slots()
            if current >= empty_after:
                self.vision.driver.click(*self.CLOSE_POINT)
                raise ScreenTimeout(
                    f"Kéo Nước táo {ordinal}/9 không làm giảm ô trống: "
                    f"trước={empty_after}, sau={current}"
                )
            empty_after = current
            self.context.log(
                f"AUTO Nước táo • đã xác minh xếp {ordinal}/9 • ô trống còn={current}"
            )
        if empty_before - empty_after != self.REQUIRED_COUNT:
            self.vision.driver.click(*self.CLOSE_POINT)
            raise ScreenTimeout("Hậu kiểm Nước táo không đạt đúng 9/9 ô")
        if close_after_success:
            self.vision.driver.click(*self.CLOSE_POINT)
        else:
            self.context.log(
                "AUTO Nước táo • giữ panel mở để bàn giao sang Sửa máy"
            )
        self.context.log("AUTO sản xuất Nước táo hoàn tất • đã xác minh đủ 9/9 ô")
        return ProductionResult(
            item_id=self.PRODUCT_TEMPLATE, requested_count=9, queued_count=9,
            empty_before=empty_before, empty_after=empty_after,
        )
