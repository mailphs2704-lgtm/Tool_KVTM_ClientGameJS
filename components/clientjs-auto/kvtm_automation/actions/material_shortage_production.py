from __future__ import annotations

from dataclasses import dataclass
import time

from ..errors import ScreenTimeout
from ..material_shortage import MaterialShortage, MaterialShortageEvidence
from .apple_juice_production import AppleJuiceProductionActions as BaseAppleJuiceProductionActions
from .cotton_planting import CottonPlantingActions as BaseCottonPlantingActions
from .machine_repair import (
    MachineRepairActions as BaseMachineRepairActions,
    MachineRepairHandoff,
)
from .production import ProductionActions as BaseProductionActions, ProductionResult
from .yellow_fabric_production import (
    YellowFabricProductionActions as BaseYellowFabricProductionActions,
)


__all__ = [
    "MaterialAwareAppleJuiceProductionActions",
    "MaterialAwareCottonPlantingActions",
    "MaterialAwareMachineRepairActions",
    "MaterialAwareProductionActions",
    "MaterialAwareProductionResult",
    "MaterialAwareYellowFabricProductionActions",
]

FILE_FUNCTIONS = (
    "Bắt hai popup thiếu nguyên liệu/sắp hết cây bằng X đúng vùng + hình học modal xanh",
    "Phân loại NOT_ENOUGH và LOW_STOCK theo dấu nút xanh/lam của hai template live 500x500",
    "Sau popup kiểm tra lại ô trống để biết gesture vừa rồi có thật sự xếp được sản phẩm hay chưa",
    "Phát MaterialShortage kèm đúng loại cây và số lượng đã xếp, không reset cả lượt sản xuất",
    "Khi quay lại máy chỉ chờ đủ số ô trống cho phần còn thiếu rồi tiếp tục",
    "Táo sấy và Nước táo ánh xạ thiếu nguyên liệu sang cay_tao",
    "Vải vàng ánh xạ thiếu nguyên liệu sang cay_bong",
    "Handoff Sửa máy chấp nhận đủ số queue-event đã hậu kiểm qua recovery gián đoạn",
)


@dataclass(frozen=True)
class MaterialAwareProductionResult(ProductionResult):
    """Production result with per-gesture proof across one or more recoveries."""

    verified_queue_events: int = 0
    material_recovery_count: int = 0


@dataclass
class _ResumeState:
    queued: int = 0
    first_empty_before: int | None = None
    top_point: tuple[int, int] | None = None
    recovery_count: int = 0

    def reset(self) -> None:
        self.queued = 0
        self.first_empty_before = None
        self.top_point = None
        self.recovery_count = 0


class _MaterialShortageMixin:
    """Shared visual guard for the two supplied material-shortage popup variants."""

    # Both supplied live screenshots are native 500x500. Coordinates remain
    # logical 1000 because VisionEngine/Bridge own the single 1000->500 transform.
    SHORTAGE_X_ZONE = (682, 337, 142, 120)
    SHORTAGE_MODAL_ZONE = (250, 385, 500, 245)
    SHORTAGE_BUTTON_ZONE = (490, 570, 170, 70)
    SHORTAGE_X_THRESHOLD = 0.78
    SHORTAGE_GREEN_RATIO_MIN = 0.55
    SHORTAGE_BLUE_RATIO_MIN = 0.03

    def _init_material_resume(self) -> None:
        self._material_resume = _ResumeState()

    def _shortage_modal(self, frame):
        """Return (kind, x_match, green_ratio) for either supplied popup template."""
        import numpy as np

        x_match = self.vision.find(
            "x",
            threshold=self.SHORTAGE_X_THRESHOLD,
            zone=self.SHORTAGE_X_ZONE,
            scales=(0.80, 0.90, 1.00, 1.10, 1.20),
            click=False,
            frame=frame,
        )
        if x_match is None:
            return None

        x, y, width, height = self.vision.logical_zone_to_frame(
            self.SHORTAGE_MODAL_ZONE, frame
        )
        roi = frame[y : y + height, x : x + width]
        if roi is None or getattr(roi, "size", 0) == 0 or roi.ndim < 3:
            return None

        blue = roi[:, :, 0].astype("int16")
        green = roi[:, :, 1].astype("int16")
        red = roi[:, :, 2].astype("int16")
        green_ratio = float(
            (
                (green > red + 8)
                & (green > blue + 25)
                & (green > 85)
            ).mean()
        )
        if green_ratio < self.SHORTAGE_GREEN_RATIO_MIN:
            return None

        bx, by, bw, bh = self.vision.logical_zone_to_frame(
            self.SHORTAGE_BUTTON_ZONE, frame
        )
        buttons = frame[by : by + bh, bx : bx + bw]
        blue_ratio = 0.0
        if buttons is not None and getattr(buttons, "size", 0) and buttons.ndim >= 3:
            bb = buttons[:, :, 0].astype("int16")
            bg = buttons[:, :, 1].astype("int16")
            br = buttons[:, :, 2].astype("int16")
            blue_ratio = float(
                (
                    (bb > 100)
                    & (bb > bg + 10)
                    & (bb > br + 20)
                ).mean()
            )

        # The supplied "KHÔNG ĐỦ NGUYÊN LIỆU RỒI" popup contains the blue
        # "Đến Bảng tin" button; "SẮP HẾT CÂY TRONG KHO RỒI!" has only the
        # green acknowledgement button. Both execute the same crop recovery.
        kind = "NOT_ENOUGH" if blue_ratio >= self.SHORTAGE_BLUE_RATIO_MIN else "LOW_STOCK"
        return kind, x_match, green_ratio

    def _raise_material_shortage(
        self,
        *,
        frame,
        material_template: str,
        material_label: str,
        production_item_id: str,
        production_label: str,
        ordinal: int,
        target_count: int,
        empty_before: int,
        count_empty,
        close_point: tuple[int, int],
    ) -> None:
        detected = self._shortage_modal(frame)
        if detected is None:
            return

        kind, x_match, green_ratio = detected

        # Close only the shortage popup first, then use the slot delta to decide
        # whether the drag that triggered LOW_STOCK had already been accepted.
        self.vision.driver.click(*x_match.center)
        self.waiter.sleep(0.25)
        try:
            current_empty = int(count_empty())
        except Exception:
            current_empty = int(empty_before)

        consumed = current_empty < int(empty_before)
        completed = int(ordinal) if consumed else int(ordinal) - 1
        completed = max(int(self._material_resume.queued), completed)
        completed = min(int(target_count), max(0, completed))
        self._material_resume.queued = completed
        self._material_resume.recovery_count += 1

        # Leave the camera on the known production floor but close the production
        # panel so RecoveryManager can perform a deterministic floor->main route.
        self.vision.driver.click(*close_point)
        self.waiter.sleep(0.25)

        evidence = MaterialShortageEvidence(
            shortage_kind=kind,
            green_ratio=round(float(green_ratio), 4),
            completed_count=completed,
            target_count=int(target_count),
            current_empty_slots=current_empty,
            drag_consumed_slot=bool(consumed),
        )
        self.context.stage("auto-production-material-shortage")
        self.context.log(
            f"AUTO {production_label} • BẮT LỖI CÂY={material_label} • "
            f"popup={kind} • green={green_ratio:.3f} • "
            f"gesture_accepted={str(consumed).lower()} • "
            f"đã_xếp={completed}/{target_count} • "
            f"còn={max(0, int(target_count) - completed)}"
        )
        raise MaterialShortage(
            material_template=material_template,
            material_label=material_label,
            production_item_id=production_item_id,
            production_label=production_label,
            completed_count=completed,
            target_count=int(target_count),
            evidence=evidence,
        )

    def _wait_for_remaining_capacity(
        self,
        *,
        slots,
        product_template: str,
        label: str,
        product_threshold: float,
        required_empty: int,
        fallback_top_point: tuple[int, int] | None,
    ) -> tuple[int, tuple[int, int], tuple[int, int]]:
        """Wait only for the capacity needed by the still-unqueued remainder."""
        required = max(0, int(required_empty))
        wait_round = 0
        product_misses = 0

        while True:
            self.context.ensure_running()
            warehouse_full, _empty_anchor = slots._panel_state()
            if warehouse_full:
                slots._raise_inventory_full(label)

            product = slots._find_product_match(
                product_template,
                threshold=product_threshold,
            )
            if product is None:
                product_misses += 1
                if product_misses == 1 or product_misses % 10 == 0:
                    self.context.log(
                        f"AUTO {label} resume • chưa thấy anchor {product_template} "
                        f"• misses={product_misses} • giữ panel và recheck"
                    )
                self.waiter.sleep(slots.PANEL_RECHECK_SECONDS)
                continue
            product_misses = 0

            empty = int(slots._count_empty_slots())
            if empty >= required:
                top = slots._find_top_empty_slot()
                top_point = (
                    top.center
                    if top is not None
                    else fallback_top_point
                )
                if top_point is None:
                    raise ScreenTimeout(
                        f"{label}: đã có {empty} ô trống nhưng không còn điểm thả "
                        "đã xác minh để resume production"
                    )
                self.context.log(
                    f"AUTO {label} resume READY • cần={required} ô • "
                    f"đang_trống={empty}/9 • tiếp tục đúng phần còn thiếu"
                )
                return empty, product.center, top_point

            wait_round += 1
            if wait_round == 1 or wait_round % 10 == 0:
                self.context.log(
                    f"AUTO {label} resume • cần tối thiểu {required} ô trống • "
                    f"hiện={empty}/9 • vòng={wait_round}"
                )
            self.waiter.sleep(slots.PANEL_RECHECK_SECONDS)


class MaterialAwareProductionActions(_MaterialShortageMixin, BaseProductionActions):
    """Táo sấy production with crop-aware shortage resume."""

    MATERIAL_TEMPLATE = "cay_tao"
    MATERIAL_LABEL = "Táo"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._init_material_resume()

    def _drag_dried_apple_with_retry(
        self,
        *,
        ordinal: int,
        product_point: tuple[int, int],
        top_point: tuple[int, int],
        empty_before: int,
    ) -> int:
        last_empty = int(empty_before)
        for drag_attempt in range(1, self.DRAG_ATTEMPTS + 1):
            self.context.ensure_running()
            self.vision.driver.swipe_points(
                (product_point, top_point),
                duration=0.02,
            )
            self.waiter.sleep(self.speed_config.vp_production_delay)

            for verify_round in range(1, self.VERIFY_RECHECKS + 1):
                self.context.ensure_running()
                frame = self.vision.frame()
                self._raise_material_shortage(
                    frame=frame,
                    material_template=self.MATERIAL_TEMPLATE,
                    material_label=self.MATERIAL_LABEL,
                    production_item_id=self.DRIED_APPLE_PRODUCTION_TEMPLATE,
                    production_label="Táo sấy",
                    ordinal=ordinal,
                    target_count=self.REQUIRED_COUNT,
                    empty_before=empty_before,
                    count_empty=self._count_empty_slots,
                    close_point=self.CLOSE_POINT,
                )

                current_empty = self._count_empty_slots()
                last_empty = current_empty
                if current_empty < empty_before:
                    if drag_attempt > 1 or verify_round > 1:
                        self.context.log(
                            f"AUTO Táo sấy • xếp {ordinal}/9 đã phục hồi sau recheck/retry "
                            f"• drag={drag_attempt}/{self.DRAG_ATTEMPTS} • "
                            f"verify={verify_round}/{self.VERIFY_RECHECKS} • "
                            f"ô trống {empty_before}→{current_empty}"
                        )
                    return current_empty
                if verify_round < self.VERIFY_RECHECKS:
                    self.waiter.sleep(self.VERIFY_RECHECK_SECONDS)

            if drag_attempt < self.DRAG_ATTEMPTS:
                self.context.log(
                    f"AUTO Táo sấy • xếp {ordinal}/9 chưa thấy ô trống giảm sau "
                    f"{self.VERIFY_RECHECKS} frame • thử lại gesture "
                    f"{drag_attempt + 1}/{self.DRAG_ATTEMPTS}"
                )
        return last_empty

    def _open_dryer_for_resume(
        self,
    ) -> tuple[int, tuple[int, int], tuple[int, int]]:
        remaining = max(0, self.REQUIRED_COUNT - self._material_resume.queued)
        if self._material_resume.queued <= 0:
            empty, product, top = self._open_verified_dryer()
            self._material_resume.first_empty_before = int(empty)
            self._material_resume.top_point = top
            return empty, product, top

        self._collect_finished_before_open()
        empty, product, top = self._wait_for_remaining_capacity(
            slots=self,
            product_template=self.DRIED_APPLE_PRODUCTION_TEMPLATE,
            label="Táo sấy",
            product_threshold=self.DRIED_APPLE_GUARD_THRESHOLD,
            required_empty=remaining,
            fallback_top_point=self._material_resume.top_point,
        )
        self._material_resume.top_point = top
        return empty, product, top

    def produce_9_dried_apples(
        self, *, close_after_success: bool = True
    ) -> ProductionResult:
        try:
            empty_now, product_point, top_point = self._open_dryer_for_resume()
            first_empty = (
                self._material_resume.first_empty_before
                if self._material_resume.first_empty_before is not None
                else int(empty_now)
            )
            self._material_resume.first_empty_before = int(first_empty)
            self._material_resume.top_point = top_point

            while self._material_resume.queued < self.REQUIRED_COUNT:
                ordinal = self._material_resume.queued + 1
                current_empty = self._drag_dried_apple_with_retry(
                    ordinal=ordinal,
                    product_point=product_point,
                    top_point=top_point,
                    empty_before=empty_now,
                )
                if current_empty >= empty_now:
                    self.vision.driver.click(*self.CLOSE_POINT)
                    raise ScreenTimeout(
                        "Kéo Táo sấy không làm giảm ô trống sau retry: "
                        f"lần={ordinal}/9, trước={empty_now}, sau={current_empty}"
                    )
                empty_now = current_empty
                self._material_resume.queued += 1
                self.context.log(
                    f"AUTO sản xuất • đã xác minh xếp Táo sấy "
                    f"{self._material_resume.queued}/9 • ô trống còn={empty_now}"
                )

            result = MaterialAwareProductionResult(
                item_id=self.DRIED_APPLE_PRODUCTION_TEMPLATE,
                requested_count=self.REQUIRED_COUNT,
                queued_count=self.REQUIRED_COUNT,
                empty_before=int(first_empty),
                empty_after=int(empty_now),
                verified_queue_events=self.REQUIRED_COUNT,
                material_recovery_count=self._material_resume.recovery_count,
            )
            if close_after_success:
                self.vision.driver.click(*self.CLOSE_POINT)
            else:
                self.context.log(
                    "AUTO sản xuất Táo sấy • giữ panel mở để bàn giao sang Sửa máy"
                )
            self.context.log(
                "AUTO sản xuất Táo sấy hoàn tất • verified_queue_events=9/9 • "
                f"material_recovery={self._material_resume.recovery_count}"
            )
            self._material_resume.reset()
            return result
        except MaterialShortage:
            raise
        except Exception:
            self._material_resume.reset()
            raise


class MaterialAwareAppleJuiceProductionActions(
    _MaterialShortageMixin,
    BaseAppleJuiceProductionActions,
):
    """Nước táo production with apple-shortage resume."""

    MATERIAL_TEMPLATE = "cay_tao"
    MATERIAL_LABEL = "Táo"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._init_material_resume()

    def _drag_one_with_retry(
        self,
        *,
        ordinal: int,
        product_point: tuple[int, int],
        top_point: tuple[int, int],
        empty_before: int,
    ) -> int:
        last_empty = int(empty_before)
        for drag_attempt in range(1, self.DRAG_ATTEMPTS + 1):
            self.context.ensure_running()
            self.vision.driver.swipe_points((product_point, top_point), duration=0.02)
            self.waiter.sleep(self.speed_config.vp_production_delay)

            for verify_round in range(1, self.VERIFY_RECHECKS + 1):
                self.context.ensure_running()
                frame = self.vision.frame()
                self._raise_material_shortage(
                    frame=frame,
                    material_template=self.MATERIAL_TEMPLATE,
                    material_label=self.MATERIAL_LABEL,
                    production_item_id=self.PRODUCT_TEMPLATE,
                    production_label="Nước táo",
                    ordinal=ordinal,
                    target_count=self.REQUIRED_COUNT,
                    empty_before=empty_before,
                    count_empty=self.slots._count_empty_slots,
                    close_point=self.CLOSE_POINT,
                )

                current = self.slots._count_empty_slots()
                last_empty = current
                if current < empty_before:
                    if drag_attempt > 1 or verify_round > 1:
                        self.context.log(
                            f"AUTO Nước táo • xếp {ordinal}/9 đã phục hồi sau recheck/retry "
                            f"• drag={drag_attempt}/{self.DRAG_ATTEMPTS} • "
                            f"verify={verify_round}/{self.VERIFY_RECHECKS} • "
                            f"ô trống {empty_before}→{current}"
                        )
                    return current
                if verify_round < self.VERIFY_RECHECKS:
                    self.waiter.sleep(self.VERIFY_RECHECK_SECONDS)

            if drag_attempt < self.DRAG_ATTEMPTS:
                self.context.log(
                    f"AUTO Nước táo • xếp {ordinal}/9 chưa thấy ô trống giảm sau "
                    f"{self.VERIFY_RECHECKS} frame • thử lại gesture "
                    f"{drag_attempt + 1}/{self.DRAG_ATTEMPTS}"
                )
        return last_empty

    def _open_for_resume(self):
        remaining = max(0, self.REQUIRED_COUNT - self._material_resume.queued)
        if self._material_resume.queued <= 0:
            empty, product, top = self._open_verified()
            self._material_resume.first_empty_before = int(empty)
            self._material_resume.top_point = top
            return empty, product, top

        self.slots._click_until_panel_open(
            machine_point=self.MACHINE_POINT,
            product_template=self.PRODUCT_TEMPLATE,
            label="Nước táo",
            product_threshold=0.70,
        )
        empty, product, top = self._wait_for_remaining_capacity(
            slots=self.slots,
            product_template=self.PRODUCT_TEMPLATE,
            label="Nước táo",
            product_threshold=0.70,
            required_empty=remaining,
            fallback_top_point=self._material_resume.top_point,
        )
        self._material_resume.top_point = top
        return empty, product, top

    def produce_9_apple_juices(
        self, *, close_after_success: bool = True
    ) -> ProductionResult:
        try:
            empty_now, product_point, top_point = self._open_for_resume()
            first_empty = (
                self._material_resume.first_empty_before
                if self._material_resume.first_empty_before is not None
                else int(empty_now)
            )
            self._material_resume.first_empty_before = int(first_empty)
            self._material_resume.top_point = top_point

            while self._material_resume.queued < self.REQUIRED_COUNT:
                ordinal = self._material_resume.queued + 1
                current = self._drag_one_with_retry(
                    ordinal=ordinal,
                    product_point=product_point,
                    top_point=top_point,
                    empty_before=empty_now,
                )
                if current >= empty_now:
                    self.vision.driver.click(*self.CLOSE_POINT)
                    raise ScreenTimeout(
                        f"Kéo Nước táo {ordinal}/9 không làm giảm ô trống sau retry: "
                        f"trước={empty_now}, sau={current}"
                    )
                empty_now = current
                self._material_resume.queued += 1
                self.context.log(
                    f"AUTO Nước táo • đã xác minh xếp "
                    f"{self._material_resume.queued}/9 • ô trống còn={empty_now}"
                )

            result = MaterialAwareProductionResult(
                item_id=self.PRODUCT_TEMPLATE,
                requested_count=self.REQUIRED_COUNT,
                queued_count=self.REQUIRED_COUNT,
                empty_before=int(first_empty),
                empty_after=int(empty_now),
                verified_queue_events=self.REQUIRED_COUNT,
                material_recovery_count=self._material_resume.recovery_count,
            )
            if close_after_success:
                self.vision.driver.click(*self.CLOSE_POINT)
            else:
                self.context.log("AUTO Nước táo • giữ panel mở để bàn giao sang Sửa máy")
            self.context.log(
                "AUTO sản xuất Nước táo hoàn tất • verified_queue_events=9/9 • "
                f"material_recovery={self._material_resume.recovery_count}"
            )
            self._material_resume.reset()
            return result
        except MaterialShortage:
            raise
        except Exception:
            self._material_resume.reset()
            raise


class MaterialAwareYellowFabricProductionActions(
    _MaterialShortageMixin,
    BaseYellowFabricProductionActions,
):
    """Vải vàng production with cotton-shortage resume."""

    MATERIAL_TEMPLATE = "cay_bong"
    MATERIAL_LABEL = "Bông"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._init_material_resume()

    def _drag_one_with_retry(
        self,
        *,
        ordinal: int,
        product_point: tuple[int, int],
        top_point: tuple[int, int],
        empty_before: int,
    ) -> int:
        last_empty = int(empty_before)
        for drag_attempt in range(1, self.DRAG_ATTEMPTS + 1):
            self.context.ensure_running()
            self.vision.driver.swipe_points((product_point, top_point), duration=0.02)
            self.waiter.sleep(self.speed_config.vp_production_delay)

            for verify_round in range(1, self.VERIFY_RECHECKS + 1):
                self.context.ensure_running()
                frame = self.vision.frame()
                self._raise_material_shortage(
                    frame=frame,
                    material_template=self.MATERIAL_TEMPLATE,
                    material_label=self.MATERIAL_LABEL,
                    production_item_id=self.PRODUCT_TEMPLATE,
                    production_label="Vải vàng",
                    ordinal=ordinal,
                    target_count=self.REQUIRED_COUNT,
                    empty_before=empty_before,
                    count_empty=self.slots._count_empty_slots,
                    close_point=self.CLOSE_POINT,
                )

                current = self.slots._count_empty_slots()
                last_empty = current
                if current < empty_before:
                    if drag_attempt > 1 or verify_round > 1:
                        self.context.log(
                            f"AUTO Vải vàng • xếp {ordinal}/9 đã phục hồi sau recheck/retry "
                            f"• drag={drag_attempt}/{self.DRAG_ATTEMPTS} • "
                            f"verify={verify_round}/{self.VERIFY_RECHECKS} • "
                            f"ô trống {empty_before}→{current}"
                        )
                    return current
                if verify_round < self.VERIFY_RECHECKS:
                    self.waiter.sleep(self.VERIFY_RECHECK_SECONDS)

            if drag_attempt < self.DRAG_ATTEMPTS:
                self.context.log(
                    f"AUTO Vải vàng • xếp {ordinal}/9 chưa thấy ô trống giảm sau "
                    f"{self.VERIFY_RECHECKS} frame • thử lại gesture "
                    f"{drag_attempt + 1}/{self.DRAG_ATTEMPTS}"
                )
        return last_empty

    def _open_for_resume(self):
        remaining = max(0, self.REQUIRED_COUNT - self._material_resume.queued)
        if self._material_resume.queued <= 0:
            empty, product, top = self._open_verified()
            self._material_resume.first_empty_before = int(empty)
            self._material_resume.top_point = top
            return empty, product, top

        self.slots._click_until_panel_open(
            machine_point=self.MACHINE_POINT,
            product_template=self.PRODUCT_TEMPLATE,
            label="Vải vàng",
            product_threshold=0.70,
        )
        empty, product, top = self._wait_for_remaining_capacity(
            slots=self.slots,
            product_template=self.PRODUCT_TEMPLATE,
            label="Vải vàng",
            product_threshold=0.70,
            required_empty=remaining,
            fallback_top_point=self._material_resume.top_point,
        )
        self._material_resume.top_point = top
        return empty, product, top

    def produce_9_yellow_fabrics(
        self, *, close_after_success: bool = True
    ) -> ProductionResult:
        try:
            empty_now, product_point, top_point = self._open_for_resume()
            first_empty = (
                self._material_resume.first_empty_before
                if self._material_resume.first_empty_before is not None
                else int(empty_now)
            )
            self._material_resume.first_empty_before = int(first_empty)
            self._material_resume.top_point = top_point

            while self._material_resume.queued < self.REQUIRED_COUNT:
                ordinal = self._material_resume.queued + 1
                current = self._drag_one_with_retry(
                    ordinal=ordinal,
                    product_point=product_point,
                    top_point=top_point,
                    empty_before=empty_now,
                )
                if current >= empty_now:
                    self._close_panel()
                    raise ScreenTimeout(
                        f"Kéo Vải vàng {ordinal}/9 không làm giảm ô trống sau retry: "
                        f"trước={empty_now}, sau={current}"
                    )
                empty_now = current
                self._material_resume.queued += 1
                self.context.log(
                    f"AUTO Vải vàng • đã xác minh xếp "
                    f"{self._material_resume.queued}/9 • ô trống còn={empty_now}"
                )

            result = MaterialAwareProductionResult(
                item_id=self.PRODUCT_TEMPLATE,
                requested_count=self.REQUIRED_COUNT,
                queued_count=self.REQUIRED_COUNT,
                empty_before=int(first_empty),
                empty_after=int(empty_now),
                verified_queue_events=self.REQUIRED_COUNT,
                material_recovery_count=self._material_resume.recovery_count,
            )
            if close_after_success:
                self._close_panel()
            else:
                self.context.log("AUTO Vải vàng • giữ panel mở để bàn giao sang Sửa máy")
            self.context.log(
                "AUTO sản xuất Vải vàng hoàn tất • verified_queue_events=9/9 • "
                f"material_recovery={self._material_resume.recovery_count}"
            )
            self._material_resume.reset()
            return result
        except MaterialShortage:
            raise
        except Exception:
            self._material_resume.reset()
            raise


class MaterialAwareCottonPlantingActions(BaseCottonPlantingActions):
    """Harvest at least one 27-cotton batch, then immediately replant it."""

    REPLENISH_TIMEOUT = 180.0

    def replenish_27_cotton_from_floor_1(self, timeout: float | None = None) -> int:
        deadline = time.monotonic() + float(timeout or self.REPLENISH_TIMEOUT)
        harvested = False
        cycle = 0

        while time.monotonic() < deadline:
            self.context.ensure_running()
            cycle += 1
            state, match = self._scan_first_pot_state(self.COTTON_TEMPLATE)

            if state == "RIPE":
                self.context.log(
                    "AUTO bổ sung Bông • cây chín READY • cào/thu hoạch 27 chậu"
                )
                self._harvest_27()
                harvested = True
                self.waiter.sleep(0.45)
                continue

            if state == "EMPTY" and match is not None:
                path = (match.center,) + self.rose_path()[1:]
                self.vision.driver.swipe_points(
                    path,
                    duration=self.speed_config.plant_harvest_duration,
                )
                self.waiter.sleep(0.40)
                self.vision.driver.click(*self.CLOSE_POINT)
                self.waiter.sleep(0.55)
                if harvested:
                    self.context.log(
                        "AUTO bổ sung Bông • đã thu 27 Bông và gieo lại đúng cay_bong"
                    )
                    return self.TREE_COUNT
                self.context.log(
                    "AUTO bổ sung Bông • ruộng đang trống • đã gieo 27 Bông • "
                    "chờ chín để thu một batch trước khi quay lại máy SX"
                )
                self.waiter.sleep(self.speed_config.crop_check_interval)
                continue

            # Growing/unknown: close the picker if it is open and wait instead of
            # failing after five rapid probes. A material recovery must eventually
            # bring an actual harvested batch back to inventory.
            self.vision.driver.click(*self.CLOSE_POINT)
            if cycle == 1 or cycle % 10 == 0:
                self.context.log(
                    "AUTO bổ sung Bông • cây chưa chín • "
                    f"đợi {self.speed_config.crop_check_interval:.3f}s • vòng={cycle}"
                )
            self.waiter.sleep(self.speed_config.crop_check_interval)

        raise ScreenTimeout(
            f"Hết {float(timeout or self.REPLENISH_TIMEOUT):.0f}s chờ Bông chín "
            "để bổ sung nguyên liệu"
        )


class MaterialAwareMachineRepairActions(BaseMachineRepairActions):
    """Accept per-gesture production proof when material recovery split the run."""

    def begin_from_open_panel(self, result: ProductionResult) -> MachineRepairHandoff:
        self.context.ensure_running()
        consumed = max(0, int(result.empty_before) - int(result.empty_after))
        requested = int(result.requested_count)
        queued = int(result.queued_count)
        verified_events = int(getattr(result, "verified_queue_events", 0) or 0)
        recovered = int(getattr(result, "material_recovery_count", 0) or 0)

        slot_delta_ok = consumed == requested
        event_proof_ok = verified_events == requested
        if requested <= 0 or queued != requested or not (slot_delta_ok or event_proof_ok):
            raise ScreenTimeout(
                "Không bàn giao sang Sửa máy vì hậu kiểm production chưa đủ: "
                f"item={result.item_id}, requested={requested}, queued={queued}, "
                f"slot_delta={consumed}, verified_queue_events={verified_events}"
            )

        self.context.stage("auto-machine-repair-handoff-ready")
        proof = "slot_delta" if slot_delta_ok else "verified_queue_events"
        self.context.log(
            "AUTO Sửa máy • production đã đủ và panel vẫn mở • "
            f"item={result.item_id} • số lượng={queued} • proof={proof} • "
            f"material_recovery={recovered}"
        )
        return MachineRepairHandoff(
            item_id=str(result.item_id),
            queued_count=queued,
            panel_open=True,
        )
