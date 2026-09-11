from __future__ import annotations

from ..errors import InventoryFull


__all__ = ["install_warehouse_full_guard"]

# Live 1000x1000 popup supplied on 2026-09-11:
# - centered olive/green board
# - red X near logical (717, 392)
# - orange "Nang cap" button near logical (500, 606)
#
# Keep coordinates in logical 1000 space. VisionEngine owns native scaling.
WAREHOUSE_FULL_MODAL_ZONE = (270, 385, 455, 225)
WAREHOUSE_FULL_X_ZONE = (665, 345, 115, 115)
WAREHOUSE_FULL_UPGRADE_ZONE = (440, 565, 125, 85)
WAREHOUSE_FULL_FALLBACK_X = (717, 392)
WAREHOUSE_FULL_X_THRESHOLD = 0.72
WAREHOUSE_FULL_GREEN_RATIO_MIN = 0.45
WAREHOUSE_FULL_ORANGE_RATIO_MIN = 0.08
WAREHOUSE_FULL_RED_X_RATIO_MIN = 0.035


def _logical_crop(action, frame, zone):
    x, y, width, height = action.vision.logical_zone_to_frame(zone, frame)
    return frame[y : y + height, x : x + width]


def _green_board_ratio(roi) -> float:
    if roi is None or getattr(roi, "size", 0) == 0 or roi.ndim < 3:
        return 0.0
    blue = roi[:, :, 0].astype("int16")
    green = roi[:, :, 1].astype("int16")
    red = roi[:, :, 2].astype("int16")
    return float(
        (
            (green > red + 8)
            & (green > blue + 25)
            & (green > 85)
        ).mean()
    )


def _orange_button_ratio(roi) -> float:
    if roi is None or getattr(roi, "size", 0) == 0 or roi.ndim < 3:
        return 0.0
    blue = roi[:, :, 0].astype("int16")
    green = roi[:, :, 1].astype("int16")
    red = roi[:, :, 2].astype("int16")
    return float(
        (
            (red > 130)
            & (green > 70)
            & (green < red - 20)
            & (blue < 90)
        ).mean()
    )


def _red_close_ratio(roi) -> float:
    if roi is None or getattr(roi, "size", 0) == 0 or roi.ndim < 3:
        return 0.0
    blue = roi[:, :, 0].astype("int16")
    green = roi[:, :, 1].astype("int16")
    red = roi[:, :, 2].astype("int16")
    return float(
        (
            (red > 145)
            & (red > green + 35)
            & (red > blue + 35)
        ).mean()
    )


def _detect_live_warehouse_full(action, frame):
    """Return visual proof for the supplied KHO QUA TAI popup."""
    modal = _logical_crop(action, frame, WAREHOUSE_FULL_MODAL_ZONE)
    green_ratio = _green_board_ratio(modal)
    if green_ratio < WAREHOUSE_FULL_GREEN_RATIO_MIN:
        return None

    button = _logical_crop(action, frame, WAREHOUSE_FULL_UPGRADE_ZONE)
    orange_ratio = _orange_button_ratio(button)
    if orange_ratio < WAREHOUSE_FULL_ORANGE_RATIO_MIN:
        return None

    x_roi = _logical_crop(action, frame, WAREHOUSE_FULL_X_ZONE)
    red_x_ratio = _red_close_ratio(x_roi)
    if red_x_ratio < WAREHOUSE_FULL_RED_X_RATIO_MIN:
        return None

    x_match = action.vision.find(
        "x",
        threshold=WAREHOUSE_FULL_X_THRESHOLD,
        zone=WAREHOUSE_FULL_X_ZONE,
        scales=(0.75, 0.85, 0.95, 1.00, 1.10, 1.20, 1.30),
        click=False,
        frame=frame,
    )
    close_point = x_match.center if x_match is not None else WAREHOUSE_FULL_FALLBACK_X
    return close_point, green_ratio, orange_ratio, red_x_ratio


def install_warehouse_full_guard() -> None:
    """Patch the shared production panel engine with the live full-kho guard.

    Every product transaction reaches panel state through ProductionPanelActions,
    directly or by inheritance. Patching this one shared primitive preserves the
    same recoverable InventoryFull evidence for Táo sấy/Nước táo/Vải vàng/TDHH.
    """
    from .production_panel import ProductionPanelActions

    if getattr(ProductionPanelActions, "_kvtm_live_warehouse_full_guard", False):
        return

    original_panel_state = ProductionPanelActions._panel_state

    def panel_state(self, frame=None):
        source = self.vision.frame() if frame is None else frame
        warehouse_full, empty_ready = original_panel_state(self, frame=source)
        if warehouse_full:
            x_match = self.vision.find(
                "x",
                threshold=WAREHOUSE_FULL_X_THRESHOLD,
                zone=WAREHOUSE_FULL_X_ZONE,
                scales=(0.75, 0.85, 0.95, 1.00, 1.10, 1.20, 1.30),
                click=False,
                frame=source,
            )
            self._warehouse_full_close_point = (
                x_match.center if x_match is not None else WAREHOUSE_FULL_FALLBACK_X
            )
            return True, empty_ready

        detected = _detect_live_warehouse_full(self, source)
        if detected is None:
            return False, empty_ready

        close_point, green_ratio, orange_ratio, red_x_ratio = detected
        self._warehouse_full_close_point = close_point
        self.context.detail(
            "AUTO kho day LIVE guard | "
            f"green={green_ratio:.3f} | orange={orange_ratio:.3f} | "
            f"red_x={red_x_ratio:.3f} | x={close_point}"
        )
        return True, empty_ready

    def raise_inventory_full(self, label: str) -> None:
        close_point = getattr(
            self,
            "_warehouse_full_close_point",
            WAREHOUSE_FULL_FALLBACK_X,
        )
        self.vision.driver.click(*close_point)
        self.waiter.sleep(0.25)
        self.context.stage("auto-production-warehouse-full")
        self.context.log(
            f"AUTO {label} • KHO QUA TAI • dong popup tai {close_point} • "
            "ban giao recovery xuong quay ban VP roi quay lai dung buoc thu"
        )
        raise InventoryFull(f"{label}: kho day khi thu VP/san xuat")

    ProductionPanelActions._panel_state = panel_state
    ProductionPanelActions._raise_inventory_full = raise_inventory_full
    ProductionPanelActions._kvtm_live_warehouse_full_guard = True
