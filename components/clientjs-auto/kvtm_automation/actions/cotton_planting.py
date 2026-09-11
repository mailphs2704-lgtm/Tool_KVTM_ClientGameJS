from __future__ import annotations

from ..errors import ScreenTimeout
from .planting import PlantingActions


__all__ = ["CottonPlantingActions"]
FILE_FUNCTIONS = (
    "Xác minh template Bông trước gesture",
    "Dùng PlantingActions PATH_27 dùng chung",
    "Chỉ trồng/thu hoạch Bông trên view hiện tại; không tự điều hướng tầng",
    "Recipe chịu trách nhiệm goUp/goDown trước và sau Action",
)


class CottonPlantingActions(PlantingActions):
    """Current-view Bông adapter over the generic 27-pot planting Action."""

    COTTON_TEMPLATE = "cay_bong"

    def plant_27_cotton(self) -> int:
        """Plant/harvest 27 cotton pots on the camera view supplied by caller."""
        if not self.vision.assets.has(self.COTTON_TEMPLATE):
            raise ScreenTimeout(
                "Thiếu template clean cay_bong; dừng trước mọi gesture gieo Bông"
            )
        result = self.harvest_and_replant_current_view(
            seed_template=self.COTTON_TEMPLATE,
            item_label="Bông",
            count=27,
            segment_label="Bông 27 chậu",
        )
        return int(result.planted_count)
