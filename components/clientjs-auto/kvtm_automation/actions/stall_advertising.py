from __future__ import annotations

from dataclasses import dataclass

from ..context import AutomationContext
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter
from .stall import StallActions, VISIBLE_SLOT_CENTERS


__all__ = ["StallAdvertisementResult", "StallAdvertisingActions"]
FILE_FUNCTIONS = (
    "Kiểm tra quảng cáo ở ba mốc đầu/giữa/cuối của mỗi lượt bán VP",
    "Chỉ chọn ô quầy còn listing và chưa có biểu tượng quảng cáo đỏ",
    "Mở chi tiết listing để kiểm tra trạng thái quảng cáo",
    "Chỉ click Đặt quảng cáo khi nút xanh đã hồi; tuyệt đối không click nút kim cương trả phí",
    "Nếu quảng cáo còn cooldown thì đóng popup bằng X và tiếp tục bán",
    "Sau khi đặt quảng cáo, đóng popup và hậu kiểm biểu tượng quảng cáo trên đúng ô",
    "Mọi center public trả cho driver luôn ở logical 1000 dù color probe chạy trên frame 500",
    "Lỗi nhận diện quảng cáo là non-blocking và không được làm hỏng luồng bán VP",
)


@dataclass(frozen=True)
class StallAdvertisementResult:
    status: str
    checkpoint: str
    view: int
    physical_slot: int = 0
    local_slot: int = 0


class StallAdvertisingActions:
    """Non-blocking own-stall advertisement helper for AUTO VP sale.

    The user-provided 1000x1000 samples establish three stable visual facts:
    * an already-advertised listing carries a bright red tag on the left edge;
    * the free ``Đặt quảng cáo`` control is bright green only when cooldown ended;
    * the listing detail popup has a red X near (607, 300).

    Color probes operate on actual frame pixels, but every returned click center
    is converted back to logical 1000 before it reaches Bridge INPUT4. This keeps
    the action resolution-independent and avoids a second 0.5 scale at 500x500.
    """

    AD_MARKER_RED_RATIO = 0.035
    READY_GREEN_RATIO = 0.30
    READY_BUTTON_ZONE = (440, 685, 120, 28)
    READY_BUTTON_POINT = (500, 699)
    MODAL_CLOSE_ZONE = (585, 280, 45, 45)
    MODAL_CLOSE_RED_RATIO = 0.08

    def __init__(
        self,
        context: AutomationContext,
        vision: VisionEngine,
        waiter: Waiter,
        stall: StallActions,
    ) -> None:
        self.context = context
        self.vision = vision
        self.waiter = waiter
        self.stall = stall
        self._checked_physical_slots: set[int] = set()

    def _scaled_zone(
        self, frame, zone: tuple[int, int, int, int]
    ) -> tuple[int, int, int, int]:
        return self.vision.logical_zone_to_frame(zone, frame)

    @staticmethod
    def _red_ratio(roi) -> float:
        if roi is None or getattr(roi, "size", 0) == 0:
            return 0.0
        source = roi[:, :, :3]
        blue = source[:, :, 0].astype("float32")
        green = source[:, :, 1].astype("float32")
        red = source[:, :, 2].astype("float32")
        mask = (
            (red > 180.0)
            & (green < 100.0)
            & (blue < 100.0)
            & (red > green * 1.50)
            & (red > blue * 1.50)
        )
        return float(mask.mean())

    @staticmethod
    def _green_ratio(roi) -> float:
        if roi is None or getattr(roi, "size", 0) == 0:
            return 0.0
        source = roi[:, :, :3]
        blue = source[:, :, 0].astype("float32")
        green = source[:, :, 1].astype("float32")
        red = source[:, :, 2].astype("float32")
        mask = (
            (green > 140.0)
            & (red < 140.0)
            & (blue < 100.0)
            & (green > red * 1.15)
            & (green > blue * 1.35)
        )
        return float(mask.mean())

    def _slot_marker_zone(self, frame, local_slot: int) -> tuple[int, int, int, int]:
        cx, cy = VISIBLE_SLOT_CENTERS[int(local_slot) - 1]
        return self.vision.logical_zone_to_frame(
            (cx - 95, cy - 50, 80, 100), frame
        )

    def _slot_has_ad_marker(self, frame, local_slot: int) -> tuple[bool, float]:
        x, y, w, h = self._slot_marker_zone(frame, local_slot)
        roi = frame[y : y + h, x : x + w]
        ratio = self._red_ratio(roi)
        return ratio >= self.AD_MARKER_RED_RATIO, ratio

    def _modal_close_center(self, frame) -> tuple[int, int] | None:
        x, y, w, h = self._scaled_zone(frame, self.MODAL_CLOSE_ZONE)
        roi = frame[y : y + h, x : x + w]
        if roi is None or getattr(roi, "size", 0) == 0:
            return None

        source = roi[:, :, :3]
        blue = source[:, :, 0].astype("float32")
        green = source[:, :, 1].astype("float32")
        red = source[:, :, 2].astype("float32")
        mask = (
            (red > 180.0)
            & (green < 100.0)
            & (blue < 100.0)
            & (red > green * 1.50)
            & (red > blue * 1.50)
        )
        ratio = float(mask.mean())
        if ratio < self.MODAL_CLOSE_RED_RATIO:
            return None

        import numpy as np

        ys, xs = np.nonzero(mask)
        if not len(xs):
            return None
        frame_center = (
            x + int(round(float(xs.mean()))),
            y + int(round(float(ys.mean()))),
        )
        return self.vision.frame_point_to_logical(frame_center, frame)

    def _free_ad_ready_center(self, frame) -> tuple[int, int] | None:
        x, y, w, h = self._scaled_zone(frame, self.READY_BUTTON_ZONE)
        roi = frame[y : y + h, x : x + w]
        ratio = self._green_ratio(roi)
        self.context.detail(
            "AUTO quảng cáo | free_ad_ready_probe=true | "
            f"green_ratio={ratio:.3f} | threshold={self.READY_GREEN_RATIO:.3f}"
        )
        if ratio < self.READY_GREEN_RATIO:
            return None
        # This is already canonical logical geometry. Do not pre-scale to frame
        # pixels because Bridge INPUT4 performs logical->client conversion once.
        return self.READY_BUTTON_POINT

    def _close_listing_modal(self) -> bool:
        """Close only a visually confirmed listing-detail X; never click blind."""
        for attempt in range(1, 4):
            self.context.ensure_running()
            frame = self.vision.frame()
            center = self._modal_close_center(frame)
            if center is None:
                return True
            self.vision.driver.click(*center)
            self.waiter.sleep(0.30)
            self.context.detail(
                "AUTO quảng cáo | close_listing_modal=true | "
                f"attempt={attempt}/3 | logical_center={center}"
            )
        return self._modal_close_center(self.vision.frame()) is None

    def _ordered_local_slots(self, view: int, target_physical_slot: int) -> tuple[int, ...]:
        locals_ = self.stall.visible_local_slots(view)
        return tuple(
            sorted(
                locals_,
                key=lambda local_slot: (
                    abs(
                        self.stall.physical_slot(view, local_slot)
                        - int(target_physical_slot)
                    ),
                    self.stall.physical_slot(view, local_slot),
                ),
            )
        )

    def check_checkpoint(
        self,
        *,
        view: int,
        checkpoint: str,
        target_physical_slot: int,
    ) -> StallAdvertisementResult:
        """Check one non-advertised listing nearest the requested stall position."""
        self.context.ensure_running()
        frame = self.vision.frame()

        candidate_local = 0
        candidate_physical = 0
        for local_slot in self._ordered_local_slots(view, target_physical_slot):
            physical = self.stall.physical_slot(view, local_slot)
            if physical in self._checked_physical_slots:
                continue
            if not self.stall.listing_is_available(frame, local_slot):
                continue

            has_ad, red_ratio = self._slot_has_ad_marker(frame, local_slot)
            if has_ad:
                self._checked_physical_slots.add(physical)
                self.context.log(
                    "AUTO quảng cáo • "
                    f"mốc {checkpoint} • ô {physical} đã có QC "
                    f"(red_ratio={red_ratio:.3f}) → KHÔNG click kiểm tra"
                )
                continue

            candidate_local = int(local_slot)
            candidate_physical = int(physical)
            break

        if candidate_local <= 0:
            self.context.log(
                f"AUTO quảng cáo • mốc {checkpoint} • không có listing chưa QC phù hợp để kiểm tra"
            )
            return StallAdvertisementResult(
                status="NO_CANDIDATE",
                checkpoint=checkpoint,
                view=int(view),
            )

        self._checked_physical_slots.add(candidate_physical)
        click_point = VISIBLE_SLOT_CENTERS[candidate_local - 1]
        self.vision.driver.click(*click_point)
        self.waiter.sleep(0.35)

        modal_frame = self.vision.frame()
        close_center = self._modal_close_center(modal_frame)
        if close_center is None:
            self.context.log(
                "AUTO quảng cáo • "
                f"mốc {checkpoint} • ô {candidate_physical} không mở được popup kiểm tra QC • "
                "NON-BLOCKING"
            )
            return StallAdvertisementResult(
                status="MODAL_NOT_OPEN",
                checkpoint=checkpoint,
                view=int(view),
                physical_slot=candidate_physical,
                local_slot=candidate_local,
            )

        ready_center = self._free_ad_ready_center(modal_frame)
        if ready_center is None:
            closed = self._close_listing_modal()
            self.context.log(
                "AUTO quảng cáo • "
                f"mốc {checkpoint} • ô {candidate_physical} còn thời gian chờ QC → "
                f"đóng X={'PASS' if closed else 'UNVERIFIED'} • tiếp tục bán"
            )
            return StallAdvertisementResult(
                status="COOLDOWN" if closed else "COOLDOWN_CLOSE_UNVERIFIED",
                checkpoint=checkpoint,
                view=int(view),
                physical_slot=candidate_physical,
                local_slot=candidate_local,
            )

        self.vision.driver.click(*ready_center)
        self.waiter.sleep(0.50)
        self.context.log(
            "AUTO quảng cáo • "
            f"mốc {checkpoint} • ô {candidate_physical} • QC miễn phí đã hồi → "
            "click Đặt quảng cáo"
        )

        self._close_listing_modal()
        for verify_attempt in range(1, 4):
            self.context.ensure_running()
            verify_frame = self.vision.frame()
            has_ad, red_ratio = self._slot_has_ad_marker(
                verify_frame, candidate_local
            )
            if has_ad:
                self.context.log(
                    "AUTO quảng cáo • PASS • "
                    f"mốc {checkpoint} • ô {candidate_physical} đã có dấu QC "
                    f"(red_ratio={red_ratio:.3f})"
                )
                return StallAdvertisementResult(
                    status="ADVERTISED",
                    checkpoint=checkpoint,
                    view=int(view),
                    physical_slot=candidate_physical,
                    local_slot=candidate_local,
                )
            if verify_attempt < 3:
                self.waiter.sleep(0.25)

        self.context.log(
            "AUTO quảng cáo • đã click Đặt quảng cáo nhưng chưa hậu kiểm được dấu QC • "
            f"mốc {checkpoint} • ô {candidate_physical} • NON-BLOCKING • không retry click"
        )
        return StallAdvertisementResult(
            status="ACTIVATED_UNVERIFIED",
            checkpoint=checkpoint,
            view=int(view),
            physical_slot=candidate_physical,
            local_slot=candidate_local,
        )
