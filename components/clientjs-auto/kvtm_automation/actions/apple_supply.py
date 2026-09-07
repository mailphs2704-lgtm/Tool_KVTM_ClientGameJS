from __future__ import annotations

import time

from ..context import AutomationContext
from ..errors import ScreenTimeout
from ..runtime.auto_speed_config import AutoSpeedConfig
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter


__all__ = ["AppleSupplyActions"]
FILE_FUNCTIONS = (
    "Chờ cây Táo tầng 1 chín bằng template thu_hoach",
    "Thu hoạch và gieo lại đủ năm hàng, ba mươi cây Táo",
    "Thu hoạch và gieo lại đúng hàng dưới cùng tại tầng 6",
    "Không xác nhận hoàn thành nếu chưa thấy trạng thái cây chín và hạt Táo",
)


class AppleSupplyActions:
    """Prepare the 36 apples required by nine apple-juice transactions."""

    APPLE_TEMPLATE = "cay_tao"
    HARVEST_TEMPLATE = "thu_hoach"
    OPEN_POT = (388, 946)
    CLOSE_PANEL = (965, 198)
    HARVEST_ZONE = (222, 703, 218, 191)
    SEED_ZONE = (179, 773, 230, 166)
    FIVE_FLOOR_PATH = (
        (325, 799), (335, 940), (835, 940), (835, 725), (335, 725),
        (335, 505), (835, 505), (835, 280), (335, 280),
        (335, 40), (835, 40),
    )
    FLOOR_6_ROW = ((325, 799), (335, 940), (835, 940))

    def __init__(self, context: AutomationContext, vision: VisionEngine,
                 waiter: Waiter, speed_config: AutoSpeedConfig | None = None) -> None:
        self.context = context
        self.vision = vision
        self.waiter = waiter
        self.speed_config = speed_config or AutoSpeedConfig()

    def _open_and_find(self, template: str, zone, threshold: float):
        self.context.ensure_running()
        self.vision.driver.click(*self.OPEN_POT)
        self.waiter.sleep(0.45)
        return self.vision.find(
            template, threshold=threshold, zone=zone,
            scales=(0.80, 0.90, 1.00, 1.10, 1.20), click=False,
        )

    def wait_until_floor_1_ripe(self, timeout: float = 14400.0,
                                poll_seconds: float = 20.0) -> None:
        deadline = time.monotonic() + timeout
        attempt = 0
        while time.monotonic() < deadline:
            attempt += 1
            ripe = self._open_and_find(
                self.HARVEST_TEMPLATE, self.HARVEST_ZONE, 0.80
            )
            if ripe is not None:
                self.context.log(
                    f"AUTO nguyên liệu • cây Táo tầng 1 đã chín • lần kiểm tra {attempt}"
                )
                return
            self.vision.driver.click(*self.CLOSE_PANEL)
            remaining = max(0, int(deadline - time.monotonic()))
            self.context.log(
                "AUTO nguyên liệu • Táo tầng 1 chưa chín • "
                f"kiểm tra lại sau {poll_seconds:.0f}s • còn tối đa {remaining}s"
            )
            self.waiter.sleep(poll_seconds)
        raise ScreenTimeout("Hết thời gian chờ cây Táo tầng 1 chín")

    def _harvest_then_plant(self, farm_path, count: int, label: str) -> int:
        self.context.ensure_running()
        self.vision.driver.swipe_points(
            farm_path, duration=self.speed_config.plant_harvest_duration
        )
        self.waiter.sleep(0.55)
        seed = self._open_and_find(self.APPLE_TEMPLATE, self.SEED_ZONE, 0.87)
        if seed is None:
            self.vision.driver.click(*self.CLOSE_PANEL)
            raise ScreenTimeout(f"Không thấy hạt Táo sau khi thu hoạch {label}")
        self.vision.driver.swipe_points(
            (seed.center,) + tuple(farm_path[1:]),
            duration=self.speed_config.plant_harvest_duration,
        )
        self.waiter.sleep(0.45)
        self.vision.driver.click(*self.CLOSE_PANEL)
        self.waiter.sleep(0.55)
        self.context.log(f"AUTO nguyên liệu • đã thu hoạch và gieo lại {label}")
        return count

    def harvest_and_replant_five_floors(self) -> int:
        return self._harvest_then_plant(self.FIVE_FLOOR_PATH, 30, "5 tầng x 6 Táo")

    def harvest_and_replant_floor_6_row(self) -> int:
        ripe = self._open_and_find(
            self.HARVEST_TEMPLATE, self.HARVEST_ZONE, 0.80
        )
        if ripe is None:
            self.vision.driver.click(*self.CLOSE_PANEL)
            raise ScreenTimeout(
                "Tầng 6: hàng dưới cùng chưa xác minh được trạng thái cây chín"
            )
        return self._harvest_then_plant(self.FLOOR_6_ROW, 6, "hàng tầng 6 x 6 Táo")
