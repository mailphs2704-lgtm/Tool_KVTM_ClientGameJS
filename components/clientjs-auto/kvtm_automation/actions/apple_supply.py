from __future__ import annotations

import time

from ..context import AutomationContext
from ..errors import ScreenTimeout
from ..runtime.auto_speed_config import AutoSpeedConfig
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter

__all__ = ["AppleSupplyActions"]
FILE_FUNCTIONS = (
    "Phân loại chậu trống, cây chín và cây chưa chín",
    "Kiểm tra lại trạng thái cây theo chu kỳ cấu hình mặc định 0.3 giây",
    "Thu hoạch và gieo lại đủ năm hàng, ba mươi cây Táo",
    "Tại tầng 6 gieo ngay nếu trống; chỉ chờ nếu đang có cây chưa chín",
)

class AppleSupplyActions:
    APPLE_TEMPLATE = "cay_tao"
    HARVEST_TEMPLATE = "thu_hoach"
    EMPTY_TEMPLATE = "next_gieo_trai"
    OPEN_POT = (388, 946)
    CLOSE_PANEL = (965, 198)
    HARVEST_ZONE = (222, 703, 218, 191)
    EMPTY_ZONE = (124, 729, 347, 236)
    SEED_ZONE = (179, 773, 230, 166)
    FIVE_FLOOR_PATH = (
        (325, 799), (335, 940), (835, 940), (835, 725), (335, 725),
        (335, 505), (835, 505), (835, 280), (335, 280),
        (335, 40), (835, 40),
    )
    FLOOR_6_ROW = ((325, 799), (335, 940), (835, 940))
    RIPE_TIMEOUT = 120.0

    def __init__(self, context: AutomationContext, vision: VisionEngine,
                 waiter: Waiter, speed_config: AutoSpeedConfig | None = None) -> None:
        self.context = context
        self.vision = vision
        self.waiter = waiter
        self.speed_config = speed_config or AutoSpeedConfig()

    def _scan_state(self) -> tuple[str, object | None]:
        self.context.ensure_running()
        self.vision.driver.click(*self.OPEN_POT)
        self.waiter.sleep(0.12)
        frame = self.vision.frame()
        ripe = self.vision.find(
            self.HARVEST_TEMPLATE, threshold=0.80, zone=self.HARVEST_ZONE,
            scales=(0.80, 0.90, 1.00, 1.10, 1.20), frame=frame,
        )
        empty = self.vision.find(
            self.EMPTY_TEMPLATE, threshold=0.70, zone=self.EMPTY_ZONE,
            scales=(0.80, 0.90, 1.00, 1.10, 1.20), frame=frame,
        )
        seed = self.vision.find(
            self.APPLE_TEMPLATE, threshold=0.87, zone=self.SEED_ZONE,
            scales=(0.80, 0.90, 1.00, 1.10, 1.20), frame=frame,
        )
        if ripe is not None:
            return "RIPE", ripe
        if empty is not None and seed is not None:
            return "EMPTY", seed
        self.vision.driver.click(*self.CLOSE_PANEL)
        return "GROWING", None

    def _wait_state(self, *, allow_empty: bool, label: str) -> tuple[str, object | None]:
        deadline = time.monotonic() + self.RIPE_TIMEOUT
        attempt = 0
        while time.monotonic() < deadline:
            attempt += 1
            state, match = self._scan_state()
            if state == "RIPE" or (allow_empty and state == "EMPTY"):
                self.context.log(
                    f"AUTO nguyên liệu • {label}={state} • kiểm tra {attempt} • "
                    f"chu kỳ={self.speed_config.crop_check_interval:.3f}s"
                )
                return state, match
            self.context.log(
                f"AUTO nguyên liệu • {label} chưa chín • kiểm tra lại sau "
                f"{self.speed_config.crop_check_interval:.3f}s"
            )
            self.waiter.sleep(self.speed_config.crop_check_interval)
        raise ScreenTimeout(f"Hết {self.RIPE_TIMEOUT:.0f}s chờ cây Táo {label} chín")

    def _plant_open_panel(self, seed, farm_path, count: int, label: str) -> int:
        self.context.ensure_running()
        self.vision.driver.swipe_points(
            (seed.center,) + tuple(farm_path[1:]),
            duration=self.speed_config.plant_harvest_duration,
        )
        self.waiter.sleep(0.45)
        self.vision.driver.click(*self.CLOSE_PANEL)
        self.waiter.sleep(0.55)
        self.context.log(f"AUTO nguyên liệu • đã gieo {label}")
        return count

    def wait_until_floor_1_ripe(self) -> None:
        self._wait_state(allow_empty=False, label="tầng 1")

    def harvest_and_replant_five_floors(self) -> int:
        self.vision.driver.swipe_points(
            self.FIVE_FLOOR_PATH, duration=self.speed_config.plant_harvest_duration
        )
        self.waiter.sleep(0.55)
        state, seed = self._wait_state(allow_empty=True, label="5 tầng sau thu hoạch")
        if state != "EMPTY" or seed is None:
            raise ScreenTimeout("Thu hoạch 5 tầng chưa chuyển thành chậu trống")
        return self._plant_open_panel(seed, self.FIVE_FLOOR_PATH, 30, "5 tầng x 6 Táo")

    def harvest_and_replant_floor_6_row(self) -> int:
        state, match = self._wait_state(allow_empty=True, label="hàng dưới cùng tầng 6")
        if state == "EMPTY":
            self.context.log("AUTO nguyên liệu • tầng 6 đang trống • gieo Táo ngay")
            return self._plant_open_panel(match, self.FLOOR_6_ROW, 6, "hàng tầng 6 x 6 Táo")
        self.vision.driver.swipe_points(
            self.FLOOR_6_ROW, duration=self.speed_config.plant_harvest_duration
        )
        self.waiter.sleep(0.55)
        state, seed = self._wait_state(allow_empty=True, label="hàng tầng 6 sau thu hoạch")
        if state != "EMPTY" or seed is None:
            raise ScreenTimeout("Thu hoạch tầng 6 chưa chuyển thành chậu trống")
        return self._plant_open_panel(seed, self.FLOOR_6_ROW, 6, "hàng tầng 6 x 6 Táo")
