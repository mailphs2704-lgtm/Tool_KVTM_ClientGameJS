from __future__ import annotations

from ..errors import ScreenTimeout
from .planting import PlantingActions


__all__ = ["CottonPlantingActions"]
FILE_FUNCTIONS = (
    "Xác minh template bông tồn tại trong clean asset library trước gesture",
    "Tái sử dụng nguyên trạng đường gieo 27 chậu đã dùng ở hai pass trước",
)


class CottonPlantingActions(PlantingActions):
    """Plant exactly 27 cotton plants through the proven clean planting path."""

    COTTON_TEMPLATE = "cay_bong"

    def plant_27_cotton(self) -> int:
        if not self.vision.assets.has(self.COTTON_TEMPLATE):
            raise ScreenTimeout(
                "Thiếu template clean cay_bong; dừng trước mọi gesture gieo Bông"
            )
        return self._plant_27(self.COTTON_TEMPLATE, "Bông")
