from __future__ import annotations

from dataclasses import dataclass
import math
import time

from ..errors import InsufficientBatch, NoEmptyStallSlot, ScreenTimeout, TransactionError
from ..actions.stall import VISIBLE_SLOT_CENTERS
from .auto_vp_sale import AutoVpSaleWorkflow


__all__ = [
    "WarehouseMaterial",
    "WarehouseSalePlan",
    "WarehouseUpgradeResult",
    "WarehouseUpgradeWorkflow",
]


@dataclass(frozen=True)
class WarehouseMaterial:
    item_id: str
    label: str
    group: int
    quantity: int


@dataclass(frozen=True)
class WarehouseSalePlan:
    mode: str
    fixed_batches: dict[str, int]
    drain_items: tuple[str, ...]
    quantities: dict[str, int]


@dataclass(frozen=True)
class WarehouseUpgradeResult:
    mode: str
    sold_batches: dict[str, int]
    quantities: dict[str, int]
    upgrade_arrow_seen: bool


class WarehouseUpgradeWorkflow:
    """Balance the six AUTO-PRO warehouse materials at an exact-main boundary."""

    MODE_WAREHOUSE_1 = "warehouse_1"
    MODE_WAREHOUSE_2 = "warehouse_2"
    MODE_BOTH = "both"
    MODE_MAX = "max"
    MODES = {MODE_WAREHOUSE_1, MODE_WAREHOUSE_2, MODE_BOTH, MODE_MAX}

    MATERIALS = (
        ("go", "Gỗ", 1),
        ("gach", "Gạch", 1),
        ("son_do", "Sơn đỏ", 1),
        ("dinh", "Đinh", 2),
        ("son_vang", "Sơn vàng", 2),
        ("da", "Đá", 2),
    )
    LABELS = {item_id: label for item_id, label, _group in MATERIALS}
    GROUPS = {
        1: tuple(item_id for item_id, _label, group in MATERIALS if group == 1),
        2: tuple(item_id for item_id, _label, group in MATERIALS if group == 2),
    }

    WAREHOUSE_ENTRY_POINT = (775, 810)
    STORAGE_3_POINT = (454, 515)
    UPGRADE_CATEGORY_POINT = (248, 712)
    INVENTORY_ZONE = (14, 345, 397, 379)
    LIST_SWIPE = (212, 630, 212, 558)
    MAX_SCAN_VIEWS = 6
    ITEM_THRESHOLD = 0.74
    ITEM_SCALES = (0.80, 0.90, 1.00, 1.10, 1.20)
    DIGIT_THRESHOLD = 0.78
    DELETE_DIAMOND_ZONE = (390, 490, 220, 100)
    SELECTED_ITEM_ZONE = (680, 240, 180, 180)

    def __init__(self, automation, *, mode: str) -> None:
        self.auto = automation
        self.context = automation.context
        selected = str(mode)
        if selected not in self.MODES:
            raise ValueError(f"Chế độ Nâng kho không hợp lệ: {selected}")
        self.mode = selected

    @staticmethod
    def build_plan(mode: str, quantities: dict[str, int]) -> WarehouseSalePlan:
        selected = str(mode)
        if selected not in WarehouseUpgradeWorkflow.MODES:
            raise ValueError(f"Chế độ Nâng kho không hợp lệ: {selected}")
        required = {item_id for item_id, _label, _group in WarehouseUpgradeWorkflow.MATERIALS}
        if set(quantities) != required:
            missing = sorted(required - set(quantities))
            extra = sorted(set(quantities) - required)
            raise ValueError(f"Bảng nguyên liệu chưa đủ: missing={missing}, extra={extra}")
        normalized = {key: max(0, int(value)) for key, value in quantities.items()}
        fixed: dict[str, int] = {}
        drain: tuple[str, ...] = ()
        if selected == WarehouseUpgradeWorkflow.MODE_WAREHOUSE_1:
            balance_group = WarehouseUpgradeWorkflow.GROUPS[1]
            drain = WarehouseUpgradeWorkflow.GROUPS[2]
        elif selected == WarehouseUpgradeWorkflow.MODE_WAREHOUSE_2:
            balance_group = WarehouseUpgradeWorkflow.GROUPS[2]
            drain = WarehouseUpgradeWorkflow.GROUPS[1]
        elif selected == WarehouseUpgradeWorkflow.MODE_BOTH:
            balance_group = ()
        else:
            balance_group = ()
            drain = WarehouseUpgradeWorkflow.GROUPS[1] + WarehouseUpgradeWorkflow.GROUPS[2]

        if balance_group:
            baseline = min(normalized[item_id] for item_id in balance_group)
            ceiling = baseline + 10
            for item_id in balance_group:
                excess = normalized[item_id] - ceiling
                fixed[item_id] = max(0, int(math.ceil(excess / 10.0)))

        return WarehouseSalePlan(
            mode=selected,
            fixed_batches=fixed,
            drain_items=tuple(drain),
            quantities=normalized,
        )

    def _open_upgrade_inventory(self) -> bool:
        if not self.auto.popup.is_own_exact_main_screen():
            raise ScreenTimeout("Nâng kho chỉ được mở từ exact MAIN")
        arrow = self.auto.vision.find(
            "nang_kho", threshold=0.78, click=False,
        )
        self.context.stage("auto-warehouse-upgrade-open-warehouse")
        self.auto.vision.driver.click(*self.WAREHOUSE_ENTRY_POINT)
        self.auto.wait.sleep(0.50)

        # ``kho_vat_dung`` is already visible as a side-tab template as soon as
        # the generic warehouse panel opens. It must never be used as a reason
        # to skip this required selection click.
        self.context.stage("auto-warehouse-upgrade-select-item-warehouse")
        self.auto.vision.driver.click(*self.STORAGE_3_POINT)
        self.auto.wait.sleep(0.50)

        self.context.stage("auto-warehouse-upgrade-select-upgrade-category")
        self.auto.vision.driver.click(*self.UPGRADE_CATEGORY_POINT)
        self.auto.wait.sleep(0.50)
        if self.auto.vision.find("kho_vat_dung", threshold=0.68) is None:
            raise ScreenTimeout("Không chứng minh được Kho vật dụng sau khi chọn tab nâng cấp")
        return arrow is not None

    def _read_quantity(self, frame, center: tuple[int, int]) -> int | None:
        """Read xNNN below one matched icon with AUTO-PRO digit templates."""
        # The quantity label is right-biased below the icon. The old 67px crop
        # clipped its final glyph in live 1000x1000 captures (142->14,
        # 138->13, 28->2), which inverted the balancing decision.
        logical = (center[0] - 42, center[1] + 12, 100, 42)
        candidates: list[tuple[float, int, int, int]] = []
        for digit in range(10):
            for suffix in ("", "_2", "_3"):
                for match in self.auto.vision.find_all(
                    f"{digit}{suffix}", threshold=self.DIGIT_THRESHOLD,
                    zone=logical, scales=(1.0,), frame=frame, maximum=6,
                ):
                    candidates.append(
                        (float(match.score), int(match.box[0]), digit, int(match.box[2]))
                    )
        candidates.sort(reverse=True)
        accepted: list[tuple[int, int]] = []
        for score, x0, digit, tw in candidates:
            if any(abs(x0 - prior_x) <= max(2, tw // 2) for prior_x, _ in accepted):
                continue
            accepted.append((x0, digit))
        accepted.sort()
        if not 1 <= len(accepted) <= 4:
            return None
        value = int("".join(str(digit) for _x, digit in accepted))
        return value

    def _scan_materials(self) -> dict[str, int]:
        found: dict[str, int] = {}
        for view in range(1, self.MAX_SCAN_VIEWS + 1):
            self.context.ensure_running()
            frame = self.auto.vision.frame()
            for item_id, label, _group in self.MATERIALS:
                if item_id in found:
                    continue
                match = self.auto.vision.find(
                    item_id,
                    threshold=self.ITEM_THRESHOLD,
                    zone=self.INVENTORY_ZONE,
                    scales=self.ITEM_SCALES,
                    click=False,
                    frame=frame,
                )
                if match is None:
                    continue
                first = self._read_quantity(frame, match.center)
                self.auto.wait.sleep(0.12)
                fresh = self.auto.vision.frame()
                confirm = self.auto.vision.find(
                    item_id,
                    threshold=self.ITEM_THRESHOLD,
                    zone=self.INVENTORY_ZONE,
                    scales=self.ITEM_SCALES,
                    click=False,
                    frame=fresh,
                )
                second = self._read_quantity(fresh, confirm.center) if confirm else None
                if first is None or second is None or first != second:
                    continue
                found[item_id] = first
                self.context.log(f"AUTO Nâng kho • check {label}={first} • verified=2-frame")
            if len(found) == len(self.MATERIALS):
                return found
            if view < self.MAX_SCAN_VIEWS:
                self.auto.vision.driver.swipe(*self.LIST_SWIPE, duration=0.30)
                self.auto.wait.sleep(0.45)
        missing = [self.LABELS[item_id] for item_id, _label, _group in self.MATERIALS if item_id not in found]
        raise ScreenTimeout("Không quét đủ 6 nguyên liệu nâng kho: " + ", ".join(missing))

    def _close_inventory_to_main(self) -> None:
        # Driver key name ``back`` maps to the physical ESC key on ClientJS.
        self.auto.vision.driver.press("back")
        self.auto.wait.sleep(0.45)
        if not self.auto.popup.is_own_main_screen():
            raise ScreenTimeout("ESC một lần nhưng chưa trở về MAIN sau check kho")

    def _delete_one_listing_for_slot(self) -> None:
        frame = self.auto.vision.frame()
        target = None
        for index, center in enumerate(VISIBLE_SLOT_CENTERS, start=1):
            if self.auto.stall.listing_is_available(frame, index):
                target = center
                break
        if target is None:
            raise NoEmptyStallSlot("View 1 không có ô VP hợp lệ để xóa bằng KC")
        self.auto.vision.driver.click(*target)
        self.auto.wait.sleep(0.35)
        delete = self.auto.vision.find(
            "xoa_vp_kc", threshold=0.76, zone=self.DELETE_DIAMOND_ZONE, click=True,
        )
        if delete is None:
            raise TransactionError("Không chứng minh được nút xóa VP bằng 1 KC")
        self.auto.wait.sleep(0.25)
        self.auto.vision.find("dong_y", threshold=0.74, click=True)
        self.auto.wait.sleep(0.45)
        if self.auto.selling.find_empty_slot(click=False) is None:
            raise TransactionError("Đã xóa VP bằng KC nhưng chưa có ô trống")
        self.context.log("AUTO Nâng kho • đã dùng 1 KC tạo một ô trống tại View 1")

    def _open_material_picker(self) -> None:
        empty = self.auto.selling.find_empty_slot(click=False)
        if empty is None:
            self._delete_one_listing_for_slot()
            empty = self.auto.selling.find_empty_slot(click=False)
        if empty is None:
            raise NoEmptyStallSlot("Không tạo được ô trống cho bán nguyên liệu nâng kho")
        self.auto.vision.driver.click(*empty.center)
        self.auto.inventory.wait_storage_picker_ready(timeout=3.0)
        self.auto.inventory.select_storage_after_picker_ready(3)
        self.auto.vision.driver.click(*self.UPGRADE_CATEGORY_POINT)
        self.auto.wait.sleep(0.50)

    def _sell_one_batch(self, item_id: str) -> bool:
        self._open_material_picker()
        frame = self.auto.vision.frame()
        match = self.auto.vision.find(
            item_id, threshold=self.ITEM_THRESHOLD, zone=self.INVENTORY_ZONE,
            scales=self.ITEM_SCALES, click=False, frame=frame,
        )
        if match is None:
            self.auto.selling.close_inventory_read_only()
            return False
        self.auto.vision.driver.click(*match.center)
        self.auto.wait.sleep(0.50)
        try:
            self.auto.selling.wait_sale_dialog_ready(
                timeout=4.0,
                description=f"dialog bán {self.LABELS[item_id]}",
            )
        except ScreenTimeout as exc:
            self.auto.selling._cancel_dialog()
            raise TransactionError(
                f"{self.LABELS[item_id]} không mở được dialog bán"
            ) from exc
        selected_passes = 0
        for attempt in range(1, 4):
            selected = self.auto.vision.find(
                item_id, threshold=0.72, zone=self.SELECTED_ITEM_ZONE,
                scales=self.ITEM_SCALES, click=False,
            )
            selected_passes = selected_passes + 1 if selected is not None else 0
            if selected_passes >= 2:
                break
            if attempt < 3:
                self.auto.wait.sleep(0.20)
        if selected_passes < 2:
            self.auto.selling._cancel_dialog()
            raise TransactionError(f"Dialog chưa chứng minh đúng {self.LABELS[item_id]}")
        native = self.auto.selling.native_size()
        if native == (500, 500):
            exact_threshold = 0.78
            exact_scales = (0.75, 0.90, 1.00, 1.10, 1.25, 1.40, 1.55)
        else:
            exact_threshold = 0.95
            exact_scales = (1.00,)
        quantity_passes = 0
        best_quantity = 0.0
        fast_ready = False
        for attempt in range(1, 4):
            quantity = self.auto.vision.find(
                "sl10", threshold=exact_threshold, zone=self.auto.selling.SL10_ZONE,
                scales=exact_scales, click=False,
            )
            if quantity is None:
                quantity_passes = 0
            else:
                quantity_passes += 1
                best_quantity = max(best_quantity, float(quantity.score))
                fast_ready = native == (1000, 1000) and quantity.score >= 0.99
            if fast_ready or quantity_passes >= 2:
                break
            if attempt < 3:
                self.auto.wait.sleep(0.20)
        if not fast_ready and quantity_passes < 2:
            self.auto.selling._cancel_dialog()
            self.auto.selling.close_inventory_read_only(timeout=3.0)
            return False
        self.auto.vision.driver.click(*self.auto.selling.PLACE_BUTTON)
        self.auto.wait.settle(0.25)
        self.auto.vision.find("dong_y", threshold=0.74, zone=self.auto.selling.CONFIRM_ZONE, click=True)
        self.auto.selling.wait_own_stall_ready(
            timeout=5.0, required_passes=1,
            description="quầy sau bán nguyên liệu nâng kho",
        )
        self.context.log(
            f"AUTO Nâng kho • đã bán {self.LABELS[item_id]} x10 • "
            f"quantity_score={best_quantity:.3f}"
        )
        return True

    def _execute_plan(self, plan: WarehouseSalePlan) -> dict[str, int]:
        sold = {item_id: 0 for item_id, _label, _group in self.MATERIALS}
        sale_entry = AutoVpSaleWorkflow(self.auto, function_id="function_1")
        sale_entry._require_sale_entry_main(timeout=15.0)
        sale_entry._open_own_stall_from_exact_main()
        try:
            self.auto.stall.collect_own_stall_gold(maximum=8)
            for item_id, batches in plan.fixed_batches.items():
                for _ in range(int(batches)):
                    if not self._sell_one_batch(item_id):
                        raise InsufficientBatch(
                            f"{self.LABELS[item_id]} không còn x10 trước số lượt đã chốt"
                        )
                    sold[item_id] += 1
            for item_id in plan.drain_items:
                while self._sell_one_batch(item_id):
                    sold[item_id] += 1
        finally:
            self.auto.stall.close_own_stall()
        return sold

    def run(self) -> WarehouseUpgradeResult:
        self.context.stage("auto-warehouse-upgrade-start")
        arrow_seen = self._open_upgrade_inventory()
        quantities = self._scan_materials()
        plan = self.build_plan(self.mode, quantities)
        fixed_text = ", ".join(
            f"{self.LABELS[key]}={value} lượt" for key, value in plan.fixed_batches.items()
            if value > 0
        ) or "không cần cân bằng"
        drain_text = ", ".join(self.LABELS[key] for key in plan.drain_items) or "không"
        self.context.log(
            f"AUTO Nâng kho • phương án CHỐT • mode={self.mode} • "
            f"cân_bằng=[{fixed_text}] • bán_đến_dưới_x10=[{drain_text}]"
        )
        self._close_inventory_to_main()
        sold = self._execute_plan(plan) if plan.fixed_batches or plan.drain_items else {
            item_id: 0 for item_id, _label, _group in self.MATERIALS
        }
        self.context.stage("auto-warehouse-upgrade-finished")
        return WarehouseUpgradeResult(
            mode=self.mode,
            sold_batches=sold,
            quantities=quantities,
            upgrade_arrow_seen=arrow_seen,
        )
