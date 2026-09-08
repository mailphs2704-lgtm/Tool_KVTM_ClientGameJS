from __future__ import annotations

from ..errors import ScreenTimeout
from .planting import PlantingActions


__all__ = ["CottonPlantingActions"]
FILE_FUNCTIONS = (
    "Xác minh template bông tồn tại trong clean asset library trước gesture",
    "Tái sử dụng đường gieo 27 chậu đã dùng ở hai pass trước",
    "Hậu kiểm đủ 27 vùng chậu thay đổi; thiếu bất kỳ chậu nào thì fail-close",
)


class CottonPlantingActions(PlantingActions):
    """Plant exactly 27 cotton plants through the proven clean planting path."""

    COTTON_TEMPLATE = "cay_bong"

    def plant_27_cotton(self) -> int:
        if not self.vision.assets.has(self.COTTON_TEMPLATE):
            raise ScreenTimeout(
                "Thiếu template clean cay_bong; dừng trước mọi gesture gieo Bông"
            )

        baseline = self._open_seed_picker(self.COTTON_TEMPLATE, "Bông")
        self.context.ensure_running()
        seed = self.vision.find(
            self.COTTON_TEMPLATE,
            threshold=0.87,
            zone=self.SEED_ZONE,
            scales=(0.80, 0.90, 1.00, 1.10, 1.20),
            click=False,
        )
        if seed is None:
            self.vision.driver.click(*self.CLOSE_POINT)
            raise ScreenTimeout(
                "Không nhận diện được hạt Bông trong bảng gieo; dừng fail-close"
            )

        path = (seed.center,) + self.rose_path()[1:]
        self.context.log(
            "AUTO trồng • chọn Bông • kéo 27 chậu "
            "từ tầng 1 đến 3 chậu tầng 5"
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
            "AUTO cotton planting diagnostic | "
            f"changed_waypoint_regions={changed}/27 | fail_close=true"
        )
        if changed != self.TREE_COUNT:
            raise ScreenTimeout(
                "Hậu kiểm gieo Bông không đạt đủ 27/27 vùng chậu: "
                f"xác minh={changed}/27; dừng fail-close"
            )

        self.context.log(
            "AUTO trồng Bông • hậu kiểm PASS • đã xác minh đủ 27/27 vùng chậu thay đổi"
        )
        return self.TREE_COUNT
