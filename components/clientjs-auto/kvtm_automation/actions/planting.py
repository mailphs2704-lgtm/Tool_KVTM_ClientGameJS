from __future__ import annotations

from ..context import AutomationContext
from ..errors import ScreenTimeout
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter


__all__ = ["PlantingActions"]
FILE_FUNCTIONS = (
    "Đi từ màn hình chính lên đúng mốc cây bằng AUTO PRO goUp(1)",
    "Mở trạng thái chậu đầu tầng một",
    "Phân biệt cây chín và chậu trống bằng template AUTO PRO",
    "Thu hoạch đúng 27 chậu nếu phát hiện cây chín",
    "Nhận diện đúng hạt Hoa hồng bằng template AUTO PRO",
    "Tạo đường zíc-zắc 27 chậu qua năm tầng",
    "Kéo một lần từ hạt giống qua đúng 27 chậu",
    "Đóng bảng gieo và ghi log kết quả",
)


class PlantingActions:
    """Plant exactly 27 roses with the recovered AUTO PRO farm geometry."""

    ROSE_TEMPLATE = "cay_hong"
    TREE_COUNT = 27
    TREES_PER_LAYER = 6
    START_POINT = (325, 799)
    X_COORDS_ODD = (335, 490, 578, 645, 720, 835)
    X_COORDS_EVEN = (335, 430, 505, 595, 665, 835)
    Y_LAYERS = (940, 725, 505, 280, 40)
    FARM_PATH_27 = (
        START_POINT,
        (335, 940), (835, 940),
        (835, 725), (335, 725),
        (335, 505), (835, 505),
        (835, 280), (335, 280),
        (335, 40), (578, 40),
    )
    OPEN_PLANT_POINT = (388, 946)
    CLOSE_POINT = (965, 198)
    CLOSE_SIDE_POINT = (975, 316)
    GO_UP_ONE_START = (514, 214)
    GO_UP_ONE_END = (514, 314)
    GO_UP_ONE_DURATION = 0.35
    SEED_ZONE = (179, 773, 230, 166)
    EMPTY_READY_ZONE = (124, 729, 347, 236)
    HARVEST_ZONE = (222, 703, 218, 191)
    SWIPE_DURATION = 0.035

    def __init__(
        self,
        context: AutomationContext,
        vision: VisionEngine,
        waiter: Waiter,
    ) -> None:
        self.context = context
        self.vision = vision
        self.waiter = waiter

    @classmethod
    def rose_path(cls) -> tuple[tuple[int, int], ...]:
        """Return the immutable AUTO PRO reference path for 27 pots."""
        return cls.FARM_PATH_27

    def _go_up_one(self) -> None:
        """Mirror the AUTO PRO transition used immediately after goDownLast."""
        self.context.ensure_running()
        self.vision.driver.click(*self.CLOSE_SIDE_POINT)
        self.waiter.sleep(0.20)
        self.vision.driver.swipe(
            *self.GO_UP_ONE_START,
            *self.GO_UP_ONE_END,
            duration=self.GO_UP_ONE_DURATION,
        )
        self.waiter.sleep(0.65)
        self.context.log(
            "AUTO trồng • đã lên đúng mốc cây bằng AUTO PRO goUp(1)"
        )

    def _count_changed_pots(self, before, after) -> int:
        """Require visible pot changes; sending a swipe alone is never PASS."""
        centers = (
            (335, 940), (490, 940), (578, 940), (645, 940), (720, 940), (835, 940),
            (835, 725), (665, 725), (595, 725), (505, 725), (430, 725), (335, 725),
            (335, 505), (490, 505), (578, 505), (645, 505), (720, 505), (835, 505),
            (835, 280), (665, 280), (595, 280), (505, 280), (430, 280), (335, 280),
            (335, 40), (490, 40), (578, 40),
        )
        height, width = before.shape[:2]
        changed = 0
        for x, y in centers:
            x0, x1 = max(0, x - 24), min(width, x + 24)
            y0, y1 = max(0, y - 24), min(height, y + 24)
            old = before[y0:y1, x0:x1].astype("int16")
            new = after[y0:y1, x0:x1].astype("int16")
            if old.shape == new.shape and old.size:
                difference = float(abs(new - old).mean())
                if difference >= 8.0:
                    changed += 1
        return changed

    def _scan_first_pot_state(self) -> tuple[str, object | None]:
        self.context.ensure_running()
        self.vision.driver.click(*self.OPEN_PLANT_POINT)
        self.waiter.sleep(0.45)
        frame = self.vision.frame()
        harvest = self.vision.find(
            "harvestBasket", threshold=0.80, zone=self.HARVEST_ZONE,
            scales=(0.80, 0.90, 1.00, 1.10, 1.20), frame=frame,
        )
        empty = self.vision.find(
            "next_gieo_trai", threshold=0.70, zone=self.EMPTY_READY_ZONE,
            scales=(0.80, 0.90, 1.00, 1.10, 1.20), frame=frame,
        )
        if harvest is not None:
            return "RIPE", harvest
        if empty is not None:
            return "EMPTY", empty
        return "UNKNOWN", None

    def _harvest_27(self) -> None:
        self.context.log(
            "AUTO trồng • phát hiện cây chín • thu hoạch 27 chậu trước khi gieo"
        )
        self.vision.driver.swipe_points(
            self.rose_path(), duration=self.SWIPE_DURATION
        )
        self.waiter.sleep(0.50)

    def _open_seed_picker(self):
        self._go_up_one()
        baseline = self.vision.frame()
        for attempt in range(1, 6):
            state, _match = self._scan_first_pot_state()
            if state == "EMPTY":
                self.context.log(
                    f"AUTO trồng • chậu trống và bảng hạt READY • lần {attempt}/5"
                )
                return baseline
            if state == "RIPE":
                self._harvest_27()
                continue
            self.context.log(
                f"AUTO trồng • chưa xác định cây chín/chậu trống • lần {attempt}/5"
            )
            self.vision.driver.click(*self.CLOSE_POINT)
            self.waiter.sleep(0.30)
        raise ScreenTimeout(
            "Không xác minh được cây chín hoặc chậu trống tại tầng gieo"
        )

    def plant_27_roses(self) -> int:
        baseline = self._open_seed_picker()
        self.context.ensure_running()
        rose = self.vision.find(
            self.ROSE_TEMPLATE, threshold=0.87, zone=self.SEED_ZONE,
            scales=(0.80, 0.90, 1.00, 1.10, 1.20), click=False,
        )
        if rose is None:
            self.vision.driver.click(*self.CLOSE_POINT)
            raise ScreenTimeout("Không nhận diện được hạt Hoa hồng trong bảng gieo")
        path = (rose.center,) + self.rose_path()[1:]
        self.context.log(
            "AUTO trồng • chọn Hoa hồng • kéo 27 chậu từ tầng 1 đến 3 chậu tầng 5"
        )
        self.vision.driver.swipe_points(path, duration=self.SWIPE_DURATION)
        self.waiter.sleep(0.40)
        self.vision.driver.click(*self.CLOSE_POINT)
        self.waiter.sleep(0.55)
        after = self.vision.frame()
        changed = self._count_changed_pots(baseline, after)
        self.context.detail(
            f"AUTO rose planting verification | changed_pots={changed}/27 | minimum=20"
        )
        if changed < 20:
            raise ScreenTimeout(
                f"Swipe gieo chưa được xác minh: chỉ {changed}/27 vùng chậu thay đổi"
            )
        self.context.log(
            f"AUTO trồng • xác minh hình ảnh {changed}/27 vùng chậu đã thay đổi"
        )
        return self.TREE_COUNT
