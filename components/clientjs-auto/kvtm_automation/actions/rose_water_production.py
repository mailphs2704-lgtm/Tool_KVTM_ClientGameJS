from __future__ import annotations

from ..errors import ScreenTimeout
from .production import ProductionResult
from .production_panel import ProductionPanelActions


__all__ = ["RoseWaterProductionActions"]


class RoseWaterProductionActions(ProductionPanelActions):
    """Queue exactly nine rose waters from the paged floor-8 machine panel."""

    MACHINE_POINT = (262, 917)
    PRODUCT_TEMPLATE = "nuoc_hoa_hong"
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
        """Collect VP, prove the production panel, then page until rose water appears."""
        click_count = 0
        open_round = 0
        product = None

        while True:
            self.context.ensure_running()
            open_round += 1
            click_count += self.collect_vp_before_machine_panel(
                machine_point=self.MACHINE_POINT,
                label="Nước hoa hồng",
            )

            frame = self.vision.frame()
            warehouse_full, empty_ready = self._panel_state(frame=frame)
            if warehouse_full:
                self._raise_inventory_full("Nước hoa hồng")

            product = self._find_product_match(
                self.PRODUCT_TEMPLATE,
                threshold=0.70,
                frame=frame,
            )
            if product is not None:
                self.context.log(
                    "AUTO Nước hoa hồng • panel SX VERIFIED bằng product anchor ngay trang hiện tại • "
                    f"open_round={open_round} • tổng click={click_count} • center={product.center}"
                )
                break

            if empty_ready:
                self.context.log(
                    "AUTO Nước hoa hồng • panel SX VERIFIED bằng empty-slot anchor • "
                    f"open_round={open_round} • tổng click={click_count} • "
                    "được phép bắt đầu chuyển trang tìm sản phẩm"
                )
                break

            self.context.log(
                "AUTO Nước hoa hồng • CHƯA chứng minh panel SX đang mở • "
                "KHÔNG click mũi tên trang • lặp shared thu VP tối thiểu 20 click • "
                f"open_round={open_round} • tổng click={click_count}"
            )

        page_turns = 0
        missing_panel_rounds = 0
        while product is None:
            self.context.ensure_running()
            frame = self.vision.frame()
            warehouse_full, empty_ready = self._panel_state(frame=frame)
            if warehouse_full:
                self._raise_inventory_full("Nước hoa hồng")

            product = self._find_product_match(
                self.PRODUCT_TEMPLATE,
                threshold=0.70,
                frame=frame,
            )
            if product is not None:
                self.context.log(
                    "AUTO Nước hoa hồng • tìm thấy template sau chuyển trang • "
                    f"page_turns={page_turns} • center={product.center} • "
                    f"score={product.score:.3f}"
                )
                break

            if not empty_ready:
                missing_panel_rounds += 1
                if missing_panel_rounds == 1 or missing_panel_rounds % 10 == 0:
                    self.context.log(
                        "AUTO Nước hoa hồng • mất panel-open anchor khi đang tìm template • "
                        "KHÔNG chuyển trang • chờ/recheck • "
                        f"miss={missing_panel_rounds}"
                    )
                self.waiter.sleep(self.PAGE_SETTLE_SECONDS)
                continue

            missing_panel_rounds = 0
            self.context.log(
                "AUTO Nước hoa hồng • panel SX đang mở VERIFIED • chưa thấy template • "
                "click mũi tên phải đúng 1 lần "
                f"tại {self.PAGE_NEXT_POINT} • page_turn={page_turns + 1}"
            )
            self.vision.driver.click(*self.PAGE_NEXT_POINT)
            page_turns += 1
            self.waiter.sleep(self.PAGE_SETTLE_SECONDS)

        empty, product_point, top_point = self._wait_for_idle_open_panel(
            product_template=self.PRODUCT_TEMPLATE,
            label="Nước hoa hồng",
            product_threshold=0.70,
        )
        self.context.log(
            "AUTO Nước hoa hồng • panel READY • "
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
                        f"Thiếu nguyên liệu khi xếp Nước hoa hồng {ordinal}/9"
                    )

                current = self._count_empty_slots()
                last_empty = current
                if current < empty_before:
                    return current
                if verify_round < self.VERIFY_RECHECKS:
                    self.waiter.sleep(self.VERIFY_RECHECK_SECONDS)

            if drag_attempt < self.DRAG_ATTEMPTS:
                self.context.log(
                    f"AUTO Nước hoa hồng • xếp {ordinal}/9 chưa thấy ô trống giảm • "
                    f"thử lại gesture {drag_attempt + 1}/{self.DRAG_ATTEMPTS}"
                )
        return last_empty

    def produce_9_rose_waters(
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
                    f"Kéo Nước hoa hồng {ordinal}/9 không làm giảm ô trống sau retry: "
                    f"trước={empty_after}, sau={current}"
                )
            empty_after = current
            self.context.log(
                f"AUTO Nước hoa hồng • đã xác minh xếp {ordinal}/9 • ô trống còn={current}"
            )

        if empty_before - empty_after != self.REQUIRED_COUNT:
            self._close_panel()
            raise ScreenTimeout("Hậu kiểm Nước hoa hồng không đạt đúng 9/9 ô")
        if close_after_success:
            self._close_panel()
        else:
            self.context.log(
                "AUTO Nước hoa hồng • giữ panel mở để bàn giao sang Sửa máy"
            )

        self.context.log(
            "AUTO sản xuất Nước hoa hồng hoàn tất • đã xác minh đủ 9/9 ô"
        )
        return ProductionResult(
            item_id=self.PRODUCT_TEMPLATE,
            requested_count=self.REQUIRED_COUNT,
            queued_count=self.REQUIRED_COUNT,
            empty_before=empty_before,
            empty_after=empty_after,
        )
