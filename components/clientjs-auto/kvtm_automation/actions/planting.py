from __future__ import annotations

from ..context import AutomationContext
from ..errors import ScreenTimeout
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter


__all__ = ["PlantingActions"]
FILE_FUNCTIONS = (
    "Mở bảng chọn hạt giống từ chậu đầu tầng một",
    "Xác minh bảng gieo hoặc chặn khi chậu đang có cây chín",
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
    SEED_ZONE = (179, 773, 230, 166)
    LEFT_READY_ZONE = (124, 729, 347, 236)
    RIGHT_READY_ZONE = (363, 769, 121, 162)
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

    def _open_seed_picker(self):
        for attempt in range(1, 4):
            self.context.ensure_running()
            self.vision.driver.click(*self.OPEN_PLANT_POINT)
            self.waiter.sleep(0.45)
            left = self.vision.find(
                "next_gieo_trai", threshold=0.70,
                zone=self.LEFT_READY_ZONE,
                scales=(0.80, 0.90, 1.00, 1.10, 1.20),
            )
            right = self.vision.find(
                "next_gieo", threshold=0.70,
                zone=self.RIGHT_READY_ZONE,
                scales=(0.80, 0.90, 1.00, 1.10, 1.20),
            )
            if left is not None or right is not None:
                self.context.log(
                    f"AUTO trồng • bảng hạt giống READY • lần {attempt}/3"
                )
                return
            harvest = self.vision.find(
                "harvestBasket", threshold=0.80,
                zone=(222, 703, 218, 191),
                scales=(0.80, 0.90, 1.00, 1.10, 1.20),
            )
            if harvest is not None:
                raise ScreenTimeout(
                    "Chậu đầu đang có cây chín; chưa trồng đè trong lượt thử Hoa hồng"
                )
        raise ScreenTimeout("Không mở được bảng chọn hạt giống tại chậu đầu tầng 1")

    def plant_27_roses(self) -> int:
        self._open_seed_picker()
        self.context.ensure_running()
        rose = self.vision.find(
            self.ROSE_TEMPLATE,
            threshold=0.87,
            zone=self.SEED_ZONE,
            scales=(0.80, 0.90, 1.00, 1.10, 1.20),
            click=False,
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
        self.waiter.sleep(0.30)
        self.context.log(
            "AUTO trồng • đã gửi đường gieo Hoa hồng 27/27 chậu • chờ LIVE xác minh"
        )
        return self.TREE_COUNT
