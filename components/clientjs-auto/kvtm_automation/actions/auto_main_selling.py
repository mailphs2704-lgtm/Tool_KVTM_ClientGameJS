from __future__ import annotations

from dataclasses import dataclass
import time

from ..errors import ScreenTimeout, TransactionError
from .item_recognition import AutoVpRecognitionActions, VpRecognition
from .selling import SellingActions, _mean_difference


__all__ = ["AutoSaleAttempt", "AutoMainSellingActions"]
FILE_FUNCTIONS = (
    "Bắt buộc OWN_STALL READY trước khi tìm ô trống",
    "Native 1000 cho phép OWN_STALL/x10 một-pass khi fresh score >=0.99; score thấp hơn giữ hai-pass cũ",
    "Nhận diện ô trống READ-ONLY rồi click đúng một lần",
    "Chờ picker Kho thành state READY; tuyệt đối không retry click ô trống",
    "Chọn storage2 bằng contract 500 hoặc baseline 1000 theo native ClientJS",
    "Quét fresh frame đúng VP được Function hiện tại cho phép mà không toggle bảng Kho",
    "Chỉ chọn VP được Function hiện tại cho phép",
    "Dùng x10 proof riêng cho native 500 và native 1000",
    "Hủy dialog rồi khôi phục picker bằng state proof, không đoán theo một icon",
    "Xác minh sale dialog + selected item + x10 trước Đặt bán",
    "Sau screen-change bắt buộc POST_SALE OWN_STALL READY trước listing tiếp theo",
    "Giữ nguyên toàn bộ threshold/scale native 500",
)


@dataclass(frozen=True)
class AutoSaleAttempt:
    status: str
    item_id: str = ""
    label: str = ""
    score: float = 0.0


class AutoMainSellingActions:
    """State-driven exact-x10 AUTO sale for both native 500 and native 1000."""

    ITEM_ORDER = ("tao_say", "vai_vang")
    SELECTED_ITEM_TEMPLATES = {
        "tao_say": "tao_say",
        "vai_vang": "vai_vang",
        "tinh_dau_hh": "tinh_dau_hh",
        "nuoc_hoa_hong": "nuoc_hoa_hong",
        "tra_da": "tra_da",
    }
    SELECTED_ITEM_FALLBACK_TEMPLATES = {
        "tra_da": ("kho_tra_da",),
    }
    SELECTED_ITEM_ZONE = (680, 240, 180, 180)
    SALE_CHANGE_ZONE = (180, 330, 640, 430)

    N500_EXACT_TEN_THRESHOLD = 0.78
    N500_EXACT_TEN_SCALES = (0.75, 0.90, 1.00, 1.10, 1.25, 1.40, 1.55)
    N1000_EXACT_TEN_THRESHOLD = 0.95
    N1000_EXACT_TEN_SCALES = (1.00,)
    N1000_FAST_CONFIDENCE_THRESHOLD = 0.99
    SELECTED_ITEM_THRESHOLD = 0.78
    SELECTED_ITEM_REQUIRED_PASSES = 2
    SELECTED_ITEM_SCAN_ATTEMPTS = 3
    EXACT_TEN_REQUIRED_PASSES = 2
    FINISHED_GOODS_SCAN_ATTEMPTS = 3
    SALE_PICKER_READY_TIMEOUT = 3.0
    POST_SALE_OWN_STALL_TIMEOUT = 5.0

    def __init__(
        self,
        selling: SellingActions,
        recognition: AutoVpRecognitionActions,
        *,
        item_order: tuple[str, ...] | None = None,
    ) -> None:
        self.selling = selling
        self.recognition = recognition
        self.context = selling.context
        requested = tuple(item_order or type(self).ITEM_ORDER)
        if not requested:
            raise ValueError("AUTO bán VP cần ít nhất một VP được Function cho phép")
        unsupported = [
            item_id for item_id in requested
            if item_id not in self.SELECTED_ITEM_TEMPLATES
        ]
        if unsupported:
            raise ValueError(
                "AUTO bán VP chưa có hậu kiểm an toàn cho: " + ", ".join(unsupported)
            )
        self.ITEM_ORDER = requested
        self._next_item_index = 0
        self._insufficient_item_ids: set[str] = set()
        self._unsafe_item_ids: set[str] = set()

    def _native_size(self) -> tuple[int, int]:
        return self.selling.native_size()

    def _exact_ten_profile(self) -> tuple[float, tuple[float, ...], str]:
        if self._native_size() == (500, 500):
            return (
                self.N500_EXACT_TEN_THRESHOLD,
                self.N500_EXACT_TEN_SCALES,
                "500-table",
            )
        return (
            self.N1000_EXACT_TEN_THRESHOLD,
            self.N1000_EXACT_TEN_SCALES,
            "1000-table",
        )

    def _wait_own_stall_ready_auto(
        self,
        *,
        timeout: float,
        description: str,
    ):
        """Fast-path only a near-perfect native-1000 own-stall proof.

        Native 500 never enters this path. A native-1000 score below 0.99 also
        falls back to the existing two-consecutive-proof contract unchanged.
        """
        native = self._native_size()
        if native == (1000, 1000):
            self.context.ensure_running()
            frame = self.selling.vision.frame()
            marker = self.selling.vision.find(
                "quay_hang_on",
                threshold=self.N1000_FAST_CONFIDENCE_THRESHOLD,
                zone=self.selling.OWN_STALL_ACTIVE_ZONE,
                click=False,
                frame=frame,
            )
            dialog_open = self.selling.is_sale_dialog_ready(frame=frame)
            if marker is not None and not dialog_open:
                self.context.log(
                    "AUTO bán VP • OWN_STALL FAST READY • "
                    f"native=1000x1000 • score={marker.score:.3f} • "
                    f"fast_threshold={self.N1000_FAST_CONFIDENCE_THRESHOLD:.2f}"
                )
                return marker

        return self.selling.wait_own_stall_ready(
            timeout=timeout,
            required_passes=2,
            description=description,
        )

    def _sale_change_crop(self):
        frame = self.selling.vision.frame()
        x, y, width, height = self.selling.vision.logical_zone_to_frame(
            self.SALE_CHANGE_ZONE, frame
        )
        return frame[y : y + height, x : x + width].copy()

    def _open_empty_slot_picker_verified(self) -> bool:
        """OWN_STALL -> EMPTY_SLOT -> PICKER with exactly one slot click."""
        self.context.ensure_running()
        try:
            own = self._wait_own_stall_ready_auto(
                timeout=4.0,
                description="OWN_STALL trước mở Kho",
            )
        except ScreenTimeout:
            self.context.log(
                "AUTO bán VP • OWN_STALL chưa READY • không click ô trống"
            )
            return False

        empty = self.selling.find_empty_slot(click=False)
        if empty is None:
            self.context.log(
                "AUTO bán VP • OWN_STALL READY nhưng không còn ô trống"
            )
            return False

        native = self._native_size()
        self.context.log(
            "AUTO bán VP • EMPTY_SLOT click-once • "
            f"native={native[0]}x{native[1]} • center={empty.center} • "
            f"score={empty.score:.3f} • own_stall={own.score:.3f}"
        )
        self.selling.vision.driver.click(*empty.center)

        try:
            self.selling.inventory.wait_storage_picker_ready(
                timeout=self.SALE_PICKER_READY_TIMEOUT,
            )
        except ScreenTimeout:
            self.context.log(
                "AUTO bán VP • PICKER không READY sau EMPTY_SLOT click-once • "
                "không click lần hai; khôi phục quầy"
            )
            self.selling.close_inventory_read_only(timeout=3.0)
            return False

        self.context.log(
            "AUTO bán VP • PICKER READY sau EMPTY_SLOT click-once • "
            f"native={native[0]}x{native[1]}"
        )
        return True

    def _open_and_scan_finished_goods(self) -> tuple[VpRecognition, ...]:
        """Picker proven -> storage2 proven/click-once -> fresh Function VP scans."""
        basket_button = (450, 442)
        self.context.ensure_running()
        change = self.selling.inventory.select_storage_after_picker_ready(2)
        native = self._native_size()
        self.context.log(
            "AUTO bán VP • Kho thành phẩm STORAGE2 READY • "
            f"native={native[0]}x{native[1]} • content_change={change:.2f} • "
            f"scan_fresh_frames={self.FINISHED_GOODS_SCAN_ATTEMPTS} • "
            f"items={','.join(self.ITEM_ORDER)}"
        )
        self.selling.waiter.sleep(0.20)

        best_by_id: dict[str, VpRecognition] = {}
        for attempt in range(1, self.FINISHED_GOODS_SCAN_ATTEMPTS + 1):
            self.context.ensure_running()
            if attempt > 1:
                self.selling.waiter.sleep(0.40)
            for item in self.recognition.scan_samples(
                log_prefix="AUTO SELL VP",
                item_ids=self.ITEM_ORDER,
            ):
                if not item.found or item.center is None:
                    continue
                previous = best_by_id.get(item.item_id)
                if previous is None or item.score > previous.score:
                    best_by_id[item.item_id] = item
            if best_by_id:
                self.context.log(
                    "AUTO bán VP • Kho thành phẩm scan PASS • "
                    f"frame={attempt}/{self.FINISHED_GOODS_SCAN_ATTEMPTS} • "
                    f"candidates={len(best_by_id)}"
                )
                return tuple(best_by_id.values())
            self.context.detail(
                "AUTO bán VP • Kho thành phẩm fresh-frame MISS • "
                f"frame={attempt}/{self.FINISHED_GOODS_SCAN_ATTEMPTS} • "
                "không toggle/click lại storage2"
            )
        return ()

    def _next_candidate(
        self,
        recognized: tuple[VpRecognition, ...],
    ) -> VpRecognition | None:
        by_id = {item.item_id: item for item in recognized}
        for offset in range(len(self.ITEM_ORDER)):
            index = (self._next_item_index + offset) % len(self.ITEM_ORDER)
            item_id = self.ITEM_ORDER[index]
            if item_id in self._insufficient_item_ids or item_id in self._unsafe_item_ids:
                continue
            item = by_id.get(item_id)
            if item is None:
                continue
            self._next_item_index = index
            return item
        return None

    def _cancel_selected_item(self) -> None:
        """Close sale dialog and restore storage2 without guessing picker state."""
        for attempt in range(1, 4):
            self.context.ensure_running()
            close_match = self.selling.vision.find_any(
                ("close_game", "close", "x_popup_event"),
                threshold=0.72,
                zone=(930, 0, 70, 70),
                click=True,
            )
            if close_match is None:
                self.selling.vision.driver.click(968, 28)
            self.selling.waiter.sleep(0.35)

            if self.selling.is_sale_dialog_ready():
                continue

            if self.selling.inventory.is_storage_picker_ready():
                self.selling.inventory.select_storage_after_picker_ready(2)
                self.context.log(
                    f"AUTO bán VP • CANCEL -> PICKER/STORAGE2 READY • lần {attempt}/3"
                )
                return

            try:
                self.selling.wait_own_stall_ready(
                    timeout=1.5,
                    required_passes=1,
                    description="quầy sau hủy dialog",
                )
            except ScreenTimeout:
                continue
            empty = self.selling.find_empty_slot(click=False)
            if empty is None:
                continue
            self.context.log(
                "AUTO bán VP • CANCEL recovery EMPTY_SLOT click-once • "
                f"center={empty.center}"
            )
            self.selling.vision.driver.click(*empty.center)
            try:
                self.selling.inventory.wait_storage_picker_ready(
                    timeout=self.SALE_PICKER_READY_TIMEOUT,
                )
                self.selling.inventory.select_storage_after_picker_ready(2)
            except ScreenTimeout:
                continue
            self.context.log(
                f"AUTO bán VP • đã hủy dialog và khôi phục STORAGE2 • lần {attempt}/3"
            )
            return
        raise ScreenTimeout(
            "Không hủy và khôi phục được kho bán VP; dừng trước khi thao tác tiếp"
        )

    def _place_exact_ten(self, item: VpRecognition) -> str:
        assert item.center is not None
        self.selling.vision.driver.click(*item.center)
        self.selling.waiter.sleep(0.30)
        try:
            self.selling.wait_sale_dialog_ready(
                timeout=4.0,
                description="màn hình đặt bán AUTO",
            )
        except ScreenTimeout as exc:
            self.selling._cancel_dialog()
            raise TransactionError(
                f"{item.label} không mở được màn hình đặt bán"
            ) from exc

        selected_templates = (
            self.SELECTED_ITEM_TEMPLATES[item.item_id],
            *self.SELECTED_ITEM_FALLBACK_TEMPLATES.get(item.item_id, ()),
        )
        selected_match = None
        selected_passes = 0
        best_selected_score = 0.0
        for selected_attempt in range(1, self.SELECTED_ITEM_SCAN_ATTEMPTS + 1):
            self.context.ensure_running()
            frame = self.selling.vision.frame()
            frame_best = None
            frame_template = ""
            for selected_template in selected_templates:
                candidate = self.selling.vision.find(
                    selected_template,
                    threshold=self.SELECTED_ITEM_THRESHOLD,
                    zone=self.SELECTED_ITEM_ZONE,
                    scales=(0.85, 1.0, 1.15, 1.30, 1.45),
                    click=False,
                    frame=frame,
                )
                if candidate is not None and (
                    frame_best is None or candidate.score > frame_best.score
                ):
                    frame_best = candidate
                    frame_template = selected_template
            if frame_best is None:
                selected_passes = 0
                self.context.detail(
                    "AUTO sale selected-item proof | "
                    f"item={item.item_id} | attempt={selected_attempt}/"
                    f"{self.SELECTED_ITEM_SCAN_ATTEMPTS} | passes reset=0 | "
                    f"templates={','.join(selected_templates)}"
                )
            else:
                selected_match = frame_best
                selected_passes += 1
                best_selected_score = max(
                    best_selected_score, float(frame_best.score)
                )
                self.context.detail(
                    "AUTO sale selected-item proof | "
                    f"item={item.item_id} | attempt={selected_attempt}/"
                    f"{self.SELECTED_ITEM_SCAN_ATTEMPTS} | "
                    f"passes={selected_passes}/"
                    f"{self.SELECTED_ITEM_REQUIRED_PASSES} | "
                    f"template={frame_template} | score={frame_best.score:.3f} | "
                    f"threshold={self.SELECTED_ITEM_THRESHOLD:.2f}"
                )
            if selected_passes >= self.SELECTED_ITEM_REQUIRED_PASSES:
                break
            if selected_attempt < self.SELECTED_ITEM_SCAN_ATTEMPTS:
                self.selling.waiter.sleep(0.20)

        if (
            selected_match is None
            or selected_passes < self.SELECTED_ITEM_REQUIRED_PASSES
        ):
            self.context.log(
                f"AUTO bán VP • CHẶN SAI VP: dialog chưa chứng minh ổn định "
                f"{item.label} • best_score={best_selected_score:.3f} • "
                f"threshold={self.SELECTED_ITEM_THRESHOLD:.2f} • "
                "hủy và chuyển VP kế tiếp"
            )
            self._cancel_selected_item()
            return "WRONG_ITEM"

        self.context.log(
            f"AUTO bán VP • selected-item STABLE READY • item={item.label} • "
            f"passes={selected_passes}/{self.SELECTED_ITEM_REQUIRED_PASSES} • "
            f"best_score={best_selected_score:.3f}"
        )

        exact_threshold, exact_scales, table_name = self._exact_ten_profile()
        native = self._native_size()
        quantity_passes = 0
        best_quantity_score = 0.0
        fast_confidence = False
        for quantity_attempt in range(1, 4):
            quantity_marker = self.selling.vision.find(
                "sl10",
                threshold=exact_threshold,
                zone=self.selling.SL10_ZONE,
                scales=exact_scales,
                click=False,
            )
            if quantity_marker is not None:
                quantity_passes += 1
                best_quantity_score = max(best_quantity_score, float(quantity_marker.score))
                fast_confidence = (
                    native == (1000, 1000)
                    and quantity_marker.score >= self.N1000_FAST_CONFIDENCE_THRESHOLD
                )
                self.context.detail(
                    "AUTO sale x10 proof | "
                    f"table={table_name} | attempt={quantity_attempt}/3 | "
                    f"passes={quantity_passes}/{self.EXACT_TEN_REQUIRED_PASSES} | "
                    f"score={quantity_marker.score:.3f} | threshold={exact_threshold:.2f} | "
                    f"fast_confidence={str(fast_confidence).lower()}"
                )
            else:
                quantity_passes = 0
                fast_confidence = False
                self.context.detail(
                    "AUTO sale x10 proof | "
                    f"table={table_name} | attempt={quantity_attempt}/3 | "
                    "passes reset=0 | marker=MISS"
                )
            if fast_confidence or quantity_passes >= self.EXACT_TEN_REQUIRED_PASSES:
                if fast_confidence:
                    self.context.log(
                        "AUTO bán VP • x10 FAST READY • native=1000x1000 • "
                        f"score={quantity_marker.score:.3f} • "
                        f"fast_threshold={self.N1000_FAST_CONFIDENCE_THRESHOLD:.2f}"
                    )
                break
            if quantity_attempt < 3:
                self.selling.waiter.sleep(0.20)
        if not fast_confidence and quantity_passes < self.EXACT_TEN_REQUIRED_PASSES:
            self.context.log(
                f"AUTO bán VP • {item.label} chưa chứng minh được x10 • "
                f"table={table_name} • best_score={best_quantity_score:.3f} • "
                f"threshold={exact_threshold:.2f} • hủy và chuyển VP kế tiếp"
            )
            self._cancel_selected_item()
            return "BELOW_TEN"

        self.context.log(
            f"AUTO bán VP • {item.label} • sale dialog READY + x10 PASS • "
            f"table={table_name} • quantity_score={best_quantity_score:.3f} • "
            "click Đặt bán"
        )
        before = self._sale_change_crop()
        self.selling.vision.driver.click(*self.selling.PLACE_BUTTON)
        self.selling.waiter.settle(0.20)
        self.selling.vision.find(
            "dong_y",
            threshold=0.74,
            zone=self.selling.CONFIRM_ZONE,
            click=True,
        )

        best_change = 0.0
        deadline = time.monotonic() + 6.0
        while time.monotonic() < deadline:
            after = self._sale_change_crop()
            best_change = max(best_change, _mean_difference(before, after))
            if best_change >= self.selling.minimum_screen_change:
                self.context.log(
                    f"AUTO MAIN đã treo {item.label} x10 "
                    f"(match={item.score:.3f}, quantity={best_quantity_score:.3f}, "
                    f"change={best_change:.2f}) • chờ POST_SALE OWN_STALL"
                )
                try:
                    self._wait_own_stall_ready_auto(
                        timeout=self.POST_SALE_OWN_STALL_TIMEOUT,
                        description="POST_SALE OWN_STALL",
                    )
                except ScreenTimeout as exc:
                    raise TransactionError(
                        f"Đã có sale screen-change nhưng quầy chưa READY sau treo {item.label}; "
                        "không click listing kế tiếp"
                    ) from exc
                self.context.log(
                    "AUTO bán VP • POST_SALE OWN_STALL READY • "
                    f"item={item.label} • next-listing-safe=true"
                )
                return "SOLD"
            self.selling.waiter.settle(0.20)
        self.selling._cancel_dialog(cancelable=False)
        raise TransactionError(
            f"Không xác nhận được thay đổi sau khi treo {item.label}"
        )

    def sell_next_allowed(self, *, storage_id: int = 2) -> AutoSaleAttempt:
        self.context.ensure_running()
        if int(storage_id) != 2:
            raise ValueError("AUTO Main chỉ bán VP từ kho thành phẩm số 2")
        if not self._open_empty_slot_picker_verified():
            return AutoSaleAttempt(status="NO_EMPTY_SLOT")

        recognized = self._open_and_scan_finished_goods()
        if not recognized:
            self.selling.close_inventory_read_only()
            return AutoSaleAttempt(status="NO_ALLOWED_ITEM")

        for checked_count in range(1, len(self.ITEM_ORDER) + 1):
            blocked_item_ids = self._insufficient_item_ids | self._unsafe_item_ids
            if len(blocked_item_ids) == len(self.ITEM_ORDER):
                self.selling.close_inventory_read_only()
                return AutoSaleAttempt(status="NO_SAFE_EXACT_TEN_ITEMS")

            selected = self._next_candidate(recognized)
            if selected is None:
                self.selling.close_inventory_read_only()
                return AutoSaleAttempt(status="NO_SAFE_EXACT_TEN_ITEMS")

            self.context.log(
                f"AUTO bán VP • kiểm tra {checked_count}/{len(self.ITEM_ORDER)} • "
                f"chọn {selected.label} • score={selected.score:.3f}"
            )
            placement = self._place_exact_ten(selected)
            if placement != "SOLD":
                if placement == "BELOW_TEN":
                    self._insufficient_item_ids.add(selected.item_id)
                else:
                    self._unsafe_item_ids.add(selected.item_id)
                self._next_item_index = (
                    self.ITEM_ORDER.index(selected.item_id) + 1
                ) % len(self.ITEM_ORDER)
                continue

            self._next_item_index = (
                self.ITEM_ORDER.index(selected.item_id) + 1
            ) % len(self.ITEM_ORDER)
            return AutoSaleAttempt(
                status="SOLD",
                item_id=selected.item_id,
                label=selected.label,
                score=float(selected.score),
            )

        self.selling.close_inventory_read_only()
        return AutoSaleAttempt(status="NO_SAFE_EXACT_TEN_ITEMS")
