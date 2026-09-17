from __future__ import annotations

from ..errors import ProductSearchExhausted, ScreenTimeout
from .production import ProductionResult
from .production_panel import ProductionPanelActions


__all__ = ["DriedTeaProductionActions"]
FILE_FUNCTIONS = (
    "Thu VP và mở máy Trà sấy tại tầng 1 bằng shared collector tối thiểu 20 click",
    "Chỉ được chuyển trang tìm Trà sấy sau khi đã chứng minh panel sản xuất đang mở",
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
        """Collect first, prove the production panel, then page until tra_say appears."""
        click_count = 0
        open_round = 0
        product = None

        # Do not touch the page arrow while the machine panel is not proven open.
        # A product match or the shared empty-slot anchor is valid panel evidence.
        while True:
            self.context.ensure_running()
            open_round += 1
            click_count += self.collect_vp_before_machine_panel(
                machine_point=self.MACHINE_POINT,
                label="Trà sấy",
            )

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
                    "AUTO Trà sấy • panel SX VERIFIED bằng product anchor ngay trang hiện tại • "
                    f"open_round={open_round} • tổng click={click_count} • center={product.center}"
                )
                break

            if empty_ready:
                self.context.log(
                    "AUTO Trà sấy • panel SX VERIFIED bằng empty-slot anchor • "
                    f"open_round={open_round} • tổng click={click_count} • "
                    "được phép bắt đầu chuyển trang"
                )
                break

            self.context.log(
                "AUTO Trà sấy • CHƯA chứng minh panel SX đang mở • "
                "KHÔNG click mũi tên trang • lặp shared thu VP tối thiểu 20 click • "
                f"open_round={open_round} • tổng click={click_count}"
            )
            if open_round >= self.PANEL_OPEN_ROUNDS:
                raise ProductSearchExhausted(
                    f"Trà sấy: không xác nhận được panel sau {open_round} vòng"
                )

        page_turns = 0
        if product is None:
            product, page_turns = self.find_product_bounded_pages(
                product_template=self.PRODUCT_TEMPLATE,
                label="Trà sấy",
                page_next_point=self.PAGE_NEXT_POINT,
                product_threshold=0.70,
            )

        empty, product_point, top_point = self._wait_for_idle_open_panel(
            product_template=self.PRODUCT_TEMPLATE,
            label="Trà sấy",
            product_threshold=0.70,
        )
        self.context.log(
            "AUTO Trà sấy • panel READY • "
            f"page_turns={page_turns} • tổng click thu VP={click_count} • "
            f"đường kéo={product_point} → {top_point}"
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
