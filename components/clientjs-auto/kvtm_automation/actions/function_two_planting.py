from __future__ import annotations

from dataclasses import dataclass

from .planting import PlantingActions


__all__ = ["FunctionTwoPlantingActions", "FunctionTwoPlantingResult"]
FILE_FUNCTIONS = (
    "LEGACY compatibility facade only; không còn sở hữu Function 2 choreography",
    "Geometry 5/28/30 được lấy trực tiếp từ PlantingActions dùng chung",
    "Runtime chuẩn mới dùng RoseOilRecipe để ghép Navigation + Planting + Production",
    "Từ chối chạy harvest_and_replant_materials cũ để tránh hai nguồn business logic",
)


@dataclass(frozen=True)
class FunctionTwoPlantingResult:
    """Historical result shape retained for import compatibility only."""

    roses_planted: int
    snow_planted: int
    roses_harvested: int
    snow_harvested: int
    end_floor: int


class FunctionTwoPlantingActions(PlantingActions):
    """Deprecated compatibility facade.

    Function 2 material order used to live in this Action, mixing business flow,
    navigation and crop gestures. The authoritative implementation now lives in
    ``recipes.rose_oil.RoseOilRecipe``. This facade keeps old imports/constants
    readable while preventing new runtime code from creating a second copy of
    the choreography.
    """

    ROSE_COUNT = 35
    SNOW_COUNT = 28
    SNOW_TEMPLATE = PlantingActions.SNOW_TEMPLATE
    PATH_30 = PlantingActions.PATH_30
    PATH_5 = PlantingActions.PATH_5
    PATH_28 = PlantingActions.PATH_28

    def harvest_and_replant_materials(self) -> FunctionTwoPlantingResult:
        raise RuntimeError(
            "FunctionTwoPlantingActions đã retired khỏi runtime chuẩn. "
            "Dùng RoseOilRecipe: Recipe ghép Navigation + PlantingActions dùng chung."
        )
