from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


__all__ = ["AutoSpeedConfig"]
FILE_FUNCTIONS = (
    "Đọc sáu tốc độ độc lập của AUTO MULTI DEV từ cấu hình giao diện",
    "Tách tốc độ kéo quầy bán khỏi tốc độ kéo tầng để không dùng nhầm timing",
    "Tách riêng tốc độ click thu VP khỏi tốc độ kéo/xếp VP sản xuất",
    "Giới hạn giá trị để tránh swipe/click quá nhanh hoặc quá chậm",
    "Xuất cấu hình đã chuẩn hóa cho worker và các module nghiệp vụ",
)


@dataclass(frozen=True)
class AutoSpeedConfig:
    """Independent AUTO MULTI DEV timings, measured in seconds."""

    floor_swipe_duration: float = 0.35
    shop_drag_speed: float = 0.35
    plant_harvest_duration: float = 0.035
    vp_collect_delay: float = 0.30
    vp_production_delay: float = 0.40
    crop_check_interval: float = 0.30

    @classmethod
    def from_mapping(cls, values: Mapping[str, object] | None) -> "AutoSpeedConfig":
        source = values or {}

        def bounded(key: str, default: float, minimum: float, maximum: float) -> float:
            try:
                value = float(source.get(key, default))
            except (TypeError, ValueError):
                value = default
            return min(maximum, max(minimum, value))

        return cls(
            floor_swipe_duration=bounded(
                "floor_swipe_duration", cls.floor_swipe_duration, 0.05, 3.0
            ),
            shop_drag_speed=bounded(
                "shop_drag_speed", cls.shop_drag_speed, 0.05, 3.0
            ),
            plant_harvest_duration=bounded(
                "plant_harvest_duration", cls.plant_harvest_duration, 0.01, 3.0
            ),
            vp_collect_delay=bounded(
                "vp_collect_delay", cls.vp_collect_delay, 0.05, 5.0
            ),
            vp_production_delay=bounded(
                "vp_production_delay", cls.vp_production_delay, 0.05, 10.0
            ),
            crop_check_interval=bounded(
                "crop_check_interval", cls.crop_check_interval, 0.05, 5.0
            ),
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "floor_swipe_duration": self.floor_swipe_duration,
            "shop_drag_speed": self.shop_drag_speed,
            "plant_harvest_duration": self.plant_harvest_duration,
            "vp_collect_delay": self.vp_collect_delay,
            "vp_production_delay": self.vp_production_delay,
            "crop_check_interval": self.crop_check_interval,
        }
