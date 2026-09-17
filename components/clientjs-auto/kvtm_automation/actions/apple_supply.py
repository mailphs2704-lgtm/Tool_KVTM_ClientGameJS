from __future__ import annotations

import time

from ..errors import ScreenTimeout
from .planting import PlantingActions


__all__ = ["AppleSupplyActions"]
FILE_FUNCTIONS = (
    "Phân loại chậu trống, cây chín và cây chưa chín",
    "Kiểm tra lại trạng thái cây theo chu kỳ cấu hình mặc định 0.3 giây",
    "Tái sử dụng PlantingActions.PATH_30 cho batch Táo 5 tầng, không giữ geometry 30 riêng",
    "Tái sử dụng PlantingActions.PATH_6 cho hàng 6 chậu tầng 6",
    "Thu hoạch và gieo lại đủ năm hàng, ba mươi cây Táo",
    "Tại tầng 6 gieo ngay nếu trống; chỉ chờ nếu đang có cây chưa chín",
    "Không sở hữu điều hướng tầng; caller/Recipe quyết định floor route",
)


class AppleSupplyActions(PlantingActions):
    """Apple crop/supply Actions on the camera view supplied by the caller.

    This class owns the crop-specific READY/GROWING wait semantics that were
    already proven for Function 1 material supply. Shared farm geometry comes
    from PlantingActions; navigation remains outside this Action.
    """

    APPLE_TEMPLATE = PlantingActions.APPLE_TEMPLATE
    HARVEST_TEMPLATE = "thu_hoach"
    EMPTY_TEMPLATE = "next_gieo_trai"
    OPEN_POT = PlantingActions.OPEN_PLANT_POINT
    CLOSE_PANEL = PlantingActions.CLOSE_POINT
    HARVEST_ZONE = PlantingActions.HARVEST_ZONE
    EMPTY_ZONE = PlantingActions.EMPTY_READY_ZONE
    SEED_ZONE = PlantingActions.SEED_ZONE

    FIVE_FLOOR_PATH = PlantingActions.PATH_30
    FLOOR_6_ROW = PlantingActions.PATH_6
    RIPE_TIMEOUT = 120.0

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
        if empty is not None:
            return "EMPTY", seed
        self.vision.driver.click(*self.CLOSE_PANEL)
        return "GROWING", None

    def _wait_state(
        self,
        *,
        allow_empty: bool,
        label: str,
        accept_ripe: bool = True,
    ) -> tuple[str, object | None]:
        deadline = time.monotonic() + self.RIPE_TIMEOUT
        attempt = 0
        while time.monotonic() < deadline:
            attempt += 1
            state, match = self._scan_state()
            if (accept_ripe and state == "RIPE") or (
                allow_empty and state == "EMPTY"
            ):
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
        raise ScreenTimeout(
            f"Hết {self.RIPE_TIMEOUT:.0f}s chờ cây Táo {label} chín"
        )

    def _plant_open_panel(self, seed, farm_path, count: int, label: str) -> int:
        self.context.ensure_running()
        seed = self._find_seed_in_open_picker(
            self.APPLE_TEMPLATE,
            "Táo",
            first_match=seed,
        )
        self.vision.driver.swipe_points(
            (seed.center,) + tuple(farm_path[1:]),
            duration=self.speed_config.plant_harvest_duration,
        )
        self.waiter.sleep(0.45)
        self.close_seed_picker_verified(label=label)
        self.waiter.sleep(0.25)
        self.context.log(f"AUTO nguyên liệu • đã gieo {label}")
        return count

    def wait_until_floor_1_ripe(self) -> None:
        self._wait_state(allow_empty=False, label="tầng 1")

    def harvest_or_replant_five_floors(self) -> int:
        """Plant 30 apples from the current floor-1 view, harvesting only if ripe."""
        state, match = self._wait_state(
            allow_empty=True,
            label="5 tầng Function 3 Step 1",
        )
        if state == "EMPTY":
            self.context.log(
                "AUTO Function 3 Step 1 • chậu đầu đang trống • mở bảng gieo trực tiếp"
            )
            return self._plant_open_panel(
                match,
                self.FIVE_FLOOR_PATH,
                30,
                "Function 3 Step 1 • 5 tầng x 6 Táo",
            )

        self.context.log(
            "AUTO Function 3 Step 1 • cây Táo đã chín • thu hoạch 5 tầng / 30 chậu"
        )
        self.vision.driver.swipe_points(
            self.FIVE_FLOOR_PATH,
            duration=self.speed_config.plant_harvest_duration,
        )
        self.waiter.sleep(0.55)
        state, seed = self._wait_state(
            allow_empty=True,
            accept_ripe=False,
            label="Function 3 Step 1 • 5 tầng sau thu hoạch",
        )
        if state != "EMPTY" or seed is None:
            raise ScreenTimeout(
                "Function 3 Step 1: thu hoạch 5 tầng chưa chuyển thành chậu trống"
            )
        return self._plant_open_panel(
            seed,
            self.FIVE_FLOOR_PATH,
            30,
            "Function 3 Step 1 • 5 tầng x 6 Táo",
        )

    def harvest_and_replant_five_floors(self) -> int:
        self.vision.driver.swipe_points(
            self.FIVE_FLOOR_PATH,
            duration=self.speed_config.plant_harvest_duration,
        )
        self.waiter.sleep(0.55)
        state, seed = self._wait_state(
            allow_empty=True,
            accept_ripe=False,
            label="5 tầng sau thu hoạch",
        )
        if state != "EMPTY" or seed is None:
            raise ScreenTimeout("Thu hoạch 5 tầng chưa chuyển thành chậu trống")
        return self._plant_open_panel(
            seed,
            self.FIVE_FLOOR_PATH,
            30,
            "5 tầng x 6 Táo",
        )

    def harvest_and_replant_floor_6_row(self) -> int:
        state, match = self._wait_state(
            allow_empty=True,
            label="hàng dưới cùng tầng 6",
        )
        if state == "EMPTY":
            self.context.log("AUTO nguyên liệu • tầng 6 đang trống • gieo Táo ngay")
            return self._plant_open_panel(
                match,
                self.FLOOR_6_ROW,
                6,
                "hàng tầng 6 x 6 Táo",
            )
        self.vision.driver.swipe_points(
            self.FLOOR_6_ROW,
            duration=self.speed_config.plant_harvest_duration,
        )
        self.waiter.sleep(0.55)
        state, seed = self._wait_state(
            allow_empty=True,
            accept_ripe=False,
            label="hàng tầng 6 sau thu hoạch",
        )
        if state != "EMPTY" or seed is None:
            raise ScreenTimeout("Thu hoạch tầng 6 chưa chuyển thành chậu trống")
        return self._plant_open_panel(
            seed,
            self.FLOOR_6_ROW,
            6,
            "hàng tầng 6 x 6 Táo",
        )
