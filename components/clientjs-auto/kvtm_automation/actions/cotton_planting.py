from __future__ import annotations

import time

from ..errors import ScreenTimeout
from .planting import PlantingActions


__all__ = ["CottonPlantingActions"]
FILE_FUNCTIONS = (
    "Xác minh template Bông trước gesture",
    "Dùng PlantingActions PATH_27 dùng chung",
    "Chỉ trồng/thu hoạch Bông trên view hiện tại; không tự điều hướng tầng",
    "Cung cấp Action chờ-chín → thu 27 → gieo lại 27 cho caller cần một batch vật liệu thực",
    "Recipe/Recovery chịu trách nhiệm điều hướng và quyết định vì sao cần batch Bông",
)


class CottonPlantingActions(PlantingActions):
    """Current-view Bông adapter over the generic 27-pot planting Action."""

    COTTON_TEMPLATE = "cay_bong"
    BATCH_WAIT_TIMEOUT = 180.0

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

    def wait_harvest_and_replant_27_cotton(
        self,
        *,
        timeout: float | None = None,
    ) -> int:
        """Return only after one real 27-cotton harvest and its replant complete.

        This is still a crop Action: it knows how to wait for the supplied current
        farm view, harvest one verified batch and replant the same crop. It does
        not know *why* the batch is needed, which machine is waiting, which
        Function is running, or what recovery should happen next.
        """
        if not self.vision.assets.has(self.COTTON_TEMPLATE):
            raise ScreenTimeout(
                "Thiếu template clean cay_bong; dừng trước batch Bông"
            )

        effective_timeout = float(timeout or self.BATCH_WAIT_TIMEOUT)
        deadline = time.monotonic() + effective_timeout
        harvested = False
        cycle = 0

        while time.monotonic() < deadline:
            self.context.ensure_running()
            cycle += 1
            state, match = self._scan_first_pot_state(self.COTTON_TEMPLATE)

            if state == "RIPE":
                self.context.log(
                    "AUTO cây Bông • RIPE → thu hoạch một batch 27 chậu"
                )
                self.vision.driver.swipe_points(
                    self.path_for_count(27),
                    duration=self.speed_config.plant_harvest_duration,
                )
                harvested = True
                self.waiter.sleep(0.45)
                continue

            if state == "EMPTY" and match is not None:
                path = (match.center,) + self.path_for_count(27)[1:]
                self.vision.driver.swipe_points(
                    path,
                    duration=self.speed_config.plant_harvest_duration,
                )
                self.waiter.sleep(0.40)
                self.vision.driver.click(*self.CLOSE_POINT)
                self.waiter.sleep(0.55)
                if harvested:
                    self.context.log(
                        "AUTO cây Bông • batch PASS • đã thu 27 và gieo lại 27"
                    )
                    return 27
                self.context.log(
                    "AUTO cây Bông • view đang trống → đã gieo 27; "
                    "chờ chín để caller nhận được một batch đã thu thật"
                )
                self.waiter.sleep(self.speed_config.crop_check_interval)
                continue

            self.vision.driver.click(*self.CLOSE_POINT)
            if cycle == 1 or cycle % 10 == 0:
                self.context.log(
                    "AUTO cây Bông • chưa RIPE/EMPTY để hoàn tất batch • "
                    f"đợi {self.speed_config.crop_check_interval:.3f}s • vòng={cycle}"
                )
            self.waiter.sleep(self.speed_config.crop_check_interval)

        raise ScreenTimeout(
            f"Hết {effective_timeout:.0f}s chờ hoàn tất batch Bông 27 chậu"
        )
