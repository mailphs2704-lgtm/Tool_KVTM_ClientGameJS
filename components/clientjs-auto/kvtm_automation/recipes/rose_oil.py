from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..actions.production import ProductionResult
from ..actions.rose_oil_production import RoseOilProductionActions
from ..errors import ScreenTimeout
from ..recovery import RecoveryManager

if TYPE_CHECKING:
    from ..automation import KVAutomation


__all__ = [
    "RoseOilMaterialResult",
    "RoseOilRecipe",
    "RoseOilRecipeResult",
]


@dataclass(frozen=True)
class RoseOilMaterialResult:
    roses_planted: int
    snow_planted: int
    roses_harvested: int
    snow_harvested: int
    end_floor: int


@dataclass(frozen=True)
class RoseOilRecipeResult:
    materials: RoseOilMaterialResult
    production: ProductionResult

    @property
    def rose_planted(self) -> int:
        return int(self.materials.roses_planted)

    @property
    def snow_planted(self) -> int:
        return int(self.materials.snow_planted)

    @property
    def queued_count(self) -> int:
        return int(self.production.queued_count)


class RoseOilRecipe:
    """Function-2 business recipe: 35 Hồng + 28 Tuyết -> produce 7 TDHH VP.

    Hồng and Tuyết are crop/material inputs handled by PlantingActions.
    TDHH (Tinh dầu hoa hồng) is a finished VP product handled by
    RoseOilProductionActions; it is never treated as a crop/planting action.
    Navigation Actions own camera primitives and all Function-2 recipes share
    the same RecoveryManager instance.
    """

    REQUIRED_COUNT = 7
    ROSE_REQUIRED = 35
    SNOW_REQUIRED = 28
    ROSE_FIRST_SEGMENT = 30
    ROSE_FINAL_SEGMENT = 5

    def __init__(
        self,
        automation: KVAutomation,
        *,
        recovery: RecoveryManager | None = None,
    ) -> None:
        self.auto = automation
        self.context = automation.context
        self.production = RoseOilProductionActions(
            automation.context,
            automation.vision,
            automation.wait,
            automation.speed_config,
        )
        self.recovery = recovery or RecoveryManager(
            automation,
            function_id="function_2",
        )
        if self.recovery.function_id != "function_2":
            raise ValueError(
                "RoseOilRecipe chỉ nhận RecoveryManager function_2"
            )
        self.recovery.register_navigation_routes(
            to_main_routes={5: self._floor_5_to_main},
            from_main_routes={5: self._main_to_floor_5},
        )

    def _require_count(self, count: int) -> None:
        if int(count) != self.REQUIRED_COUNT:
            raise ValueError(
                f"VP TDHH recipe hiện khóa đúng {self.REQUIRED_COUNT} sản phẩm; "
                f"requested={count}"
            )

    def _require_native_1000(self) -> None:
        frame = self.auto.vision.frame()
        height, width = frame.shape[:2]
        if (width, height) != (1000, 1000):
            raise ScreenTimeout(
                "Function 2 materials hiện khóa native 1000x1000; "
                f"capture={width}x{height}. Không chạy contract 500x500."
            )
        self.context.detail(
            "AUTO Function 2 materials | native=1000x1000 | resolution_gate=PASS"
        )

    def _main_to_floor_5(self, label: str) -> None:
        self.context.log(
            f"AUTO TDHH recovery route • {label} • MAIN → goUp(1) → goUp(4) → tầng 5"
        )
        self.auto.function_one_navigation.main_to_floor_1()
        self.auto.function_one_navigation.floor_1_to_floor_5()

    def _floor_5_to_main(self, label: str) -> None:
        self.context.log(
            f"AUTO TDHH recovery route • {label} • đóng panel → goDown(1) → click XUỐNG → MAIN"
        )
        self.auto.vision.driver.click(*RoseOilProductionActions.CLOSE_POINT)
        self.auto.wait.sleep(0.35)
        self.auto.function_one_pass_three_navigation.known_upper_floor_to_main_via_down_floor(
            "TDHH tầng 5 → MAIN"
        )

    def _prepare_materials(self) -> RoseOilMaterialResult:
        self._require_native_1000()
        planting = self.auto.planting
        nav = self.auto.function_one_navigation
        upper_nav = self.auto.function_one_pass_three_navigation

        self.context.stage("auto-recipe-rose-oil-rose-start")
        nav.main_to_floor_1()
        rose_first = planting.harvest_and_replant_current_view(
            seed_template=planting.ROSE_TEMPLATE,
            item_label="Hoa hồng",
            count=self.ROSE_FIRST_SEGMENT,
            segment_label="Hồng 30 chậu đầu",
        )
        nav.floor_1_to_floor_6()
        rose_final = planting.harvest_and_replant_current_view(
            seed_template=planting.ROSE_TEMPLATE,
            item_label="Hoa hồng",
            count=self.ROSE_FINAL_SEGMENT,
            segment_label="Hồng 5 chậu tầng 6",
        )

        roses_planted = int(rose_first.planted_count + rose_final.planted_count)
        roses_harvested = int(
            rose_first.harvested_count + rose_final.harvested_count
        )
        if roses_planted != self.ROSE_REQUIRED:
            raise RuntimeError(
                f"TDHH Hồng contract FAIL: {roses_planted}/{self.ROSE_REQUIRED}"
            )

        self.context.stage("auto-recipe-rose-oil-rose-return-main")
        upper_nav.known_upper_floor_to_main_via_down_floor(
            "Function 2 Hồng tầng 6 → MAIN"
        )
        if not self.auto.popup.is_own_exact_main_screen():
            raise ScreenTimeout(
                "Hồng 35/35 đã xong nhưng chưa chứng minh MAIN trước Tuyết"
            )

        self.context.stage("auto-recipe-rose-oil-snow-start")
        nav.main_to_floor_1()
        snow = planting.harvest_and_replant_current_view(
            seed_template=planting.SNOW_TEMPLATE,
            item_label="Cây tuyết",
            count=self.SNOW_REQUIRED,
            segment_label="Tuyết 28 chậu",
        )
        if int(snow.planted_count) != self.SNOW_REQUIRED:
            raise RuntimeError(
                f"TDHH Tuyết contract FAIL: {snow.planted_count}/{self.SNOW_REQUIRED}"
            )
        nav.floor_1_to_floor_5()

        self.context.stage("auto-recipe-rose-oil-materials-pass")
        self.context.log(
            "AUTO recipe TDHH nguyên liệu cây • PASS • Hồng=35 • Tuyết=28 • candidate_floor=5"
        )
        return RoseOilMaterialResult(
            roses_planted=roses_planted,
            snow_planted=int(snow.planted_count),
            roses_harvested=roses_harvested,
            snow_harvested=int(snow.harvested_count),
            end_floor=5,
        )

    def run_from_main(self, *, count: int = 7) -> RoseOilRecipeResult:
        self._require_count(count)
        self.recovery.ensure_main("TDHH recipe: entry MAIN")
        self.context.stage("auto-recipe-rose-oil-materials")

        materials = self._prepare_materials()
        if (
            int(materials.roses_planted) != self.ROSE_REQUIRED
            or int(materials.snow_planted) != self.SNOW_REQUIRED
            or int(materials.end_floor) != 5
        ):
            raise RuntimeError(
                "TDHH material contract FAIL: "
                f"rose={materials.roses_planted}/{self.ROSE_REQUIRED}, "
                f"snow={materials.snow_planted}/{self.SNOW_REQUIRED}, "
                f"end_floor={materials.end_floor}/5"
            )

        self.context.ensure_running()
        self.context.stage("auto-recipe-rose-oil-vp-production")
        produced = self.recovery.run_production(
            floor=5,
            label="Tinh dầu hoa hồng",
            producer=lambda: self.production.produce_7_rose_oils(
                close_after_success=False
            ),
        )
        self.context.ensure_running()
        self.auto.machine_repair.repair_after_production(produced)
        self.context.ensure_running()

        self.recovery.to_main_from_floor(5, "TDHH recipe: cuối production")
        self.context.stage("auto-recipe-rose-oil-pass")
        self.context.log(
            "AUTO recipe TDHH • PASS • nguyên liệu Hồng=35 + Tuyết=28 • SX VP TDHH=7/7 • Sửa máy"
        )
        return RoseOilRecipeResult(
            materials=materials,
            production=produced,
        )
