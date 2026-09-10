from __future__ import annotations

from dataclasses import dataclass

from ..errors import ScreenTimeout
from .function_one_navigation import FunctionOneNavigationActions
from .function_one_pass_three_navigation import FunctionOnePassThreeNavigationActions
from .planting import PlantingActions


__all__ = ["FunctionTwoPlantingActions", "FunctionTwoPlantingResult"]
FILE_FUNCTIONS = (
    "Khoá riêng Function 2 ở native ClientJS 1000x1000",
    "Trồng/thu hoạch 30 Hoa hồng trên năm tầng đầu bằng một lượt kéo",
    "Tái sử dụng route Function 1: main goUp(1), floor1 goUp(4), goUp(1) tới tầng 6",
    "Sau Hồng tầng 6: goDown(1) + nhận diện/click XUỐNG để về main",
    "Từ main lên lại tầng 1 rồi trồng/thu hoạch 28 Cây tuyết qua năm tầng",
    "Sau Tuyết đi thẳng floor1 goUp(4) tới candidate tầng 5 để bàn giao TDHH",
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

    Rose:
      exact-main -> goUp(1) -> floor 1
      5 rows x 6 = 30
      floor1 -> goUp(4) -> floor5 -> goUp(1) -> floor6
      floor6 row = 5
      floor6 -> goDown(1) -> visual XUỐNG -> main

    Snow:
      exact-main -> goUp(1) -> floor 1
      4 rows x 6 + 1 row x 4 = 28
      floor1 -> goUp(4) -> candidate floor5

    The recipe receives candidate floor5 directly; it must not route through
    invented floor7/floor11 states.
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

    def __init__(
        self,
        *args,
        function_one_navigation: FunctionOneNavigationActions,
        pass_three_navigation: FunctionOnePassThreeNavigationActions,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.function_one_navigation = function_one_navigation
        self.pass_three_navigation = pass_three_navigation

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
        harvested = 0
        for attempt in range(1, 7):
            self.context.ensure_running()
            state, match = self._scan_first_pot_state(seed_template)
            if state == "RIPE" and match is not None:
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

        # HỒNG: exact-main -> floor1, then use the same proven Function-1
        # navigation composition as the 36-apple supply: goUp(1), goUp(4), goUp(1).
        self.function_one_navigation.main_to_floor_1()
        rose_harvest_30, rose_plant_30 = self._harvest_and_replant_current_view(
            seed_template=self.ROSE_TEMPLATE,
            item_label="Hoa hồng",
            path=self.PATH_30,
            count=30,
            segment_label="Hồng 5 tầng đầu",
        )
        self.function_one_navigation.floor_1_to_floor_6()
        rose_harvest_5, rose_plant_5 = self._harvest_and_replant_current_view(
            seed_template=self.ROSE_TEMPLATE,
            item_label="Hoa hồng",
            path=self.PATH_5,
            count=5,
            segment_label="Hồng tầng 6",
        )

        self.context.stage("auto-function-2-rose-return-main")
        self.pass_three_navigation.known_upper_floor_to_main_via_down_floor(
            "Function 2 Hồng tầng 6 → main"
        )

        # TUYẾT: always restart from exact-main -> floor1. Never continue upward
        # from the Rose floor6 camera and never invent a floor7 snow group.
        self.context.stage("auto-function-2-snow-start-from-main")
        self.function_one_navigation.main_to_floor_1()
        snow_harvest, snow_plant = self._harvest_and_replant_current_view(
            seed_template=self.SNOW_TEMPLATE,
            item_label="Cây tuyết",
            path=self.PATH_28,
            count=28,
            segment_label="Tuyết 4x6 + 1x4",
        )

        # Snow finishes with the same floor1 camera anchor. Go straight up(4)
        # to floor5 and hand that candidate directly to TDHH production.
        self.function_one_navigation.floor_1_to_floor_5()

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
            f"Hồng={roses_planted}/35 • Tuyết={snow_plant}/28 • candidate_floor=5"
        )
        return FunctionTwoPlantingResult(
            roses_planted=roses_planted,
            snow_planted=snow_plant,
            roses_harvested=roses_harvested,
            snow_harvested=snow_harvest,
            end_floor=5,
        )
