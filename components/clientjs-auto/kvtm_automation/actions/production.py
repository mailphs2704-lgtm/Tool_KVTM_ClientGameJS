from __future__ import annotations

from dataclasses import dataclass

from ..context import AutomationContext
from ..errors import InventoryFull, ScreenTimeout
from ..runtime.auto_speed_config import AutoSpeedConfig
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter


__all__ = ["ProductionResult", "ProductionActions"]
FILE_FUNCTIONS = (
    "Thu VP bằng đúng năm click tức thì cùng tọa độ rồi mới kiểm tra panel sản xuất",
    "Dùng tốc độ thu VP làm khoảng nghỉ sau mỗi burst x5, không chèn nghỉ giữa năm click",
    "Chỉ công nhận panel mở khi ảnh đúng sản phẩm xuất hiện trong vùng thư viện panel",
    "Giữ nguyên panel cho tới khi đủ đúng 9/9 ô trống mới sản xuất lượt mới",
    "Mất ảnh sản phẩm tạm thời khi đang chờ chỉ recheck, không dừng AUTO",
    "Phát tín hiệu InventoryFull riêng khi kho đầy để workflow xuống quầy bán VP",
    "Xác minh đúng máy bằng template sản phẩm trước khi thao tác",
    "Đếm ô sản xuất trống bằng template và loại trùng hình học",
    "Kéo đúng chín Táo sấy từ ảnh thư viện xuống tâm ô top",
    "Mỗi lần kéo được recheck nhiều frame và retry tối đa ba gesture trước khi fail",
    "Hậu kiểm số ô trống giảm và dừng an toàn nếu giao dịch không khớp",
)


@dataclass(frozen=True)
class ProductionResult:
    item_id: str
    requested_count: int
    queued_count: int
    empty_before: int
    empty_after: int


class ProductionActions:
    """Self-contained Multi Dev dried-apple production transaction."""

    DRYER_FLOOR = 1
    DRYER_POINT = (262, 917)
    DRIED_APPLE_PRODUCTION_TEMPLATE = "tao_say"
    # Proven product-library centers from successful panels are around
    # Nước táo=(464,603), Táo sấy=(528,602), Vải vàng=(529,604). Restricting
    # matching to this panel-only area prevents farm/slot imagery from being
    # mistaken for an opened production panel.
    PRODUCT_SEARCH_ZONE = (420, 550, 170, 120)
    DRIED_APPLE_GUARD_THRESHOLD = 0.70
    EMPTY_SLOT_TEMPLATE = "o_trong"
    TOP_EMPTY_SLOT_ZONE = (335, 650, 130, 135)
    EMPTY_SLOT_ZONE = (335, 781, 395, 186)
    MATERIAL_ERROR_TEMPLATE = "x"
    MATERIAL_ERROR_ZONE = (682, 337, 142, 120)
    CLOSE_POINT = (965, 198)
    REQUIRED_COUNT = 9
    MIN_DISTANCE = 34
    PANEL_RECHECK_SECONDS = 1.0
    COLLECT_CLICK_BURST = 5
    DRAG_ATTEMPTS = 3
    VERIFY_RECHECKS = 4
    VERIFY_RECHECK_SECONDS = 0.18

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

    def _count_matches(
        self,
        name: str,
        zone: tuple[int, int, int, int],
        threshold: float,
    ) -> int:
        import cv2

        frame = self.vision.frame()
        if frame.ndim == 3 and frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        x, y, width, height = zone
        roi = frame[y:y + height, x:x + width]
        centers: list[tuple[int, int, float]] = []
        for path in self.vision.assets.candidates(name):
            template = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if template is None or template.size == 0:
                continue
            if template.shape[0] > roi.shape[0] or template.shape[1] > roi.shape[1]:
                continue
            scores = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
            while True:
                _minimum, maximum, _min_loc, maximum_location = cv2.minMaxLoc(scores)
                if float(maximum) < threshold:
                    break
                cx = x + maximum_location[0] + template.shape[1] // 2
                cy = y + maximum_location[1] + template.shape[0] // 2
                if all(
                    (cx - old_x) ** 2 + (cy - old_y) ** 2 >= self.MIN_DISTANCE ** 2
                    for old_x, old_y, _score in centers
                ):
                    centers.append((cx, cy, float(maximum)))
                left = max(0, maximum_location[0] - template.shape[1] // 2)
                top = max(0, maximum_location[1] - template.shape[0] // 2)
                right = min(scores.shape[1], maximum_location[0] + template.shape[1] // 2)
                bottom = min(scores.shape[0], maximum_location[1] + template.shape[0] // 2)
                scores[top:bottom, left:right] = -1.0
        self.context.detail(
            f"AUTO production matches | template={name} | count={len(centers)} | "
            f"threshold={threshold:.2f} | zone={zone}"
        )
        return len(centers)

    def _find_top_empty_slot(self):
        return self.vision.find(
            self.EMPTY_SLOT_TEMPLATE,
            threshold=0.82,
            zone=self.TOP_EMPTY_SLOT_ZONE,
            scales=(1.00, 1.15, 1.30, 1.45, 1.60),
            click=False,
        )

    def _count_empty_slots(self) -> int:
        top_match = self._find_top_empty_slot()
        top = 1 if top_match is not None else 0
        lower = min(8, self._count_matches(
            self.EMPTY_SLOT_TEMPLATE, self.EMPTY_SLOT_ZONE, 0.90
        ))
        total = top + lower
        self.context.detail(
            f"AUTO production empty slots | top={top}/1 | lower={lower}/8 | total={total}/9"
        )
        return total

    def _find_product_match(self, name: str, *, threshold: float = 0.70):
        return self.vision.find(
            name,
            threshold=threshold,
            zone=self.PRODUCT_SEARCH_ZONE,
            scales=(0.75, 0.90, 1.00, 1.10, 1.25),
            click=False,
        )

    def _panel_state(self) -> tuple[bool, bool]:
        frame = self.vision.frame()
        warehouse_full = self.vision.find(
            "full_kho",
            threshold=0.90,
            zone=(333, 363, 313, 115),
            scales=(0.90, 1.00, 1.10),
            click=False,
            frame=frame,
        )
        empty_ready = self.vision.find(
            self.EMPTY_SLOT_TEMPLATE,
            threshold=0.70,
            zone=self.EMPTY_SLOT_ZONE,
            scales=(0.90, 1.00, 1.10),
            click=False,
            frame=frame,
        )
        return warehouse_full is not None, empty_ready is not None

    def _raise_inventory_full(self, label: str) -> None:
        self.vision.driver.click(*self.CLOSE_POINT)
        self.context.stage("auto-production-warehouse-full")
        self.context.log(
            f"AUTO {label} • phát hiện full_kho • đóng bảng cảnh báo/panel • "
            "bàn giao workflow xuống quầy bán VP"
        )
        raise InventoryFull(f"{label}: kho đầy khi thu VP/sản xuất")

    def _send_collect_burst(
        self,
        *,
        machine_point: tuple[int, int],
    ) -> int:
        """Send exactly five raw clicks with no intentional gap or vision check."""
        self.context.ensure_running()
        for _ in range(self.COLLECT_CLICK_BURST):
            self.vision.driver.click(*machine_point)
        return self.COLLECT_CLICK_BURST

    def _click_until_panel_open(
        self,
        *,
        machine_point: tuple[int, int],
        product_template: str,
        label: str,
        product_threshold: float = 0.70,
    ) -> int:
        """Send true x5 bursts until the panel-only product anchor is visible.

        Empty-slot imagery is diagnostic only: it can also appear while the farm
        screen is still visible and therefore must never stop collection. The
        panel is accepted only when the requested production item is matched in
        the proven product-library zone. Until then, another x5 burst is sent.
        """
        click_count = 0
        burst_count = 0
        while True:
            self.context.ensure_running()
            burst_count += 1
            click_count += self._send_collect_burst(machine_point=machine_point)

            self.context.log(
                f"AUTO {label} • đã phát x5 click tức thì tại cùng tọa độ "
                f"• burst={burst_count} • tổng click={click_count}"
            )

            # vp_collect_delay is intentionally a post-burst settle delay.
            # There is no configured or artificial delay between the five clicks.
            self.waiter.sleep(self.speed_config.vp_collect_delay)
            self.context.ensure_running()

            warehouse_full, empty_ready = self._panel_state()
            if warehouse_full:
                self._raise_inventory_full(label)

            product = self._find_product_match(
                product_template, threshold=product_threshold
            )
            if product is not None:
                self.context.log(
                    f"AUTO {label} • panel đã mở sau burst x5 và đã xác minh ảnh "
                    f"{product_template} trong vùng thư viện • burst={burst_count} • "
                    f"tổng click={click_count} • center={product.center} • "
                    f"nghỉ sau burst={self.speed_config.vp_collect_delay:.3f}s"
                )
                return click_count

            if empty_ready and (burst_count == 1 or burst_count % 5 == 0):
                self.context.log(
                    f"AUTO {label} • thấy dấu ô trống nhưng CHƯA có ảnh {product_template} "
                    "trong vùng thư viện • KHÔNG coi panel đã mở • tiếp tục burst x5"
                )
            elif burst_count == 1 or burst_count % 5 == 0:
                self.context.log(
                    f"AUTO {label} • panel chưa hiện sau burst x5 "
                    "• tiếp tục một burst x5 tức thì mới • "
                    f"burst={burst_count} • tổng click={click_count}"
                )

    def _wait_for_idle_open_panel(
        self,
        *,
        product_template: str,
        label: str,
        product_threshold: float = 0.70,
    ) -> tuple[int, tuple[int, int], tuple[int, int]]:
        """Keep the verified production panel open until all 9 slots are empty."""
        wait_round = 0
        product_misses = 0
        while True:
            self.context.ensure_running()

            warehouse_full, _empty_anchor = self._panel_state()
            if warehouse_full:
                self._raise_inventory_full(label)

            product = self._find_product_match(
                product_template, threshold=product_threshold
            )
            if product is None:
                product_misses += 1
                if product_misses == 1 or product_misses % 10 == 0:
                    self.context.log(
                        f"AUTO {label} • ảnh sản phẩm tạm chưa khớp khi đang chờ "
                        f"• misses={product_misses} • KHÔNG dừng AUTO • "
                        f"giữ trạng thái và recheck sau {self.PANEL_RECHECK_SECONDS:.1f}s"
                    )
                self.waiter.sleep(self.PANEL_RECHECK_SECONDS)
                continue
            product_misses = 0

            top_slot = self._find_top_empty_slot()
            empty = self._count_empty_slots()
            if top_slot is not None and empty == self.REQUIRED_COUNT:
                self.context.log(
                    f"AUTO {label} • panel giữ nguyên đã READY • đủ {empty}/9 ô trống"
                )
                return empty, product.center, top_slot.center

            wait_round += 1
            if wait_round == 1 or wait_round % 10 == 0:
                self.context.log(
                    f"AUTO {label} • giữ nguyên panel sản xuất • "
                    f"đang có {empty}/9 ô trống • chờ máy chạy xong • "
                    f"recheck={self.PANEL_RECHECK_SECONDS:.1f}s • vòng={wait_round}"
                )
            self.waiter.sleep(self.PANEL_RECHECK_SECONDS)

    def _collect_finished_before_open(self) -> None:
        """Collect finished output in five-click bursts until the dryer panel opens."""
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
        self, *, close_after_success: bool = True
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