from __future__ import annotations

from dataclasses import dataclass

from ..errors import ScreenTimeout
from .production_panel import ProductionPanelActions


__all__ = ["ProductionResult", "ProductionActions"]
FILE_FUNCTIONS = (
    "Táo sấy product transaction trên shared ProductionPanelActions",
    "Thu VP/mở panel/đếm slot/sai máy/kho đầy được delegate shared panel engine",
    "Kéo đúng chín Táo sấy và hậu kiểm mỗi queue event",
    "Giữ retry gesture hiện hữu 3 lần x 4 frame verify",
    "Không sở hữu logic sản phẩm Nước táo/Vải vàng/TDHH",
)


@dataclass(frozen=True)
class ProductionResult:
    item_id: str
    requested_count: int
    queued_count: int
    empty_before: int
    empty_after: int


class ProductionActions(ProductionPanelActions):
    """Dried-apple product transaction over the shared production panel engine."""

    DRYER_FLOOR = 1
    DRYER_POINT = (262, 917)
    DRIED_APPLE_PRODUCTION_TEMPLATE = "tao_say"
    DRIED_APPLE_GUARD_THRESHOLD = 0.70
    MATERIAL_ERROR_TEMPLATE = "x"
    MATERIAL_ERROR_ZONE = (682, 337, 142, 120)
    REQUIRED_COUNT = 9
    DRAG_ATTEMPTS = 3
    VERIFY_RECHECKS = 4
    VERIFY_RECHECK_SECONDS = 0.18

    def _collect_finished_before_open(self) -> None:
        click_count = self._click_until_panel_open(
            machine_point=self.DRYER_POINT,
            product_template=self.DRIED_APPLE_PRODUCTION_TEMPLATE,
            label="Táo sấy",
            product_threshold=self.DRIED_APPLE_GUARD_THRESHOLD,
        )
        self.context.log(
            "AUTO sản xuất • đã mở đúng panel tầng 1 bằng burst thu VP "
            f"• tổng click={click_count} • nếu còn ô đang chạy sẽ giữ panel để chờ"
        )

    def _open_verified_dryer(self) -> tuple[int, tuple[int, int], tuple[int, int]]:
        self._collect_finished_before_open()
        empty, product_point, top_point = self._wait_for_idle_open_panel(
            product_template=self.DRIED_APPLE_PRODUCTION_TEMPLATE,
            label="Táo sấy",
            product_threshold=self.DRIED_APPLE_GUARD_THRESHOLD,
        )
        self.context.log(
            f"AUTO sản xuất • đúng máy sấy tầng 1 • có {empty} ô trống"
        )
        self.context.log(
            "AUTO sản xuất • đường kéo đã xác minh "
            f"• tao_say={product_point} → top={top_point}"
        )
        return empty, product_point, top_point

    def _drag_dried_apple_with_retry(
        self,
        *,
        ordinal: int,
        product_point: tuple[int, int],
        top_point: tuple[int, int],
        empty_before: int,
    ) -> int:
        last_empty = int(empty_before)
        for drag_attempt in range(1, self.DRAG_ATTEMPTS + 1):
            self.context.ensure_running()
            self.vision.driver.swipe_points(
                (product_point, top_point),
                duration=0.02,
            )
            self.waiter.sleep(self.speed_config.vp_production_delay)

            for verify_round in range(1, self.VERIFY_RECHECKS + 1):
                self.context.ensure_running()
                missing = self.vision.find(
                    self.MATERIAL_ERROR_TEMPLATE,
                    threshold=0.80,
                    zone=self.MATERIAL_ERROR_ZONE,
                    scales=(0.90, 1.00, 1.10),
                    click=False,
                )
                if missing is not None:
                    self.vision.driver.click(*missing.center)
                    self.vision.driver.click(*self.CLOSE_POINT)
                    raise ScreenTimeout(
                        f"Thiếu nguyên liệu khi xếp Táo sấy {ordinal}/9"
                    )

                current_empty = self._count_empty_slots()
                last_empty = current_empty
                if current_empty < empty_before:
                    if drag_attempt > 1 or verify_round > 1:
                        self.context.log(
                            f"AUTO Táo sấy • xếp {ordinal}/9 đã phục hồi sau recheck/retry "
                            f"• drag={drag_attempt}/{self.DRAG_ATTEMPTS} • "
                            f"verify={verify_round}/{self.VERIFY_RECHECKS} • "
                            f"ô trống {empty_before}→{current_empty}"
                        )
                    return current_empty
                if verify_round < self.VERIFY_RECHECKS:
                    self.waiter.sleep(self.VERIFY_RECHECK_SECONDS)

            if drag_attempt < self.DRAG_ATTEMPTS:
                self.context.log(
                    f"AUTO Táo sấy • xếp {ordinal}/9 chưa thấy ô trống giảm sau "
                    f"{self.VERIFY_RECHECKS} frame • thử lại gesture "
                    f"{drag_attempt + 1}/{self.DRAG_ATTEMPTS}"
                )
        return last_empty

    def produce_9_dried_apples(
        self,
        *,
        close_after_success: bool = True,
    ) -> ProductionResult:
        empty_before, product_point, top_point = self._open_verified_dryer()
        empty_after = empty_before
        queued = 0
        for ordinal in range(1, self.REQUIRED_COUNT + 1):
            self.context.ensure_running()
            current_empty = self._drag_dried_apple_with_retry(
                ordinal=ordinal,
                product_point=product_point,
                top_point=top_point,
                empty_before=empty_after,
            )
            if current_empty >= empty_after:
                self.vision.driver.click(*self.CLOSE_POINT)
                raise ScreenTimeout(
                    "Kéo Táo sấy không làm giảm ô trống sau retry: "
                    f"lần={ordinal}/9, trước={empty_after}, sau={current_empty}, "
                    f"drag_attempts={self.DRAG_ATTEMPTS}, "
                    f"verify_rechecks={self.VERIFY_RECHECKS}, "
                    f"từ={product_point}, đến_top={top_point}"
                )
            empty_after = current_empty
            queued += 1
            self.context.log(
                f"AUTO sản xuất • đã xác minh xếp Táo sấy {ordinal}/9 "
                f"• ô trống còn={empty_after}"
            )

        consumed = max(0, empty_before - empty_after)
        if consumed != self.REQUIRED_COUNT:
            self.vision.driver.click(*self.CLOSE_POINT)
            raise ScreenTimeout(
                "Hậu kiểm máy sấy không đúng 9 ô thay đổi: "
                f"trước={empty_before}, sau={empty_after}, xác minh={consumed}/9"
            )
        if close_after_success:
            self.vision.driver.click(*self.CLOSE_POINT)
        else:
            self.context.log(
                "AUTO sản xuất Táo sấy • giữ panel mở để bàn giao sang Sửa máy"
            )
        self.context.log(
            "AUTO sản xuất Táo sấy hoàn tất • đã xác minh đủ 9/9 ô"
        )
        return ProductionResult(
            item_id=self.DRIED_APPLE_PRODUCTION_TEMPLATE,
            requested_count=self.REQUIRED_COUNT,
            queued_count=queued,
            empty_before=empty_before,
            empty_after=empty_after,
        )
