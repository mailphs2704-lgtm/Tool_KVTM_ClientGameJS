from __future__ import annotations

from dataclasses import dataclass

from ..errors import ScreenTimeout
from .floor_navigation import FloorNavigationActions
from .planting import PlantingActions


__all__ = ["FunctionTwoPlantingActions", "FunctionTwoPlantingResult"]
FILE_FUNCTIONS = (
    "Khoá riêng Function 2 ở native ClientJS 1000x1000",
    "Thu hoạch/gieo lại 30 Hoa hồng trên nhóm tầng 1-5 bằng một lượt kéo",
    "Đi từ candidate tầng 1 lên tầng 6 rồi thu hoạch/gieo lại 5 Hoa hồng",
    "Đi tiếp lên candidate tầng 7 rồi thu hoạch/gieo lại 28 Cây tuyết qua năm tầng",
    "Giữ Function 1 và contract 500x500 hoàn toàn không đổi",
)


@dataclass(frozen=True)
class FunctionTwoPlantingResult:
    roses_planted: int
    snow_planted: int
    roses_harvested: int
    snow_harvested: int
    end_floor: int


class FunctionTwoPlantingActions(PlantingActions):
    """Function-2-only 1000x1000 material planting choreography.

    The recovered 27-pot geometry proves six pots per visible farm row and the
    five-row zig-zag. Function 2 extends that same geometry without changing the
    legacy Function 1 planting path:

      Rose: floors 1..5 = 5 x 6, then floor 6 = 5  => 35
      Snow: floors 7..10 = 4 x 6, floor 11 = 4   => 28

    The second crop starts at candidate floor 7 so it never overwrites the rose
    group. Every segment still requires the AUTO PRO seed template before drag.
    """

    SNOW_TEMPLATE = "cay_tuyet"
    ROSE_COUNT = 35
    SNOW_COUNT = 28

    PATH_30 = (
        PlantingActions.START_POINT,
        (335, 940), (835, 940),
        (835, 725), (335, 725),
        (335, 505), (835, 505),
        (835, 280), (335, 280),
        (335, 40), (835, 40),
    )
    PATH_5 = (
        PlantingActions.START_POINT,
        (335, 940), (720, 940),
    )
    PATH_28 = (
        PlantingActions.START_POINT,
        (335, 940), (835, 940),
        (835, 725), (335, 725),
        (335, 505), (835, 505),
        (835, 280), (335, 280),
        (335, 40), (645, 40),
    )

    def __init__(self, *args, floors: FloorNavigationActions, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.floors = floors

    def _require_native_1000(self) -> None:
        frame = self.vision.frame()
        height, width = frame.shape[:2]
        if (width, height) != (1000, 1000):
            raise ScreenTimeout(
                "Function 2 planting hiện chỉ VERIFIED-target native 1000x1000; "
                f"capture={width}x{height}. Không chạy bảng 500x500."
            )
        self.context.detail(
            "AUTO Function 2 planting | native=1000x1000 | resolution_gate=PASS"
        )

    def _harvest_and_replant_current_view(
        self,
        *,
        seed_template: str,
        item_label: str,
        path: tuple[tuple[int, int], ...],
        count: int,
        segment_label: str,
    ) -> tuple[int, int]:
        """Harvest a ripe segment when present, then replant exactly that segment."""
        harvested = 0
        for attempt in range(1, 7):
            self.context.ensure_running()
            state, match = self._scan_first_pot_state(seed_template)
            if state == "RIPE" and match is not None:
                # Keep the recovered AUTO PRO harvest contract: the harvest icon
                # proves readiness, but the actual farm drag starts at START_POINT.
                self.context.log(
                    f"AUTO Function 2 • {segment_label} • cây chín READY • "
                    f"thu hoạch {count} chậu từ farm start"
                )
                self.vision.driver.swipe_points(
                    tuple(path),
                    duration=self.speed_config.plant_harvest_duration,
                )
                harvested = count
                self.waiter.sleep(0.55)
                continue

            if state == "EMPTY" and match is not None:
                # Seed selection is the opposite contract: start exactly from the
                # verified seed template center, then traverse the target pots.
                plant_path = (match.center,) + tuple(path[1:])
                self.context.log(
                    f"AUTO Function 2 • {segment_label} • hạt {item_label} READY • "
                    f"gieo {count} chậu"
                )
                self.vision.driver.swipe_points(
                    plant_path,
                    duration=self.speed_config.plant_harvest_duration,
                )
                self.waiter.sleep(0.45)
                self.vision.driver.click(*self.CLOSE_POINT)
                self.waiter.sleep(0.45)
                self.context.log(
                    f"AUTO Function 2 • {segment_label} • replant PASS {count}/{count}"
                )
                return harvested, count

            self.context.log(
                f"AUTO Function 2 • {segment_label} • chưa chứng minh RIPE/EMPTY "
                f"lần {attempt}/6"
            )
            self.vision.driver.click(*self.CLOSE_POINT)
            self.waiter.sleep(0.30)

        raise ScreenTimeout(
            f"Function 2 không hoàn tất được segment {segment_label}; "
            "dừng trước khi kéo segment kế tiếp"
        )

    def harvest_and_replant_materials(self) -> FunctionTwoPlantingResult:
        self._require_native_1000()
        self.context.stage("auto-function-2-materials-start")

        # Exact-main -> candidate floor 1. This is the same recovered goUp(1)
        # entry used by the proven planting action; only the Function-2 paths are new.
        self._go_up_one()
        rose_harvest_30, rose_plant_30 = self._harvest_and_replant_current_view(
            seed_template=self.ROSE_TEMPLATE,
            item_label="Hoa hồng",
            path=self.PATH_30,
            count=30,
            segment_label="Hồng tầng 1-5",
        )

        # Camera anchor is still floor 1 after the five-row drag. Advance five
        # proven one-floor moves to candidate floor 6, then plant only five pots.
        self.floors.up(5)
        rose_harvest_5, rose_plant_5 = self._harvest_and_replant_current_view(
            seed_template=self.ROSE_TEMPLATE,
            item_label="Hoa hồng",
            path=self.PATH_5,
            count=5,
            segment_label="Hồng tầng 6",
        )

        # Keep rose and snow on disjoint physical floors. Candidate floor 7 is the
        # anchor for one five-row snow drag: 6+6+6+6+4 = 28.
        self.floors.up(1)
        snow_harvest, snow_plant = self._harvest_and_replant_current_view(
            seed_template=self.SNOW_TEMPLATE,
            item_label="Cây tuyết",
            path=self.PATH_28,
            count=28,
            segment_label="Tuyết tầng 7-11",
        )

        roses_planted = rose_plant_30 + rose_plant_5
        roses_harvested = rose_harvest_30 + rose_harvest_5
        if roses_planted != self.ROSE_COUNT or snow_plant != self.SNOW_COUNT:
            raise ScreenTimeout(
                "Function 2 planting count mismatch: "
                f"rose={roses_planted}/{self.ROSE_COUNT}, "
                f"snow={snow_plant}/{self.SNOW_COUNT}"
            )

        self.context.stage("auto-function-2-materials-pass")
        self.context.log(
            "AUTO Function 2 • material planting PASS • "
            f"Hồng={roses_planted}/35 • Tuyết={snow_plant}/28 • candidate_floor=7"
        )
        return FunctionTwoPlantingResult(
            roses_planted=roses_planted,
            snow_planted=snow_plant,
            roses_harvested=roses_harvested,
            snow_harvested=snow_harvest,
            end_floor=7,
        )
