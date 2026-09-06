from __future__ import annotations

from dataclasses import dataclass

from ..context import AutomationContext
from ..errors import ScreenTimeout
from ..runtime.auto_speed_config import AutoSpeedConfig
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter


__all__ = ["ProductionResult", "ProductionActions"]
FILE_FUNCTIONS = (
    "Thu VP hoàn thành đang chắn trước máy bằng nhịp AUTO PRO đối chiếu",
    "Chỉ mở máy sấy tầng 1 sau khi đã thu VP và xác minh panel",
    "Xác minh đúng máy bằng template Táo sấy trước khi thao tác",
    "Đếm ô sản xuất trống bằng template và loại trùng hình học",
    "Kéo đúng chín Táo sấy theo slot AUTO PRO",
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
    """Clean production transaction; AUTO PRO is coordinate reference only."""

    DRYER_FLOOR = 1
    DRYER_POINT = (262, 917)
    DRIED_APPLE_PRODUCTION_TEMPLATE = "tao_say"
    PRODUCT_SEARCH_ZONE = (9, 341, 402, 386)
    DRIED_APPLE_GUARD_ZONE = (180, 360, 150, 125)
    DRIED_APPLE_GUARD_THRESHOLD = 0.28
    EMPTY_SLOT_TEMPLATE = "o_trong"
    EMPTY_SLOT_ZONE = (335, 781, 395, 186)
    PRODUCT_SLOT_0 = (252, 421)
    QUEUE_DROP_POINT = (400, 719)
    MATERIAL_ERROR_TEMPLATE = "x"
    MATERIAL_ERROR_ZONE = (682, 337, 142, 120)
    CLOSE_POINT = (965, 198)
    REQUIRED_COUNT = 9
    MIN_DISTANCE = 34

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

    def _panel_state(self) -> tuple[bool, bool]:
        frame = self.vision.frame()
        warehouse_full = self.vision.find(
            "fullkho",
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

    def _collect_finished_before_open(self) -> None:
        """Collect finished output first; opening the panel is the verification."""

        self.context.ensure_running()
        for batch, click_count in ((1, 1), (2, 5), (3, 5)):
            for _pulse in range(click_count):
                self.vision.driver.click(*self.DRYER_POINT)
                self.waiter.sleep(0.10)
            self.waiter.sleep(0.50)
            warehouse_full, panel_ready = self._panel_state()
            self.context.log(
                "AUTO sản xuất • thu VP trước máy "
                f"nhịp {batch}/3 • clicks={click_count} • "
                f"panel={panel_ready} • fullkho={warehouse_full}"
            )
            if warehouse_full:
                self.vision.driver.click(*self.CLOSE_POINT)
                raise ScreenTimeout(
                    "Đã thu VP trước máy nhưng kho đang đầy; dừng trước khi sản xuất"
                )
            if panel_ready:
                self.context.log(
                    "AUTO sản xuất • đã thu hết VP chắn máy và mở được panel tầng 1"
                )
                return
        raise ScreenTimeout(
            "Không thu hết VP hoàn thành hoặc không mở được panel máy sấy tầng 1"
        )

    def _open_verified_dryer(self) -> tuple[int, tuple[int, int]]:
        self._collect_finished_before_open()

        product = None
        for attempt in range(1, 4):
            product = self.vision.find(
                self.DRIED_APPLE_PRODUCTION_TEMPLATE,
                threshold=self.DRIED_APPLE_GUARD_THRESHOLD,
                zone=self.DRIED_APPLE_GUARD_ZONE,
                scales=(0.75, 0.90, 1.00, 1.10, 1.25),
                click=False,
            )
            if product is not None:
                break
            self.context.log(
                "AUTO sản xuất • chưa khớp Táo sấy tại slot cố định "
                f"(252,421) • lần {attempt}/3"
            )
            self.waiter.sleep(0.35)
        if product is None:
            self.vision.driver.click(*self.CLOSE_POINT)
            raise ScreenTimeout(
                "Panel máy đã mở nhưng slot cố định (252,421) không khớp Táo sấy; "
                "không chọn vật phẩm khác"
            )
        self.context.log(
            "AUTO sản xuất • xác minh Táo sấy tại slot cố định "
            f"• score={product.score:.3f} • center={product.center}"
        )
        empty = self._count_matches(
            self.EMPTY_SLOT_TEMPLATE, self.EMPTY_SLOT_ZONE, 0.90
        )
        if empty < self.REQUIRED_COUNT:
            self.vision.driver.click(*self.CLOSE_POINT)
            raise ScreenTimeout(
                f"Máy sấy chỉ có {empty}/9 ô trống; chưa đủ để sản xuất đúng 9 Táo sấy"
            )
        self.context.log(
            f"AUTO sản xuất • đúng máy sấy tầng 1 • có {empty} ô trống"
        )
        return empty, product.center

    def produce_9_dried_apples(self) -> ProductionResult:
        empty_before, product_point = self._open_verified_dryer()
        queued = 0
        for ordinal in range(1, self.REQUIRED_COUNT + 1):
            self.context.ensure_running()
            self.vision.driver.swipe_points(
                (product_point, self.QUEUE_DROP_POINT),
                duration=0.02,
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
                self.vision.driver.click(*self.CLOSE_POINT)
                raise ScreenTimeout(
                    f"Thiếu nguyên liệu khi xếp Táo sấy {ordinal}/9"
                )
            queued += 1
            self.context.log(
                f"AUTO sản xuất • đã xếp Táo sấy {ordinal}/9 vào hàng chờ"
            )

        self.waiter.sleep(0.40)
        empty_after = self._count_matches(
            self.EMPTY_SLOT_TEMPLATE, self.EMPTY_SLOT_ZONE, 0.90
        )
        consumed = max(0, empty_before - empty_after)
        self.vision.driver.click(*self.CLOSE_POINT)
        if consumed < self.REQUIRED_COUNT:
            raise ScreenTimeout(
                "Hậu kiểm máy sấy không đủ 9 ô thay đổi: "
                f"trước={empty_before}, sau={empty_after}, xác minh={consumed}/9"
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
