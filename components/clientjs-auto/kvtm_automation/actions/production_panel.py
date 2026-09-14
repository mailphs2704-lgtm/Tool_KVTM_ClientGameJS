from __future__ import annotations

from ..context import AutomationContext
from ..errors import InventoryFull, WrongProductionMachine
from ..runtime.auto_speed_config import AutoSpeedConfig
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter


__all__ = ["ProductionPanelActions"]
FILE_FUNCTIONS = (
    "Sở hữu panel/slot primitives dùng chung cho mọi máy sản xuất VP",
    "Thu VP bằng burst x5 cùng tọa độ rồi xác minh đúng panel sản phẩm",
    "Đếm ô trống theo logical 1000 geometry và native frame scale",
    "Phát typed InventoryFull/WrongProductionMachine từ shared panel engine",
    "Giữ panel mở và chờ đủ số ô trống theo REQUIRED_COUNT của caller/subclass",
    "Không sở hữu recipe sản phẩm cụ thể hoặc Function choreography",
)


class ProductionPanelActions:
    """Reusable production panel/slot manipulation shared by product Actions.

    This class owns *how* a production machine panel is opened and verified, how
    empty slots are counted, and how shared recoverable signals are emitted. It
    does not queue any particular VP product. Product-specific Actions either
    inherit this engine or hold it as a helper.

    ``REQUIRED_COUNT`` defaults to 9 to preserve the existing Táo sấy/Nước táo/
    Vải vàng helper contract; product subclasses such as TDHH may override it.
    """

    PRODUCT_SEARCH_ZONE = (420, 550, 170, 120)
    KNOWN_PRODUCT_TEMPLATES = ("tao_say", "nuoc_tao", "vai_vang", "tra_say")
    EMPTY_SLOT_TEMPLATE = "o_trong"
    TOP_EMPTY_SLOT_ZONE = (335, 650, 130, 135)
    EMPTY_SLOT_ZONE = (335, 781, 395, 186)
    CLOSE_POINT = (965, 198)
    REQUIRED_COUNT = 9
    MIN_DISTANCE = 34
    PANEL_RECHECK_SECONDS = 1.0
    COLLECT_CLICK_BURST = 5

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

    def _count_matches(
        self,
        name: str,
        zone: tuple[int, int, int, int],
        threshold: float,
    ) -> int:
        """Count repeated panel anchors in logical 1000 coordinates."""
        import cv2

        frame = self.vision.frame()
        if frame.ndim == 3 and frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

        x, y, width, height = self.vision.logical_zone_to_frame(zone, frame)
        roi = frame[y:y + height, x:x + width]
        if roi.size == 0:
            self.context.detail(
                f"AUTO production matches | template={name} | count=0 | "
                f"threshold={threshold:.2f} | logical_zone={zone} | "
                f"frame_roi={(x, y, width, height)} | empty_roi=true"
            )
            return 0

        frame_sx, frame_sy = self.vision.frame_scales(frame)
        centers: list[tuple[int, int, float]] = []
        for path in self.vision.assets.candidates(name):
            template = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if template is None or template.size == 0:
                continue

            template_width = max(2, int(round(template.shape[1] * frame_sx)))
            template_height = max(2, int(round(template.shape[0] * frame_sy)))
            if template_height > roi.shape[0] or template_width > roi.shape[1]:
                continue

            scaled = template
            if (
                template_width != template.shape[1]
                or template_height != template.shape[0]
            ):
                interpolation = (
                    cv2.INTER_AREA
                    if (
                        template_width <= template.shape[1]
                        and template_height <= template.shape[0]
                    )
                    else cv2.INTER_CUBIC
                )
                scaled = cv2.resize(
                    template,
                    (template_width, template_height),
                    interpolation=interpolation,
                )

            scores = cv2.matchTemplate(roi, scaled, cv2.TM_CCOEFF_NORMED)
            while True:
                _minimum, maximum, _min_loc, maximum_location = cv2.minMaxLoc(scores)
                if float(maximum) < threshold:
                    break

                frame_center = (
                    x + maximum_location[0] + template_width // 2,
                    y + maximum_location[1] + template_height // 2,
                )
                cx, cy = self.vision.frame_point_to_logical(frame_center, frame)
                if all(
                    (cx - old_x) ** 2 + (cy - old_y) ** 2 >= self.MIN_DISTANCE ** 2
                    for old_x, old_y, _score in centers
                ):
                    centers.append((cx, cy, float(maximum)))

                left = max(0, maximum_location[0] - template_width // 2)
                top = max(0, maximum_location[1] - template_height // 2)
                right = min(
                    scores.shape[1], maximum_location[0] + template_width // 2
                )
                bottom = min(
                    scores.shape[0], maximum_location[1] + template_height // 2
                )
                scores[top:bottom, left:right] = -1.0

        self.context.detail(
            f"AUTO production matches | template={name} | count={len(centers)} | "
            f"threshold={threshold:.2f} | logical_zone={zone} | "
            f"frame_roi={(x, y, width, height)} | "
            f"frame_scale=({frame_sx:.4f},{frame_sy:.4f})"
        )
        return len(centers)

    def _find_top_empty_slot(self):
        return self.vision.find(
            self.EMPTY_SLOT_TEMPLATE,
            threshold=0.82,
            zone=self.TOP_EMPTY_SLOT_ZONE,
            scales=(1.00, 1.15, 1.30, 1.45, 1.60),
            click=False,
        )

    def _count_empty_slots(self) -> int:
        top_match = self._find_top_empty_slot()
        top = 1 if top_match is not None else 0
        lower = min(
            8,
            self._count_matches(
                self.EMPTY_SLOT_TEMPLATE,
                self.EMPTY_SLOT_ZONE,
                0.90,
            ),
        )
        total = top + lower
        self.context.detail(
            f"AUTO production empty slots | top={top}/1 | lower={lower}/8 | total={total}/9"
        )
        return total

    def _find_product_match(
        self,
        name: str,
        *,
        threshold: float = 0.70,
        frame=None,
    ):
        return self.vision.find(
            name,
            threshold=threshold,
            zone=self.PRODUCT_SEARCH_ZONE,
            scales=(0.75, 0.90, 1.00, 1.10, 1.25),
            click=False,
            frame=frame,
        )

    def _find_wrong_product_match(
        self,
        expected_template: str,
        *,
        threshold: float = 0.70,
        frame=None,
    ):
        source = self.vision.frame() if frame is None else frame
        best_name = None
        best_match = None
        for candidate in self.KNOWN_PRODUCT_TEMPLATES:
            if candidate == expected_template:
                continue
            match = self._find_product_match(
                candidate,
                threshold=threshold,
                frame=source,
            )
            if match is not None and (
                best_match is None or match.score > best_match.score
            ):
                best_name = candidate
                best_match = match
        if best_match is None:
            return None
        return best_name, best_match

    def _panel_state(self, frame=None) -> tuple[bool, bool]:
        source = self.vision.frame() if frame is None else frame
        warehouse_full = self.vision.find(
            "full_kho",
            threshold=0.90,
            zone=(333, 363, 313, 115),
            scales=(0.90, 1.00, 1.10),
            click=False,
            frame=source,
        )
        empty_ready = self.vision.find(
            self.EMPTY_SLOT_TEMPLATE,
            threshold=0.70,
            zone=self.EMPTY_SLOT_ZONE,
            scales=(0.90, 1.00, 1.10),
            click=False,
            frame=source,
        )
        return warehouse_full is not None, empty_ready is not None

    def _raise_inventory_full(self, label: str) -> None:
        self.vision.driver.click(*self.CLOSE_POINT)
        self.context.stage("auto-production-warehouse-full")
        self.context.log(
            f"AUTO {label} • phát hiện full_kho • đóng bảng cảnh báo/panel • "
            "bàn giao workflow xuống quầy bán VP"
        )
        raise InventoryFull(f"{label}: kho đầy khi thu VP/sản xuất")

    def _raise_wrong_machine(
        self,
        *,
        label: str,
        expected_template: str,
        actual_template: str,
        actual_center: tuple[int, int],
    ) -> None:
        self.vision.driver.click(*self.CLOSE_POINT)
        self.waiter.sleep(0.25)
        self.context.stage("auto-production-wrong-machine")
        self.context.log(
            f"AUTO {label} • PANEL SAI MÁY/SAI TẦNG • cần={expected_template} "
            f"nhưng thấy={actual_template} tại {actual_center} • đóng bảng SX ngay • "
            "bàn giao recovery về exact-main rồi lên lại đúng tầng"
        )
        raise WrongProductionMachine(
            f"{label}: cần {expected_template} nhưng panel đang mở là {actual_template}"
        )

    def _send_collect_burst(
        self,
        *,
        machine_point: tuple[int, int],
    ) -> int:
        self.context.ensure_running()
        for _ in range(self.COLLECT_CLICK_BURST):
            self.vision.driver.click(*machine_point)
        return self.COLLECT_CLICK_BURST

    def _click_until_panel_open(
        self,
        *,
        machine_point: tuple[int, int],
        product_template: str,
        label: str,
        product_threshold: float = 0.70,
    ) -> int:
        """Open and prove the exact requested product panel.

        This intentionally preserves the existing unbounded wait behavior. A
        maximum time/burst limit has not been defined by the operator and must not
        be invented during architecture-only refactoring.
        """
        click_count = 0
        burst_count = 0
        while True:
            self.context.ensure_running()
            burst_count += 1
            click_count += self._send_collect_burst(machine_point=machine_point)

            self.context.log(
                f"AUTO {label} • đã phát x5 click tức thì tại cùng tọa độ "
                f"• burst={burst_count} • tổng click={click_count}"
            )
            self.waiter.sleep(self.speed_config.vp_collect_delay)
            self.context.ensure_running()

            frame = self.vision.frame()
            warehouse_full, empty_ready = self._panel_state(frame=frame)
            if warehouse_full:
                self._raise_inventory_full(label)

            product = self._find_product_match(
                product_template,
                threshold=product_threshold,
                frame=frame,
            )
            if product is not None:
                self.context.log(
                    f"AUTO {label} • panel đã mở sau burst x5 và đã xác minh ảnh "
                    f"{product_template} trong vùng thư viện • burst={burst_count} • "
                    f"tổng click={click_count} • center={product.center} • "
                    f"nghỉ sau burst={self.speed_config.vp_collect_delay:.3f}s"
                )
                return click_count

            wrong = self._find_wrong_product_match(
                product_template,
                threshold=product_threshold,
                frame=frame,
            )
            if wrong is not None:
                actual_template, actual_match = wrong
                self._raise_wrong_machine(
                    label=label,
                    expected_template=product_template,
                    actual_template=actual_template,
                    actual_center=actual_match.center,
                )

            if empty_ready and (burst_count == 1 or burst_count % 5 == 0):
                self.context.log(
                    f"AUTO {label} • thấy dấu ô trống nhưng CHƯA có ảnh {product_template} "
                    "trong vùng thư viện • KHÔNG coi panel đã mở • tiếp tục burst x5"
                )
            elif burst_count == 1 or burst_count % 5 == 0:
                self.context.log(
                    f"AUTO {label} • panel chưa hiện sau burst x5 "
                    "• tiếp tục một burst x5 tức thì mới • "
                    f"burst={burst_count} • tổng click={click_count}"
                )

    def _wait_for_idle_open_panel(
        self,
        *,
        product_template: str,
        label: str,
        product_threshold: float = 0.70,
    ) -> tuple[int, tuple[int, int], tuple[int, int]]:
        """Keep a proven product panel open until required capacity is available.

        This intentionally preserves the existing unbounded machine/slot wait.
        No operator-defined max wait exists yet.
        """
        wait_round = 0
        product_misses = 0
        while True:
            self.context.ensure_running()

            warehouse_full, _empty_anchor = self._panel_state()
            if warehouse_full:
                self._raise_inventory_full(label)

            product = self._find_product_match(
                product_template,
                threshold=product_threshold,
            )
            if product is None:
                product_misses += 1
                if product_misses == 1 or product_misses % 10 == 0:
                    self.context.log(
                        f"AUTO {label} • ảnh sản phẩm tạm chưa khớp khi đang chờ "
                        f"• misses={product_misses} • KHÔNG dừng AUTO • "
                        f"giữ trạng thái và recheck sau {self.PANEL_RECHECK_SECONDS:.1f}s"
                    )
                self.waiter.sleep(self.PANEL_RECHECK_SECONDS)
                continue
            product_misses = 0

            top_slot = self._find_top_empty_slot()
            empty = self._count_empty_slots()
            if top_slot is not None and empty >= self.REQUIRED_COUNT:
                self.context.log(
                    f"AUTO {label} • panel giữ nguyên đã READY • "
                    f"đủ {empty} ô trống / cần {self.REQUIRED_COUNT}"
                )
                return empty, product.center, top_slot.center

            wait_round += 1
            if wait_round == 1 or wait_round % 10 == 0:
                self.context.log(
                    f"AUTO {label} • giữ nguyên panel sản xuất • "
                    f"đang có {empty} ô trống / cần {self.REQUIRED_COUNT} • "
                    f"chờ máy chạy xong • recheck={self.PANEL_RECHECK_SECONDS:.1f}s • "
                    f"vòng={wait_round}"
                )
            self.waiter.sleep(self.PANEL_RECHECK_SECONDS)
