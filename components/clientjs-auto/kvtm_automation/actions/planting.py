from __future__ import annotations

from dataclasses import dataclass

from ..context import AutomationContext
from ..errors import ScreenTimeout
from ..runtime.auto_speed_config import AutoSpeedConfig
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter


__all__ = ["PlantingActions", "PlantingSegmentResult"]
FILE_FUNCTIONS = (
    "Sở hữu geometry/path trồng và thu hoạch dùng chung, không sở hữu Function choreography",
    "Cung cấp path chuẩn 3/5/6/15/24/27/28/30 chậu ở logical 1000x1000",
    "Nhận diện trạng thái chậu RIPE/EMPTY theo crop template",
    "Tìm seed động theo template qua các trang picker; không dùng tọa độ tuyệt đối của seed",
    "Chỉ chuyển trang tìm seed sau khi template mũi tên chứng minh bảng gieo đang mở",
    "Cho phép thu hoạch count A rồi gieo lại count B bằng các path đã xác minh",
    "Crop/template tách khỏi geometry để cùng path dùng được cho nhiều loại cây",
    "Giữ wrapper 27 cũ chỉ để tương thích; code mới dùng current-view Action + Navigation Action riêng",
)


@dataclass(frozen=True)
class PlantingSegmentResult:
    seed_template: str
    item_label: str
    target_count: int
    harvested_count: int
    planted_count: int
    attempts: int


class PlantingActions:
    """Reusable crop planting/harvest primitives.

    This Action owns *how* a verified farm path is dragged. It does not decide
    which floor a Function should visit next or which crop follows another crop.
    Recipes/Modules own that orchestration and call Navigation Actions separately.
    """

    ROSE_TEMPLATE = "cay_hong"
    APPLE_TEMPLATE = "cay_tao"
    SNOW_TEMPLATE = "cay_tuyet"
    TEA_TEMPLATE = "cay_tra"

    TREE_COUNT = 27  # legacy compatibility name
    TREES_PER_LAYER = 6
    START_POINT = (325, 799)
    X_COORDS_ODD = (335, 490, 578, 645, 720, 835)
    X_COORDS_EVEN = (335, 430, 505, 595, 665, 835)
    Y_LAYERS = (940, 725, 505, 280, 40)

    PATH_3 = (
        START_POINT,
        (335, 940), (578, 940),
    )
    PATH_15 = (
        START_POINT,
        (335, 940), (835, 940),
        (835, 725), (335, 725),
        (335, 505), (578, 505),
    )
    PATH_24 = (
        START_POINT,
        (335, 940), (835, 940),
        (835, 725), (335, 725),
        (335, 505), (835, 505),
        (835, 280), (335, 280),
    )
    PATH_27 = (
        START_POINT,
        (335, 940), (835, 940),
        (835, 725), (335, 725),
        (335, 505), (835, 505),
        (835, 280), (335, 280),
        (335, 40), (578, 40),
    )
    PATH_28 = (
        START_POINT,
        (335, 940), (835, 940),
        (835, 725), (335, 725),
        (335, 505), (835, 505),
        (835, 280), (335, 280),
        (335, 40), (645, 40),
    )
    PATH_30 = (
        START_POINT,
        (335, 940), (835, 940),
        (835, 725), (335, 725),
        (335, 505), (835, 505),
        (835, 280), (335, 280),
        (335, 40), (835, 40),
    )
    PATH_6 = (
        START_POINT,
        (335, 940), (835, 940),
    )
    PATH_5 = (
        START_POINT,
        (335, 940), (720, 940),
    )

    # Historical public name retained for compatibility.
    FARM_PATH_27 = PATH_27
    VERIFIED_PATHS = {
        3: PATH_3,
        5: PATH_5,
        6: PATH_6,
        15: PATH_15,
        24: PATH_24,
        27: PATH_27,
        28: PATH_28,
        30: PATH_30,
    }

    OPEN_PLANT_POINT = (388, 946)
    CLOSE_POINT = (965, 198)
    CLOSE_SIDE_POINT = (975, 316)
    GO_UP_ONE_START = (514, 214)
    GO_UP_ONE_END = (514, 314)
    SEED_ZONE = (179, 773, 230, 166)
    EMPTY_READY_ZONE = (124, 729, 347, 236)
    HARVEST_ZONE = (222, 703, 218, 191)
    SEED_PANEL_ARROW_TEMPLATE = "next_gieo_trai"
    # Operator-marked right-page arrow in the seed picker (logical 1000x1000).
    # Seed locations themselves are never absolute and are always template-matched.
    SEED_NEXT_PAGE_POINT = (418, 848)
    SEED_PAGE_SETTLE_SECONDS = 0.35
    SEED_PANEL_PROOF_RECHECKS = 3
    SEED_PANEL_PROOF_RECHECK_SECONDS = 0.15
    SEED_MAX_PAGE_TURNS = 8
    SEED_PICKER_CLOSE_ATTEMPTS = 3

    def __init__(
        self,
        context: AutomationContext,
        vision: VisionEngine,
        waiter: Waiter,
        speed_config: AutoSpeedConfig | None = None,
    ) -> None:
        self.context = context
        self.vision = vision
        self.waiter = waiter
        self.speed_config = speed_config or AutoSpeedConfig()

    @classmethod
    def path_for_count(cls, count: int) -> tuple[tuple[int, int], ...]:
        """Return only operator/source-verified geometry; never synthesize paths."""
        requested = int(count)
        path = cls.VERIFIED_PATHS.get(requested)
        if path is None:
            raise ValueError(
                f"Chưa có planting path được xác minh cho count={requested}; fail-close"
            )
        return tuple(path)

    @classmethod
    def rose_path(cls) -> tuple[tuple[int, int], ...]:
        """Historical helper for the verified 27-pot path."""
        return cls.path_for_count(27)

    def _go_up_one(self) -> None:
        """LEGACY compatibility only.

        New orchestration must call ``FloorNavigationActions.go_up(1)`` before a
        current-view planting Action. This wrapper remains so old isolated
        workflows are not silently broken during the staged standardization.
        """
        self.context.ensure_running()
        self.context.invalidate_camera_main("legacy-planting-goUp(1)")
        self.vision.driver.click(*self.CLOSE_SIDE_POINT)
        self.waiter.sleep(0.20)
        self.vision.driver.swipe(
            *self.GO_UP_ONE_START,
            *self.GO_UP_ONE_END,
            duration=self.speed_config.floor_swipe_duration,
        )
        self.waiter.sleep(0.65)
        self.context.log(
            "AUTO trồng legacy • goUp(1) compatibility • "
            "code mới phải dùng Navigation Action riêng"
        )

    def _count_changed_pots_27(self, before, after) -> int:
        """Legacy non-blocking diagnostic for the verified 27-pot path."""
        centers = (
            (335, 940), (490, 940), (578, 940), (645, 940), (720, 940), (835, 940),
            (835, 725), (665, 725), (595, 725), (505, 725), (430, 725), (335, 725),
            (335, 505), (490, 505), (578, 505), (645, 505), (720, 505), (835, 505),
            (835, 280), (665, 280), (595, 280), (505, 280), (430, 280), (335, 280),
            (335, 40), (490, 40), (578, 40),
        )
        changed = 0
        for center in centers:
            logical_zone = (center[0] - 24, center[1] - 24, 48, 48)
            bx, by, bw, bh = self.vision.logical_zone_to_frame(
                logical_zone, before
            )
            ax, ay, aw, ah = self.vision.logical_zone_to_frame(
                logical_zone, after
            )
            old = before[by : by + bh, bx : bx + bw].astype("int16")
            new = after[ay : ay + ah, ax : ax + aw].astype("int16")
            if old.shape == new.shape and old.size:
                difference = float(abs(new - old).mean())
                if difference >= 8.0:
                    changed += 1
        return changed

    # Historical name retained for existing diagnostics/tests.
    def _count_changed_pots(self, before, after) -> int:
        return self._count_changed_pots_27(before, after)

    def _find_seed_panel_arrow(self, *, frame=None):
        return self.vision.find(
            self.SEED_PANEL_ARROW_TEMPLATE,
            threshold=0.70,
            zone=self.EMPTY_READY_ZONE,
            scales=(0.80, 0.90, 1.00, 1.10, 1.20),
            frame=frame,
        )

    def _prove_seed_picker_open_for_page_turn(self):
        """Prove the seed picker before any page-arrow click; never click blind."""
        for recheck in range(1, self.SEED_PANEL_PROOF_RECHECKS + 1):
            self.context.ensure_running()
            frame = self.vision.frame()
            arrow = self._find_seed_panel_arrow(frame=frame)
            if arrow is not None:
                self.context.detail(
                    "AUTO planting picker proof PASS | "
                    f"template={self.SEED_PANEL_ARROW_TEMPLATE} | "
                    f"center={arrow.center} | recheck={recheck}"
                )
                return arrow
            if recheck < self.SEED_PANEL_PROOF_RECHECKS:
                self.waiter.sleep(self.SEED_PANEL_PROOF_RECHECK_SECONDS)

        return None

    def _find_seed_in_open_picker(
        self,
        seed_template: str,
        item_label: str,
        *,
        first_match: object | None = None,
    ):
        """Find a seed by template, paging right until the requested seed appears.

        Seed order/location may vary between accounts/sessions. The only fixed
        coordinate here is the operator-marked picker page arrow. Once a template
        is found, callers must drag from ``match.center`` rather than any absolute
        seed coordinate. Every page turn is gated by the existing arrow template
        that proves the seed picker is actually open.
        """
        match = first_match
        page_moves = 0
        while match is None:
            self.context.ensure_running()
            frame = self.vision.frame()
            match = self.vision.find(
                seed_template,
                threshold=0.87,
                zone=self.SEED_ZONE,
                scales=(0.80, 0.90, 1.00, 1.10, 1.20),
                frame=frame,
            )
            if match is not None:
                break

            arrow = self._prove_seed_picker_open_for_page_turn()
            if arrow is None:
                self.context.log(
                    f"AUTO trồng • seed {item_label} MISS nhưng bảng gieo CHƯA VERIFIED • "
                    "KHÔNG chuyển trang • fail-close"
                )
                raise ScreenTimeout(
                    f"Không chứng minh bảng gieo đang mở trước khi chuyển trang tìm {item_label}"
                )

            page_moves += 1
            if page_moves > self.SEED_MAX_PAGE_TURNS:
                raise ScreenTimeout(
                    f"Không tìm thấy hạt {item_label} sau "
                    f"{self.SEED_MAX_PAGE_TURNS} lần chuyển trang"
                )
            self.context.log(
                f"AUTO trồng • bảng gieo VERIFIED bằng {self.SEED_PANEL_ARROW_TEMPLATE} "
                f"center={arrow.center} • seed {item_label} MISS • "
                f"chuyển trang phải lần {page_moves} • "
                f"point={self.SEED_NEXT_PAGE_POINT}"
            )
            self.vision.driver.click(*self.SEED_NEXT_PAGE_POINT)
            self.waiter.sleep(self.SEED_PAGE_SETTLE_SECONDS)

        self.context.detail(
            "AUTO planting dynamic seed READY | "
            f"seed={seed_template} | item={item_label} | "
            f"page_moves={page_moves} | center={match.center}"
        )
        return match

    def close_seed_picker_verified(self, *, label: str) -> None:
        """Close the planting picker and prove it no longer owns input."""

        for attempt in range(1, self.SEED_PICKER_CLOSE_ATTEMPTS + 1):
            self.context.ensure_running()
            if self._prove_seed_picker_open_for_page_turn() is None:
                self.context.detail(
                    f"AUTO planting picker CLOSED VERIFIED | label={label} | attempt={attempt}"
                )
                return
            self.vision.driver.click(*self.CLOSE_POINT)
            self.waiter.sleep(0.30)
        if self._prove_seed_picker_open_for_page_turn() is not None:
            raise ScreenTimeout(
                f"Bảng gieo chưa đóng sau {self.SEED_PICKER_CLOSE_ATTEMPTS} lần: {label}"
            )

    def _scan_first_pot_state(self, seed_template: str) -> tuple[str, object | None]:
        self.context.ensure_running()
        # OPEN_PLANT_POINT is the operator-verified hitbox that opens the
        # seed/harvest picker. Path waypoints are drag geometry, not click hitboxes.
        self.vision.driver.click(*self.OPEN_PLANT_POINT)
        self.context.detail(
            "AUTO planting open picker | "
            f"seed={seed_template} | point={self.OPEN_PLANT_POINT}"
        )
        self.waiter.sleep(0.45)
        frame = self.vision.frame()
        harvest = self.vision.find(
            "thu_hoach", threshold=0.80, zone=self.HARVEST_ZONE,
            scales=(0.70, 0.80, 0.90, 1.00, 1.10, 1.20, 1.30), frame=frame,
        )
        empty = self._find_seed_panel_arrow(frame=frame)
        seed = self.vision.find(
            seed_template, threshold=0.87, zone=self.SEED_ZONE,
            scales=(0.80, 0.90, 1.00, 1.10, 1.20), frame=frame,
        )
        if harvest is not None:
            return "RIPE", harvest
        if empty is not None:
            return "EMPTY", seed
        return "UNKNOWN", None

    def harvest_and_replant_current_view(
        self,
        *,
        seed_template: str,
        item_label: str,
        count: int,
        plant_count: int | None = None,
        path: tuple[tuple[int, int], ...] | None = None,
        segment_label: str = "",
        max_attempts: int = 6,
    ) -> PlantingSegmentResult:
        """Harvest current-view pots, then plant a verified count of the crop.

        ``count`` owns the harvest geometry. ``plant_count`` defaults to the same
        value, preserving every existing caller. A caller may explicitly request
        a smaller verified replant count, such as harvest 6 then plant 3.

        Seed position/order inside the picker is dynamic. If the requested seed is
        not on the current picker page, the shared Action advances only with the
        fixed right-page arrow after the picker is proven open, then drags from the
        detected template center.
        """
        harvest_requested = int(count)
        plant_requested = (
            harvest_requested if plant_count is None else int(plant_count)
        )
        harvest_path = tuple(path or self.path_for_count(harvest_requested))
        replant_path = self.path_for_count(plant_requested)
        label = str(
            segment_label
            or (
                f"{item_label} thu {harvest_requested} / gieo {plant_requested}"
                if harvest_requested != plant_requested
                else f"{item_label} x{harvest_requested}"
            )
        )
        attempts_limit = max(1, int(max_attempts))
        harvested = 0

        for attempt in range(1, attempts_limit + 1):
            self.context.ensure_running()
            # Every attempt reopens the picker through the verified click hitbox.
            # harvest_path[1] is only a drag waypoint and must never replace it.
            state, match = self._scan_first_pot_state(seed_template)

            if state == "RIPE" and match is not None:
                self.context.log(
                    f"AUTO trồng • {label} • RIPE → thu hoạch {harvest_requested} chậu"
                )
                self.vision.driver.swipe_points(
                    harvest_path,
                    duration=self.speed_config.plant_harvest_duration,
                )
                harvested = harvest_requested
                self.waiter.sleep(0.55)

                # RIPE may be discovered on the last allowed attempt. Reopen the
                # picker from the now-empty first pot immediately in this same
                # attempt; never require an artificial attempt 7 just to plant.
                state, match = self._scan_first_pot_state(seed_template)
                self.context.log(
                    f"AUTO trồng • {label} • sau thu hoạch đã mở lại bảng gieo "
                    f"tại điểm chuẩn={self.OPEN_PLANT_POINT}"
                )

            if state == "EMPTY":
                match = self._find_seed_in_open_picker(
                    seed_template,
                    item_label,
                    first_match=match,
                )
                plant_path = (match.center,) + tuple(replant_path[1:])
                self.context.log(
                    f"AUTO trồng • {label} • seed {item_label} READY động "
                    f"center={match.center} → gieo {plant_requested} chậu"
                )
                self.vision.driver.swipe_points(
                    plant_path,
                    duration=self.speed_config.plant_harvest_duration,
                )
                self.waiter.sleep(0.45)
                self.close_seed_picker_verified(label=label)
                self.waiter.sleep(0.15)
                self.context.log(
                    f"AUTO trồng • {label} • PASS gieo {plant_requested}/{plant_requested}"
                )
                return PlantingSegmentResult(
                    seed_template=str(seed_template),
                    item_label=str(item_label),
                    target_count=plant_requested,
                    harvested_count=harvested,
                    planted_count=plant_requested,
                    attempts=attempt,
                )

            self.context.log(
                f"AUTO trồng • {label} • chưa chứng minh RIPE/EMPTY "
                f"lần {attempt}/{attempts_limit} • "
                f"đã click lại điểm mở chuẩn={self.OPEN_PLANT_POINT}"
            )
            self.close_seed_picker_verified(label=f"{label}: trạng thái chưa xác định")

        raise ScreenTimeout(
            f"Không hoàn tất planting segment {label} sau {attempts_limit} lần; fail-close"
        )

    def plant_current_view(
        self,
        *,
        seed_template: str,
        item_label: str,
        count: int,
    ) -> int:
        """Convenience Action for callers that only need the planted count."""
        result = self.harvest_and_replant_current_view(
            seed_template=seed_template,
            item_label=item_label,
            count=int(count),
        )
        return int(result.planted_count)

    def _harvest_27(self) -> None:
        """Legacy helper retained for old isolated callers."""
        self.context.log("AUTO trồng legacy • thu hoạch 27 chậu")
        self.vision.driver.swipe_points(
            self.path_for_count(27),
            duration=self.speed_config.plant_harvest_duration,
        )
        self.waiter.sleep(0.50)

    def _open_seed_picker(self, seed_template: str, item_label: str):
        """Legacy entry that includes goUp(1); new code must separate Navigation."""
        self._go_up_one()
        baseline = self.vision.frame().copy()
        for attempt in range(1, 6):
            state, match = self._scan_first_pot_state(seed_template)
            if state == "EMPTY":
                match = self._find_seed_in_open_picker(
                    seed_template,
                    item_label,
                    first_match=match,
                )
                self.context.log(
                    f"AUTO trồng legacy • bảng hạt READY động • lần {attempt}/5"
                )
                return baseline, match
            if state == "RIPE":
                self._harvest_27()
                continue
            self.context.log(
                f"AUTO trồng legacy • chưa xác định RIPE/EMPTY • lần {attempt}/5"
            )
            self.vision.driver.click(*self.CLOSE_POINT)
            self.waiter.sleep(0.30)
        raise ScreenTimeout(
            "Không xác minh được cây chín hoặc chậu trống tại tầng gieo"
        )

    def _plant_27(self, seed_template: str, item_label: str) -> int:
        """Legacy 27 wrapper preserving old entry semantics during migration."""
        baseline, seed = self._open_seed_picker(seed_template, item_label)
        self.context.ensure_running()
        if seed is None:
            self.vision.driver.click(*self.CLOSE_POINT)
            raise ScreenTimeout(
                f"Không nhận diện được hạt {item_label} trong bảng gieo"
            )
        path = (seed.center,) + self.path_for_count(27)[1:]
        self.vision.driver.swipe_points(
            path, duration=self.speed_config.plant_harvest_duration
        )
        self.waiter.sleep(0.40)
        self.vision.driver.click(*self.CLOSE_POINT)
        self.waiter.sleep(0.55)
        after = self.vision.frame().copy()
        changed = self._count_changed_pots_27(baseline, after)
        self.context.detail(
            "AUTO planting legacy diagnostic | "
            f"item={seed_template} | changed_waypoint_regions={changed}/27 | "
            "non_blocking=true"
        )
        self.context.log(
            f"AUTO trồng legacy • {item_label} 27/27 PASS"
        )
        return 27

    def plant_27_roses(self) -> int:
        return self._plant_27(self.ROSE_TEMPLATE, "Hoa hồng")

    def plant_27_apples(self) -> int:
        return self._plant_27(self.APPLE_TEMPLATE, "Táo")
