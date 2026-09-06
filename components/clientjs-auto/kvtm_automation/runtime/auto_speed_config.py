from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


__all__ = ["AutoSpeedConfig"]
FILE_FUNCTIONS = (
    "Đọc ba tốc độ độc lập của AUTO MULTI DEV từ cấu hình giao diện",
    "Giới hạn giá trị để tránh swipe/click quá nhanh hoặc quá chậm",
    "Xuất cấu hình đã chuẩn hóa cho log và module sản xuất VP sau này",
)


@dataclass(frozen=True)
class AutoSpeedConfig:
    """Independent AUTO MULTI DEV timings, measured in seconds."""

    floor_swipe_duration: float = 0.35
    plant_harvest_duration: float = 0.035
    vp_production_delay: float = 0.40

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
            plant_harvest_duration=bounded(
                "plant_harvest_duration", cls.plant_harvest_duration, 0.01, 3.0
            ),
            vp_production_delay=bounded(
                "vp_production_delay", cls.vp_production_delay, 0.05, 10.0
            ),
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "floor_swipe_duration": self.floor_swipe_duration,
            "plant_harvest_duration": self.plant_harvest_duration,
            "vp_production_delay": self.vp_production_delay,
        }
