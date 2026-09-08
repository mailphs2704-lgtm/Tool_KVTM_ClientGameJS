from __future__ import annotations

from dataclasses import dataclass

from ..context import AutomationContext
from ..errors import ScreenTimeout
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter
from .production import ProductionResult


__all__ = [
    "MachineRepairActions",
    "MachineRepairHandoff",
    "MachineRepairTestResult",
]
FILE_FUNCTIONS = (
    "Nhận bàn giao từ panel máy đang mở sau khi đã kéo đủ số lượng VP",
    "Chỉ cho phép vào luồng Sửa máy khi hậu kiểm production đã đủ chính xác",
    "Giữ panel máy mở để bước Sửa máy tiếp theo không phải mở lại máy",
    "Test riêng luồng ? → Sửa máy → đóng modal ngay từ panel sản xuất VP đang mở",
    "Không đọc/OCR giá sửa máy vì số tiền thay đổi theo trạng thái máy",
    "Hậu kiểm modal mở, vùng Độ bền thay đổi và modal đóng trước khi báo PASS",
    "Fail-close về logic nếu số lượng/hậu kiểm không khớp, không thao tác mù",
)


@dataclass(frozen=True)
class MachineRepairHandoff:
    item_id: str
    queued_count: int
    panel_open: bool


@dataclass(frozen=True)
class MachineRepairTestResult:
    modal_open_change: float
    durability_change: float
    repair_button_change: float
    modal_close_change: float


class MachineRepairActions:
    """Machine repair actions isolated from the proven production workflows.

    Runtime integration for Function 2 still starts from a verified production
    handoff. The DEV test below is intentionally narrower: the operator places
    ClientJS at an already-open production panel and the module tests only the
    repair UI sequence supplied from live screenshots.
    """

    # Logical ClientJS coordinates are 0..1000. These points come from the
    # supplied 1000x1000 live screenshots, not from the variable repair price.
    OPEN_REPAIR_POINT = (165, 856)
    REPAIR_BUTTON_POINT = (730, 596)
    CLOSE_MODAL_POINT = (652, 284)

    # Geometry-only verification. No OCR and no dependency on a displayed cost
    # such as 37, because that value legitimately changes between machines/runs.
    MODAL_ZONE = (335, 270, 335, 455)
    DURABILITY_ZONE = (355, 565, 295, 55)
    REPAIR_BUTTON_ZONE = (650, 555, 145, 85)
    MIN_MODAL_CHANGE = 5.0
    MIN_REPAIR_CHANGE = 0.75
    MIN_CLOSE_CHANGE = 5.0

    def __init__(
        self,
        context: AutomationContext,
        vision: VisionEngine,
        waiter: Waiter,
    ) -> None:
        self.context = context
        self.vision = vision
        self.waiter = waiter

    @staticmethod
    def _mean_zone_change(before, after, zone: tuple[int, int, int, int]) -> float:
        """Mean absolute pixel change for one logical 0..1000 screen zone."""
        if before is None or after is None or before.shape[:2] != after.shape[:2]:
            return 0.0
        height, width = before.shape[:2]
        x, y, logical_width, logical_height = zone
        left = max(0, min(width, round(x * width / 1000)))
        top = max(0, min(height, round(y * height / 1000)))
        right = max(left + 1, min(width, round((x + logical_width) * width / 1000)))
        bottom = max(top + 1, min(height, round((y + logical_height) * height / 1000)))
        before_roi = before[top:bottom, left:right]
        after_roi = after[top:bottom, left:right]
        if before_roi.size == 0 or before_roi.shape != after_roi.shape:
            return 0.0
        return float(
            abs(before_roi.astype("float32") - after_roi.astype("float32")).mean()
        )

    def test_from_open_production_panel(self) -> MachineRepairTestResult:
        """DEV-only test beginning exactly at an already-open production panel.

        Sequence:
        1. Click the circled ? repair entry on the production panel.
        2. Require a strong center-modal screen change.
        3. Click the fixed repair-button area; never inspect the numeric price.
        4. Require the durability/button region to change.
        5. Close the repair modal with its red X and require the modal to vanish.
        """
        self.context.ensure_running()
        self.context.stage("auto-machine-repair-test-start")
        self.context.log(
            "TEST Sửa máy • bắt đầu tại panel sản xuất VP đang mở • "
            "không chạy production, không đọc giá sửa"
        )

        panel_frame = self.vision.frame()
        self.vision.driver.click(*self.OPEN_REPAIR_POINT)
        self.waiter.sleep(0.65)
        modal_frame = self.vision.frame()
        modal_open_change = self._mean_zone_change(
            panel_frame, modal_frame, self.MODAL_ZONE
        )
        if modal_open_change < self.MIN_MODAL_CHANGE:
            raise ScreenTimeout(
                "TEST Sửa máy: bấm ? nhưng chưa xác minh được modal Sửa máy mở "
                f"(change={modal_open_change:.2f})"
            )

        self.context.log(
            "TEST Sửa máy • modal đã mở • "
            f"screen_change={modal_open_change:.2f}"
        )
        modal_opened = True
        try:
            self.context.ensure_running()
            self.vision.driver.click(*self.REPAIR_BUTTON_POINT)
            self.waiter.sleep(0.75)
            repaired_frame = self.vision.frame()
            durability_change = self._mean_zone_change(
                modal_frame, repaired_frame, self.DURABILITY_ZONE
            )
            repair_button_change = self._mean_zone_change(
                modal_frame, repaired_frame, self.REPAIR_BUTTON_ZONE
            )
            if max(durability_change, repair_button_change) < self.MIN_REPAIR_CHANGE:
                raise ScreenTimeout(
                    "TEST Sửa máy: đã bấm vùng nút Sửa nhưng UI không thay đổi; "
                    "không xác nhận đã sửa "
                    f"(durability={durability_change:.2f}, "
                    f"button={repair_button_change:.2f})"
                )

            self.context.log(
                "TEST Sửa máy • nút Sửa đã phản hồi • "
                f"độ_bền_change={durability_change:.2f} • "
                f"button_change={repair_button_change:.2f}"
            )

            self.context.ensure_running()
            self.vision.driver.click(*self.CLOSE_MODAL_POINT)
            self.waiter.sleep(0.65)
            closed_frame = self.vision.frame()
            modal_close_change = self._mean_zone_change(
                repaired_frame, closed_frame, self.MODAL_ZONE
            )
            if modal_close_change < self.MIN_CLOSE_CHANGE:
                raise ScreenTimeout(
                    "TEST Sửa máy: bấm X nhưng chưa xác minh modal đã đóng "
                    f"(change={modal_close_change:.2f})"
                )
            modal_opened = False

            result = MachineRepairTestResult(
                modal_open_change=modal_open_change,
                durability_change=durability_change,
                repair_button_change=repair_button_change,
                modal_close_change=modal_close_change,
            )
            self.context.stage("auto-machine-repair-test-pass")
            self.context.log(
                "PASS | TEST Sửa máy • ? → Sửa → X hoàn tất • "
                "giá hiển thị không được dùng làm điều kiện"
            )
            return result
        except Exception:
            # Once the modal has definitely opened, recover to a predictable UI
            # before propagating FAIL. Do not click X if the initial ? gate failed.
            if modal_opened:
                try:
                    self.vision.driver.click(*self.CLOSE_MODAL_POINT)
                    self.waiter.sleep(0.35)
                except Exception:
                    pass
            raise

    def begin_from_open_panel(self, result: ProductionResult) -> MachineRepairHandoff:
        self.context.ensure_running()
        consumed = max(0, int(result.empty_before) - int(result.empty_after))
        requested = int(result.requested_count)
        queued = int(result.queued_count)
        if requested <= 0 or queued != requested or consumed != requested:
            raise ScreenTimeout(
                "Không bàn giao sang Sửa máy vì hậu kiểm production chưa đủ: "
                f"item={result.item_id}, requested={requested}, queued={queued}, "
                f"slot_delta={consumed}"
            )

        self.context.stage("auto-machine-repair-handoff-ready")
        self.context.log(
            "AUTO Sửa máy • production đã đủ và panel vẫn mở • "
            f"item={result.item_id} • số lượng={queued} • chờ bước vào Sửa máy"
        )
        return MachineRepairHandoff(
            item_id=str(result.item_id),
            queued_count=queued,
            panel_open=True,
        )
