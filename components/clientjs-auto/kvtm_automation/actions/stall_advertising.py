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

    We deliberately use color/geometry only inside tight UI zones. Farm/world
    background is never consulted, and the orange diamond paid-ad button is
    outside the only click zone used for free advertisement.
    """

    # Local-slot marker is left of the item icon. On the supplied image the red
    # advertisement tag occupies about 8.5% of this zone, while non-ad slots are
    # below 0.7%. 3.5% keeps a large separation margin.
    AD_MARKER_RED_RATIO = 0.035

    # Tight inner strip of the bottom free-ad button. Supplied READY sample is
    # ~55% bright green while cooldown/disabled is 0% in this strip.
    READY_GREEN_RATIO = 0.30
    READY_BUTTON_ZONE = (440, 685, 120, 28)
    READY_BUTTON_POINT = (500, 699)

    # Tight zone around the listing-detail X. Only click a detected red control;
    # there is no blind fallback coordinate.
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

    @staticmethod
    def _scaled_zone(frame, zone: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        height, width = frame.shape[:2]
        sx = width / 1000.0
        sy = height / 1000.0
        x, y, w, h = zone
        return (
            max(0, int(round(x * sx))),
            max(0, int(round(y * sy))),
            max(1, int(round(w * sx))),
            max(1, int(round(h * sy))),
        )

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

    @classmethod
    def _slot_marker_zone(cls, frame, local_slot: int) -> tuple[int, int, int, int]:
        height, width = frame.shape[:2]
        sx = width / 1000.0
        sy = height / 1000.0
        cx, cy = VISIBLE_SLOT_CENTERS[int(local_slot) - 1]
        x = int(round((cx - 95) * sx))
        y = int(round((cy - 50) * sy))
        w = int(round(80 * sx))
        h = int(round(100 * sy))
        return max(0, x), max(0, y), max(1, w), max(1, h)

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
        return x + int(round(float(xs.mean()))), y + int(round(float(ys.mean())))

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
        height, width = frame.shape[:2]
        return (
            int(round(self.READY_BUTTON_POINT[0] * width / 1000.0)),
            int(round(self.READY_BUTTON_POINT[1] * height / 1000.0)),
        )

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
                f"attempt={attempt}/3 | center={center}"
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

        # The paid orange diamond button is around x~625,y~627 in the supplied
        # cooldown sample. We never click there: this point is inside the visually
        # proven green FREE ``Đặt quảng cáo`` button only.
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

        # Do not click the green control again after one destructive attempt.
        # Advertisement is opportunistic and must never interrupt the proven sale
        # transaction just because the marker animation/render was late.
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
