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
    "Probe bounded candidate tầng 2 sau goDown(4), không lặp click vô hạn khi lệch tầng",
    "Thu VP bằng burst x5 liên tục cho tới khi ảnh Nước táo xuất hiện trong vùng thư viện panel",
    "Ô trống chỉ là tín hiệu phụ, không được tự xác nhận panel đã mở",
    "Giữ nguyên panel cho tới khi đủ đúng 9/9 ô trống mới sản xuất lượt mới",
    "Mất ảnh sản phẩm tạm thời khi chờ không làm dừng AUTO",
    "Phát tín hiệu kho đầy riêng để workflow xuống quầy bán VP rồi quay lại tầng 2",
    "Kéo Nước táo xuống ô top động đúng chín lần",
    "Mỗi lần kéo được recheck nhiều frame và retry tối đa ba gesture trước khi fail",
    "Hậu kiểm mỗi lần kéo làm giảm đúng bộ đếm ô trống",
)


class AppleJuiceProductionActions:
    """Queue exactly nine apple juices on the verified floor-2 panel."""

    MACHINE_POINT = (262, 917)
    PRODUCT_TEMPLATE = "nuoc_tao"
    CLOSE_POINT = (965, 198)
    REQUIRED_COUNT = 9
    DRAG_ATTEMPTS = 3
    VERIFY_RECHECKS = 4
    VERIFY_RECHECK_SECONDS = 0.18

    # The direct floor6->floor2 route is only a candidate until the production
    # item itself proves the destination. Two x5 bursts are enough to clear a
    # full nine-output queue and expose the panel, while remaining bounded on a
    # wrong floor so recovery can take over instead of clicking forever.
    DIRECT_FLOOR_PROBE_BURSTS = 2
    DIRECT_FLOOR_PROBE_RECHECKS = 3
    DIRECT_FLOOR_PROBE_RECHECK_SECONDS = 0.18

    def __init__(self, context: AutomationContext, vision: VisionEngine,
                 waiter: Waiter, speed_config: AutoSpeedConfig | None = None) -> None:
        self.context = context
        self.vision = vision
        self.waiter = waiter
        self.speed_config = speed_config or AutoSpeedConfig()
        self.slots = ProductionActions(context, vision, waiter, self.speed_config)

    def probe_floor_2_machine(self) -> bool:
        """Bounded proof that the fast goDown(4) landed at the Nước táo machine.

        This is deliberately separate from the normal production opener, which is
        allowed to keep collecting until the requested panel opens. A wrong-floor
        route must never inherit that unbounded behavior. On success or failure we
        close the probe panel and let the normal production transaction start from
        a clean state. ``full_kho`` is not accepted as floor proof; it falls back
        to exact-main normalization, after which the normal warehouse recovery can
        handle InventoryFull on the verified floor 2.
        """
        click_count = 0
        for burst in range(1, self.DIRECT_FLOOR_PROBE_BURSTS + 1):
            self.context.ensure_running()
            click_count += self.slots._send_collect_burst(
                machine_point=self.MACHINE_POINT
            )
            self.context.log(
                "AUTO Nước táo • probe candidate tầng 2 • "
                f"burst={burst}/{self.DIRECT_FLOOR_PROBE_BURSTS} • "
                f"tổng click={click_count}"
            )
            self.waiter.sleep(self.speed_config.vp_collect_delay)

            for recheck in range(1, self.DIRECT_FLOOR_PROBE_RECHECKS + 1):
                self.context.ensure_running()
                warehouse_full, _empty_ready = self.slots._panel_state()
                if warehouse_full:
                    self.vision.driver.click(*self.CLOSE_POINT)
                    self.waiter.sleep(0.25)
                    self.context.log(
                        "AUTO Nước táo • probe direct gặp full_kho • "
                        "không dùng popup này để chứng minh tầng • chuyển fallback exact-main"
                    )
                    return False

                product = self.slots._find_product_match(
                    self.PRODUCT_TEMPLATE, threshold=0.70
                )
                if product is not None:
                    self.context.log(
                        "AUTO Nước táo • direct floor 2 PASS • "
                        f"đã thấy anchor {self.PRODUCT_TEMPLATE} trong panel • "
                        f"center={product.center} • burst={burst} • recheck={recheck}"
                    )
                    self.vision.driver.click(*self.CLOSE_POINT)
                    self.waiter.sleep(0.25)
                    return True

                if recheck < self.DIRECT_FLOOR_PROBE_RECHECKS:
                    self.waiter.sleep(self.DIRECT_FLOOR_PROBE_RECHECK_SECONDS)

        # Wrong floor / transient route miss: close anything that may have opened
        # and hand control back to the background-independent main recovery.
        self.vision.driver.click(*self.CLOSE_POINT)
        self.waiter.sleep(0.25)
        self.context.log(
            "AUTO Nước táo • direct floor 2 MISS • không thấy anchor nuoc_tao sau "
            f"{self.DIRECT_FLOOR_PROBE_BURSTS} burst x5 • đóng panel và fallback exact-main"
        )
        return False

    def _open_verified(self):
        click_count = self.slots._click_until_panel_open(
            machine_point=self.MACHINE_POINT,
            product_template=self.PRODUCT_TEMPLATE,
            label="Nước táo",
            product_threshold=0.70,
        )
        empty, product_point, top_point = self.slots._wait_for_idle_open_panel(
            product_template=self.PRODUCT_TEMPLATE,
            label="Nước táo",
            product_threshold=0.70,
        )
        self.context.log(
            "AUTO Nước táo • panel giữ nguyên READY • "
            f"tổng click thu VP={click_count} • đường kéo={product_point} → {top_point}"
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
        """Retry a lost/slow production gesture without failing on one early frame."""
        last_empty = int(empty_before)
        for drag_attempt in range(1, self.DRAG_ATTEMPTS + 1):
            self.context.ensure_running()
            self.vision.driver.swipe_points((product_point, top_point), duration=0.02)
            self.waiter.sleep(self.speed_config.vp_production_delay)

            for verify_round in range(1, self.VERIFY_RECHECKS + 1):
                self.context.ensure_running()
                current = self.slots._count_empty_slots()
                last_empty = current
                if current < empty_before:
                    if drag_attempt > 1 or verify_round > 1:
                        self.context.log(
                            f"AUTO Nước táo • xếp {ordinal}/9 đã phục hồi sau recheck/retry "
                            f"• drag={drag_attempt}/{self.DRAG_ATTEMPTS} • "
                            f"verify={verify_round}/{self.VERIFY_RECHECKS} • "
                            f"ô trống {empty_before}→{current}"
                        )
                    return current
                if verify_round < self.VERIFY_RECHECKS:
                    self.waiter.sleep(self.VERIFY_RECHECK_SECONDS)

            if drag_attempt < self.DRAG_ATTEMPTS:
                self.context.log(
                    f"AUTO Nước táo • xếp {ordinal}/9 chưa thấy ô trống giảm sau "
                    f"{self.VERIFY_RECHECKS} frame • thử lại gesture "
                    f"{drag_attempt + 1}/{self.DRAG_ATTEMPTS}"
                )

        return last_empty

    def produce_9_apple_juices(
        self, *, close_after_success: bool = True
    ) -> ProductionResult:
        empty_before, product_point, top_point = self._open_verified()
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
                self.vision.driver.click(*self.CLOSE_POINT)
                raise ScreenTimeout(
                    f"Kéo Nước táo {ordinal}/9 không làm giảm ô trống sau "
                    f"{self.DRAG_ATTEMPTS} lần kéo x {self.VERIFY_RECHECKS} recheck: "
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
