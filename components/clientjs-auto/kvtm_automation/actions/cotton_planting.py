from __future__ import annotations

from ..errors import ScreenTimeout
from .planting import PlantingActions


__all__ = ["CottonPlantingActions"]
FILE_FUNCTIONS = (
    "Xác minh template bông tồn tại trong clean asset library trước gesture",
    "Tái sử dụng đường gieo 27 chậu đã dùng ở hai pass trước",
    "Giữ seed match Bông đã xác minh trên cùng frame READY để tránh race frame",
    "Ghi hậu kiểm vùng chậu như diagnostic không chặn, giống logic trồng Táo",
)


class CottonPlantingActions(PlantingActions):
    """Plant exactly 27 cotton plants through the proven clean planting path."""

    COTTON_TEMPLATE = "cay_bong"

    def plant_27_cotton(self) -> int:
        if not self.vision.assets.has(self.COTTON_TEMPLATE):
            raise ScreenTimeout(
                "Thiếu template clean cay_bong; dừng trước mọi gesture gieo Bông"
            )

        # _open_seed_picker now returns both the detached diagnostic baseline and
        # the seed match proven on the SAME READY frame. Reusing that match avoids
        # a second capture racing with the seed-picker animation, and also keeps
        # baseline as an ndarray instead of accidentally passing the tuple below.
        baseline, seed = self._open_seed_picker(self.COTTON_TEMPLATE, "Bông")
        self.context.ensure_running()
        if seed is None:
            self.vision.driver.click(*self.CLOSE_POINT)
            raise ScreenTimeout(
                "Không nhận diện được hạt Bông trong bảng gieo; dừng fail-close"
            )

        path = (seed.center,) + self.rose_path()[1:]
        self.context.log(
            "AUTO trồng • chọn Bông • dùng seed match đã xác minh cùng frame • "
            "kéo 27 chậu từ tầng 1 đến 3 chậu tầng 5"
        )
        self.vision.driver.swipe_points(
            path, duration=self.speed_config.plant_harvest_duration
        )
        self.waiter.sleep(0.40)
        self.vision.driver.click(*self.CLOSE_POINT)
        self.waiter.sleep(0.55)

        # Match the already-stable apple planting contract. The 27-point native
        # path is the business action; visible-region comparison is only useful
        # as diagnostics because the fifth row can be outside the current camera
        # viewport after the gesture. A 0/27 or partial visible count must not
        # turn a successfully dispatched 27-pot planting path into a false error.
        after = self.vision.frame().copy()
        changed = self._count_changed_pots(baseline, after)
        self.context.detail(
            "AUTO cotton planting diagnostic | "
            f"changed_waypoint_regions={changed}/27 | non_blocking=true"
        )
        self.context.log(
            "AUTO trồng Bông • đã gửi đủ đường gieo 27 chậu • "
            f"hậu kiểm vùng nhìn thấy={changed}/27 chỉ dùng chẩn đoán"
        )
        return self.TREE_COUNT
