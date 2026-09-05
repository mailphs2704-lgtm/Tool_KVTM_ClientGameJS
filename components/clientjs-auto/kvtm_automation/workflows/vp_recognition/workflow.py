from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation
from ...actions.item_recognition import VpRecognition


__all__ = ["VpRecognitionProbeResult", "VpRecognitionProbeWorkflow"]
FILE_FUNCTIONS = (
    "Đưa clone về màn hình chính",
    "Mở quầy và thu vàng trước khi mở kho",
    "Quét ba VP mẫu bằng module nhận diện dùng chung",
    "Tổng hợp kết quả để hiển thị và kiểm thử",
)


@dataclass(frozen=True)
class VpRecognitionProbeResult:
    profile_id: str
    recognized: tuple[VpRecognition, ...]
    elapsed_seconds: float
    collected_gold_slots: int
    read_only: bool = True

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["recognized_count"] = sum(
            1 for item in self.recognized if item.found
        )
        return payload


class VpRecognitionProbeWorkflow:
    """Open own sale inventory and identify sample VP without selling."""

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context

    def run(self, timeout: float = 90.0) -> VpRecognitionProbeResult:
        started = time.monotonic()
        self.context.stage("vp-recognition-read-only")
        self.auto.ensure_main_screen(timeout=timeout)
        self.auto.stall.open_own_stall()
        self.context.stage("vp-recognition-collect-own-stall-gold")
        collected_gold = self.auto.stall.collect_own_stall_gold(maximum=20)
        self.context.log(
            f"READ-ONLY VP probe • đã thu vàng {collected_gold} ô trước khi mở kho"
        )
        self.auto.selling.open_inventory_read_only(storage_id=2)
        try:
            recognized = self.auto.auto_vp.scan_samples()
        finally:
            self.auto.selling.close_inventory_read_only()
        self.context.ensure_running()
        self.context.stage("vp-recognition-read-only-finished")
        return VpRecognitionProbeResult(
            profile_id=self.context.profile_id,
            recognized=recognized,
            elapsed_seconds=round(time.monotonic() - started, 3),
            collected_gold_slots=int(collected_gold),
        )
