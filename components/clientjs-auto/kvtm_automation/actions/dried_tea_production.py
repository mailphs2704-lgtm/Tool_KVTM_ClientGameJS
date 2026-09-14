from __future__ import annotations

from ..errors import ScreenTimeout
from .production import ProductionResult
from .production_panel import ProductionPanelActions


__all__ = ["DriedTeaProductionActions"]
FILE_FUNCTIONS = (
    "Thu VP và mở máy Trà sấy tại tầng 1 bằng điểm máy dùng chung",
    "Tìm ảnh Trà sấy; nếu chưa thấy thì click đúng một lần nút trang phải rồi quét frame mới",
    "Lặp chuyển trang có stop-check cho tới khi tìm đúng Trà sấy",
    "Dùng ProductionPanelActions cho kho đầy, ô trống và hậu kiểm số lượng",
    "Kéo đúng chín Trà sấy và giữ panel mở để bàn giao Sửa máy",
)


class DriedTeaProductionActions(ProductionPanelActions):
    """Queue exactly nine dried teas from the paged floor-1 machine panel."""

    MACHINE_POINT = (262, 917)
    PRODUCT_TEMPLATE = "tra_say"
    PAGE_NEXT_POINT = (644, 638)
    MATERIAL_ERROR_TEMPLATE = "x"
    MATERIAL_ERROR_ZONE = (682, 337, 142, 120)
    REQUIRED_COUNT = 9
    DRAG_ATTEMPTS = 3
    VERIFY_RECHECKS = 4
    VERIFY_RECHECK_SECONDS = 0.18
    PAGE_SETTLE_SECONDS = 0.35

    def _close_panel(self) -> None:
        self.vision.driver.click(*self.CLOSE_POINT)

    def _open_and_find_product(self) -> tuple[int, tuple[int, int], tuple[int, int]]:
        """Open once, then turn exactly one page per miss until tra_say is found."""
        click_count = self._send_collect_burst(machine_point=self.MACHINE_POINT)
        self.context.log(
            "AUTO Trà sấy • thu VP/mở máy bằng burst x5 tại cùng tọa độ • "
            f"tổng click={click_count}"
        )
        self.waiter.sleep(self.speed_config.vp_collect_delay)

        page_turns = 0
        while True:
            self.context.ensure_running()
            frame = self.vision.frame()
            warehouse_full, empty_ready = self._panel_state(frame=frame)
            if warehouse_full:
                self._raise_inventory_full("Trà sấy")

            product = self._find_product_match(
                self.PRODUCT_TEMPLATE,
                threshold=0.70,
                frame=frame,
            )
            if product is not None:
                self.context.log(
                    "AUTO Trà sấy • tìm thấy template sau chuyển trang • "
                    f"page_turns={page_turns} • center={product.center} • "
                    f"score={product.score:.3f}"
                )
                break

            self.context.log(
                "AUTO Trà sấy • chưa thấy template • click mũi tên phải đúng 1 lần "
                f"tại {self.PAGE_NEXT_POINT} • page_turn={page_turns + 1} • "
                f"empty_anchor={'có' if empty_ready else 'chưa thấy'}"
            )
            self.vision.driver.click(*self.PAGE_NEXT_POINT)
            page_turns += 1
            self.waiter.sleep(self.PAGE_SETTLE_SECONDS)

        empty, product_point, top_point = self._wait_for_idle_open_panel(
            product_template=self.PRODUCT_TEMPLATE,
            label="Trà sấy",
            product_threshold=0.70,
        )
        self.context.log(
            "AUTO Trà sấy • panel READY • "
            f"page_turns={page_turns} • đường kéo={product_point} → {top_point}"
        )
        return empty, product_point, top_point

    def _drag_one_with_retry(
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
                    self._close_panel()
                    raise ScreenTimeout(
                        f"Thiếu nguyên liệu khi xếp Trà sấy {ordinal}/9"
                    )

                current = self._count_empty_slots()
                last_empty = current
                if current < empty_before:
                    if drag_attempt > 1 or verify_round > 1:
                        self.context.log(
                            f"AUTO Trà sấy • xếp {ordinal}/9 phục hồi sau recheck/retry "
                            f"• drag={drag_attempt}/{self.DRAG_ATTEMPTS} • "
                            f"verify={verify_round}/{self.VERIFY_RECHECKS} • "
                            f"ô trống {empty_before}→{current}"
                        )
                    return current
                if verify_round < self.VERIFY_RECHECKS:
                    self.waiter.sleep(self.VERIFY_RECHECK_SECONDS)

            if drag_attempt < self.DRAG_ATTEMPTS:
                self.context.log(
                    f"AUTO Trà sấy • xếp {ordinal}/9 chưa thấy ô trống giảm • "
                    f"thử lại gesture {drag_attempt + 1}/{self.DRAG_ATTEMPTS}"
                )
        return last_empty

    def produce_9_dried_teas(
        self,
        *,
        close_after_success: bool = True,
    ) -> ProductionResult:
        empty_before, product_point, top_point = self._open_and_find_product()
        empty_after = empty_before

        for ordinal in range(1, self.REQUIRED_COUNT + 1):
            self.context.ensure_running()
            current = self._drag_one_with_retry(
                ordinal=ordinal,
                product_point=product_point,
                top_point=top_point,
                empty_before=empty_after,
            )
            if current >= empty_after:
                self._close_panel()
                raise ScreenTimeout(
                    f"Kéo Trà sấy {ordinal}/9 không làm giảm ô trống sau "
                    f"{self.DRAG_ATTEMPTS} lần kéo x {self.VERIFY_RECHECKS} recheck: "
                    f"trước={empty_after}, sau={current}"
                )
            empty_after = current
            self.context.log(
                f"AUTO Trà sấy • đã xác minh xếp {ordinal}/9 • ô trống còn={current}"
            )

        if empty_before - empty_after != self.REQUIRED_COUNT:
            self._close_panel()
            raise ScreenTimeout("Hậu kiểm Trà sấy không đạt đúng 9/9 ô")
        if close_after_success:
            self._close_panel()
        else:
            self.context.log("AUTO Trà sấy • giữ panel mở để bàn giao sang Sửa máy")

        self.context.log("AUTO sản xuất Trà sấy hoàn tất • đã xác minh đủ 9/9 ô")
        return ProductionResult(
            item_id=self.PRODUCT_TEMPLATE,
            requested_count=self.REQUIRED_COUNT,
            queued_count=self.REQUIRED_COUNT,
            empty_before=empty_before,
            empty_after=empty_after,
        )
