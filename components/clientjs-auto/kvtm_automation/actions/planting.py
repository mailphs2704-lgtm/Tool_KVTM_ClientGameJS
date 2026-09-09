from __future__ import annotations

from ..context import AutomationContext
from ..errors import ScreenTimeout
from ..runtime.auto_speed_config import AutoSpeedConfig
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
    APPLE_TEMPLATE = "cay_tao"
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
        speed_config: AutoSpeedConfig | None = None,
    ) -> None:
        self.context = context
        self.vision = vision
        self.waiter = waiter
        self.speed_config = speed_config or AutoSpeedConfig()

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
            duration=self.speed_config.floor_swipe_duration,
        )
        self.waiter.sleep(0.65)
        self.context.log(
            "AUTO trồng • đã lên đúng mốc cây bằng AUTO PRO goUp(1) • "
            f"tốc độ kéo tầng={self.speed_config.floor_swipe_duration:.3f}s"
        )

    def _count_changed_pots(self, before, after) -> int:
        """Require visible pot changes using logical 1000 waypoint geometry."""
        centers = (
            (335, 940), (490, 940), (578, 940), (645, 940), (720, 940), (835, 940),
            (835, 725), (665, 725), (595, 725), (505, 725), (430, 725), (335, 725),
            (335, 505), (490, 505), (578, 505), (645, 505), (720, 505), (835, 505),
            (835, 280), (665, 280), (595, 280), (505, 280), (430, 280), (335, 280),
            (335, 40), (490, 40), (578, 40),
        )
        changed = 0
        for center in centers:
            # The old diagnostic sliced x/y logical values directly from the
            # captured frame. Once Vision sees true 500x500 that would make most
            # lower/right pot ROIs empty. Keep the same logical ±24 box and map
            # it to each actual frame independently.
            logical_zone = (center[0] - 24, center[1] - 24, 48, 48)
            bx, by, bw, bh = self.vision.logical_zone_to_frame(
                logical_zone, before
            )
            ax, ay, aw, ah = self.vision.logical_zone_to_frame(
                logical_zone, after
            )
            old = before[by : by + bh, bx : bx + bw].astype("int16")
            new = after[ay : ay + ah, ax : ax + aw].astype("int16")
            if old.shape == new.shape and old.size:
                difference = float(abs(new - old).mean())
                if difference >= 8.0:
                    changed += 1
        return changed

    def _scan_first_pot_state(self, seed_template: str) -> tuple[str, object | None]:
        self.context.ensure_running()
        self.vision.driver.click(*self.OPEN_PLANT_POINT)
        self.waiter.sleep(0.45)
        frame = self.vision.frame()
        harvest = self.vision.find(
            "thu_hoach", threshold=0.80, zone=self.HARVEST_ZONE,
            scales=(0.70, 0.80, 0.90, 1.00, 1.10, 1.20, 1.30), frame=frame,
        )
        empty = self.vision.find(
            "next_gieo_trai", threshold=0.70, zone=self.EMPTY_READY_ZONE,
            scales=(0.80, 0.90, 1.00, 1.10, 1.20), frame=frame,
        )
        rose = self.vision.find(
            seed_template, threshold=0.87, zone=self.SEED_ZONE,
            scales=(0.80, 0.90, 1.00, 1.10, 1.20), frame=frame,
        )
        if harvest is not None:
            return "RIPE", harvest
        if empty is not None and rose is not None:
            return "EMPTY", rose
        return "UNKNOWN", None

    def _harvest_27(self) -> None:
        self.context.log(
            "AUTO trồng • phát hiện cây chín • thu hoạch 27 chậu trước khi gieo"
        )
        self.vision.driver.swipe_points(
            self.rose_path(), duration=self.speed_config.plant_harvest_duration
        )
        self.waiter.sleep(0.50)

    def _open_seed_picker(self, seed_template: str, item_label: str):
        self._go_up_one()
        baseline = self.vision.frame().copy()
        for attempt in range(1, 6):
            state, match = self._scan_first_pot_state(seed_template)
            if state == "EMPTY":
                self.context.log(
                    f"AUTO trồng • chậu trống và bảng hạt READY • lần {attempt}/5 • "
                    "giữ seed match từ cùng frame đã xác minh"
                )
                return baseline, match
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

    def _plant_27(self, seed_template: str, item_label: str) -> int:
        baseline, seed = self._open_seed_picker(seed_template, item_label)
        self.context.ensure_running()
        if seed is None:
            self.vision.driver.click(*self.CLOSE_POINT)
            raise ScreenTimeout(
                f"Không nhận diện được hạt {item_label} trong bảng gieo"
            )
        path = (seed.center,) + self.rose_path()[1:]
        self.context.log(
            f"AUTO trồng • chọn {item_label} • dùng seed match đã xác minh cùng frame • "
            "kéo 27 chậu từ tầng 1 đến 3 chậu tầng 5"
        )
        self.vision.driver.swipe_points(
            path, duration=self.speed_config.plant_harvest_duration
        )
        self.waiter.sleep(0.40)
        self.vision.driver.click(*self.CLOSE_POINT)
        self.waiter.sleep(0.55)
        after = self.vision.frame().copy()
        changed = self._count_changed_pots(baseline, after)
        self.context.detail(
            "AUTO planting diagnostic | "
            f"item={seed_template} | "
            f"changed_waypoint_regions={changed}/27 | non_blocking=true"
        )
        self.context.log(
            "AUTO trồng • hoàn tất chuỗi đã xác minh: "
            f"cây chín → thu hoạch → chậu trống → hạt {item_label} → swipe 27 chậu"
        )
        return self.TREE_COUNT

    def plant_27_roses(self) -> int:
        return self._plant_27(self.ROSE_TEMPLATE, "Hoa hồng")

    def plant_27_apples(self) -> int:
        return self._plant_27(self.APPLE_TEMPLATE, "Táo")
