from __future__ import annotations

from dataclasses import dataclass

from ..context import AutomationContext
from ..errors import ScreenTimeout
from ..runtime.auto_speed_config import AutoSpeedConfig
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter


__all__ = ["ProductionResult", "ProductionActions"]
FILE_FUNCTIONS = (
    "Click thu VP liên tục đến khi panel máy thực sự mở",
    "Cho phép chỉnh riêng tốc độ click thu VP trước khi panel mở",
    "Chỉ mở máy sấy tầng 1 sau khi đã thu VP và xác minh panel",
    "Xác minh đúng máy bằng template Táo sấy trước khi thao tác",
    "Đếm ô sản xuất trống bằng template và loại trùng hình học",
    "Kéo đúng chín Táo sấy từ ảnh thư viện xuống tâm ô top",
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
    PRODUCT_SEARCH_ZONE = None
    DRIED_APPLE_GUARD_THRESHOLD = 0.70
    EMPTY_SLOT_TEMPLATE = "o_trong"
    TOP_EMPTY_SLOT_ZONE = (335, 650, 130, 135)
    EMPTY_SLOT_ZONE = (335, 781, 395, 186)
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

    def _collect_finished_before_open(self) -> None:
        """Collect finished output first; opening the panel is the verification."""

        click_count = 0
        while True:
            self.context.ensure_running()
            click_count += 1
            self.vision.driver.click(*self.DRYER_POINT)
            self.waiter.sleep(self.speed_config.vp_collect_delay)
            warehouse_full, panel_ready = self._panel_state()
            if click_count == 1 or click_count % 5 == 0 or panel_ready:
                self.context.log(
                    "AUTO sản xuất • click thu VP/mở máy "
                    f"• clicks={click_count} • panel={panel_ready} • "
                    f"fullkho={warehouse_full} • "
                    f"delay={self.speed_config.vp_collect_delay:.3f}s"
                )
            if warehouse_full:
                self.vision.driver.click(*self.CLOSE_POINT)
                raise ScreenTimeout(
                    "Đã thu VP trước máy nhưng kho đang đầy; dừng trước khi sản xuất"
                )
            if panel_ready:
                self.context.log(
                    "AUTO sản xuất • đã thu hết VP chắn máy và mở được panel tầng 1 "
                    f"• dừng click sau {click_count} lần"
                )
                return

    def _open_verified_dryer(self) -> tuple[int, tuple[int, int], tuple[int, int]]:
        self._collect_finished_before_open()

        product = None
        for attempt in range(1, 4):
            product = self.vision.find(
                self.DRIED_APPLE_PRODUCTION_TEMPLATE,
                threshold=self.DRIED_APPLE_GUARD_THRESHOLD,
                zone=self.PRODUCT_SEARCH_ZONE,
                scales=(0.75, 0.90, 1.00, 1.10, 1.25),
                click=False,
            )
            if product is not None:
                break
            self.context.log(
                "AUTO sản xuất • chưa khớp ảnh thư viện tao_say trên panel "
                f"• lần {attempt}/3"
            )
            self.waiter.sleep(0.35)
        if product is None:
            self.vision.driver.click(*self.CLOSE_POINT)
            raise ScreenTimeout(
                "Panel máy đã mở nhưng không khớp chắc chắn ảnh thư viện tao_say; "
                "dừng trước gesture để không chọn nhầm vật phẩm"
            )
        self.context.log(
            "AUTO sản xuất • xác minh ảnh thư viện tao_say "
            f"• score={product.score:.3f} • center={product.center}"
        )
        top_slot = self._find_top_empty_slot()
        if top_slot is None:
            self.vision.driver.click(*self.CLOSE_POINT)
            raise ScreenTimeout(
                "Không tìm thấy ô top bằng ảnh thư viện o_trong; dừng trước gesture"
            )
        empty = self._count_empty_slots()
        if empty < self.REQUIRED_COUNT:
            self.vision.driver.click(*self.CLOSE_POINT)
            raise ScreenTimeout(
                f"Máy sấy chỉ có {empty}/9 ô trống; chưa đủ để sản xuất đúng 9 Táo sấy"
            )
        self.context.log(
            f"AUTO sản xuất • đúng máy sấy tầng 1 • có {empty} ô trống"
        )
        self.context.log(
            "AUTO sản xuất • đường kéo đã xác minh "
            f"• tao_say={product.center} → top={top_slot.center}"
        )
        return empty, product.center, top_slot.center

    def produce_9_dried_apples(
        self, *, close_after_success: bool = True
    ) -> ProductionResult:
        empty_before, product_point, top_point = self._open_verified_dryer()
        empty_after = empty_before
        queued = 0
        for ordinal in range(1, self.REQUIRED_COUNT + 1):
            self.context.ensure_running()
            self.vision.driver.swipe_points(
                (product_point, top_point),
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
            current_empty = self._count_empty_slots()
            if current_empty >= empty_after:
                self.vision.driver.click(*self.CLOSE_POINT)
                raise ScreenTimeout(
                    "Kéo Táo sấy không làm giảm ô trống: "
                    f"lần={ordinal}/9, trước={empty_after}, sau={current_empty}, "
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
