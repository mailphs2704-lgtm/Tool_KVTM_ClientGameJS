from __future__ import annotations

from ..errors import ScreenTimeout
from .production import ProductionResult
from .production_panel import ProductionPanelActions


__all__ = ["RoseOilProductionActions"]
FILE_FUNCTIONS = (
    "Mở đúng máy TDHH tại logical machine point dùng chung của các tầng sản xuất",
    "Dùng ProductionPanelActions cho panel/slot/kho đầy/sai máy dùng chung",
    "Xác minh panel bằng template tinh_dau_hh trước mọi thao tác",
    "Chờ đủ số ô trống theo transaction rồi xếp chính xác 7 hoặc 9 TDHH",
    "Hậu kiểm mỗi lần kéo bằng số ô trống giảm và fail-close khi thiếu nguyên liệu",
    "Giữ panel mở sau PASS để bàn giao Sửa máy",
    "Cung cấp Action đóng panel có settle để Recipe/Navigation không click tọa độ trực tiếp",
)


class RoseOilProductionActions(ProductionPanelActions):
    """Exact-count Tinh dầu hoa hồng production transaction."""

    ROSE_OIL_FLOOR = 5
    ROSE_OIL_POINT = (262, 917)
    ROSE_OIL_TEMPLATE = "tinh_dau_hh"
    ROSE_OIL_GUARD_THRESHOLD = 0.70
    TARGET_COUNT = 7
    STEP4_TARGET_COUNT = 9
    REQUIRED_COUNT = TARGET_COUNT
    MATERIAL_ERROR_TEMPLATE = "x"
    MATERIAL_ERROR_ZONE = (682, 337, 142, 120)
    DRAG_ATTEMPTS = 3
    VERIFY_RECHECKS = 4
    VERIFY_RECHECK_SECONDS = 0.18
    KNOWN_PRODUCT_TEMPLATES = (
        "tao_say",
        "nuoc_tao",
        "vai_vang",
        "tinh_dau_hh",
    )

    def close_panel_for_navigation(self, *, settle_seconds: float = 0.35) -> None:
        self.context.ensure_running()
        self.vision.driver.click(*self.CLOSE_POINT)
        self.waiter.sleep(max(0.0, float(settle_seconds)))
        self.context.log("AUTO TDHH • đóng panel trước điều hướng")

    def _open_verified_rose_oil_machine(
        self,
        *,
        required_count: int | None = None,
    ) -> tuple[int, tuple[int, int], tuple[int, int]]:
        required = int(
            self.REQUIRED_COUNT if required_count is None else required_count
        )
        original_required = int(self.REQUIRED_COUNT)
        self.REQUIRED_COUNT = required
        try:
            click_count = self._click_until_panel_open(
                machine_point=self.ROSE_OIL_POINT,
                product_template=self.ROSE_OIL_TEMPLATE,
                label="Tinh dầu hoa hồng",
                product_threshold=self.ROSE_OIL_GUARD_THRESHOLD,
            )
            self.context.log(
                "AUTO TDHH • đã mở đúng panel tầng 5 bằng burst thu VP • "
                f"tổng click={click_count}"
            )
            empty, product_point, top_point = self._wait_for_idle_open_panel(
                product_template=self.ROSE_OIL_TEMPLATE,
                label="Tinh dầu hoa hồng",
                product_threshold=self.ROSE_OIL_GUARD_THRESHOLD,
            )
        finally:
            self.REQUIRED_COUNT = original_required

        self.context.log(
            "AUTO TDHH • panel tầng 5 VERIFIED • "
            f"empty={empty} • required={required} • "
            f"tinh_dau_hh={product_point} → top={top_point}"
        )
        return empty, product_point, top_point

    def _drag_one_with_retry(
        self,
        *,
        ordinal: int,
        target_count: int,
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
                        f"Thiếu Hồng/Tuyết khi xếp TDHH {ordinal}/{target_count}"
                    )

                current_empty = self._count_empty_slots()
                last_empty = current_empty
                if current_empty < empty_before:
                    if drag_attempt > 1 or verify_round > 1:
                        self.context.log(
                            "AUTO TDHH • gesture phục hồi sau recheck/retry • "
                            f"ordinal={ordinal}/{target_count} • "
                            f"drag={drag_attempt}/{self.DRAG_ATTEMPTS} • "
                            f"verify={verify_round}/{self.VERIFY_RECHECKS} • "
                            f"empty={empty_before}→{current_empty}"
                        )
                    return current_empty
                if verify_round < self.VERIFY_RECHECKS:
                    self.waiter.sleep(self.VERIFY_RECHECK_SECONDS)

            if drag_attempt < self.DRAG_ATTEMPTS:
                self.context.log(
                    "AUTO TDHH • chưa thấy ô trống giảm • retry gesture • "
                    f"ordinal={ordinal}/{target_count} • "
                    f"next={drag_attempt + 1}/{self.DRAG_ATTEMPTS}"
                )
        return last_empty

    def _produce_rose_oils(
        self,
        *,
        target_count: int,
        close_after_success: bool,
    ) -> ProductionResult:
        requested = int(target_count)
        if requested not in (self.TARGET_COUNT, self.STEP4_TARGET_COUNT):
            raise ValueError(
                "TDHH production chỉ hỗ trợ exact-count 7 hoặc 9; "
                f"requested={requested}"
            )

        empty_before, product_point, top_point = self._open_verified_rose_oil_machine(
            required_count=requested,
        )
        empty_after = empty_before
        queued = 0

        for ordinal in range(1, requested + 1):
            current_empty = self._drag_one_with_retry(
                ordinal=ordinal,
                target_count=requested,
                product_point=product_point,
                top_point=top_point,
                empty_before=empty_after,
            )
            if current_empty >= empty_after:
                self.vision.driver.click(*self.CLOSE_POINT)
                raise ScreenTimeout(
                    "Kéo TDHH không làm giảm ô trống sau retry: "
                    f"lần={ordinal}/{requested}, "
                    f"trước={empty_after}, sau={current_empty}"
                )
            empty_after = current_empty
            queued += 1
            self.context.log(
                f"AUTO TDHH • đã xác minh xếp {ordinal}/{requested} • "
                f"ô trống còn={empty_after}"
            )

        consumed = max(0, empty_before - empty_after)
        if queued != requested or consumed != requested:
            self.vision.driver.click(*self.CLOSE_POINT)
            raise ScreenTimeout(
                f"Hậu kiểm TDHH không đúng {requested} ô thay đổi: "
                f"queued={queued}, trước={empty_before}, sau={empty_after}, "
                f"delta={consumed}"
            )

        if close_after_success:
            self.vision.driver.click(*self.CLOSE_POINT)
        else:
            self.context.log(
                "AUTO TDHH • giữ panel mở để bàn giao sang Sửa máy"
            )

        self.context.stage("auto-rose-oil-production-pass")
        self.context.log(
            f"AUTO TDHH • production PASS {requested}/{requested}"
        )
        return ProductionResult(
            item_id=self.ROSE_OIL_TEMPLATE,
            requested_count=requested,
            queued_count=queued,
            empty_before=empty_before,
            empty_after=empty_after,
        )

    def produce_7_rose_oils(
        self,
        *,
        close_after_success: bool = True,
    ) -> ProductionResult:
        return self._produce_rose_oils(
            target_count=self.TARGET_COUNT,
            close_after_success=close_after_success,
        )

    def produce_9_rose_oils(
        self,
        *,
        close_after_success: bool = True,
    ) -> ProductionResult:
        return self._produce_rose_oils(
            target_count=self.STEP4_TARGET_COUNT,
            close_after_success=close_after_success,
        )