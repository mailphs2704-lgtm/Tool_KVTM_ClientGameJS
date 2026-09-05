from __future__ import annotations

from dataclasses import asdict, dataclass
import time

from ...automation import KVAutomation
from ...actions.item_recognition import VpRecognition
from ...errors import NoEmptyStallSlot


__all__ = ["VpRecognitionProbeResult", "VpRecognitionProbeWorkflow"]
FILE_FUNCTIONS = (
    "Đưa clone về màn hình chính và mở quầy bán",
    "Theo từng view: thu vàng rồi mở kho tại ô vừa trống",
    "Quét READ-ONLY ba VP mẫu tại chính view hiện tại",
    "Kéo đúng hai swipe sang view kế tiếp và lặp đến hết quầy",
    "Tổng hợp kết quả tốt nhất để hiển thị và kiểm thử",
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
    """Follow the real per-view sale order, but never click or list a VP."""

    def __init__(self, automation: KVAutomation) -> None:
        self.auto = automation
        self.context = automation.context

    def run(self, timeout: float = 90.0) -> VpRecognitionProbeResult:
        started = time.monotonic()
        self.context.stage("vp-recognition-read-only")
        self.auto.ensure_main_screen(timeout=timeout)
        self.auto.stall.open_own_stall()

        collected_gold = 0
        inventory_views = 0
        best_by_id: dict[str, VpRecognition] = {}
        try:
            for view in range(1, 5):
                self.context.ensure_running()
                self.context.stage(f"vp-recognition-own-stall-view-{view}")
                self.context.log(
                    f"Quầy clone view {view}/4 • thu vàng rồi kiểm tra VP"
                )
                collected_gold += self.auto.stall.collect_own_stall_gold(
                    maximum=20
                )

                inventory_open = False
                try:
                    self.auto.selling.open_inventory_read_only(storage_id=2)
                    inventory_open = True
                    inventory_views += 1
                    for result in self.auto.auto_vp.scan_samples():
                        previous = best_by_id.get(result.item_id)
                        if previous is None or result.score > previous.score:
                            best_by_id[result.item_id] = result
                except NoEmptyStallSlot:
                    self.context.log(
                        f"Quầy clone view {view}/4 • chưa có ô trống sau thu vàng"
                    )
                finally:
                    if inventory_open:
                        self.auto.selling.close_inventory_read_only()

                if view < 4:
                    self.auto.stall.next_view()
        finally:
            self.auto.stall.close_own_stall()

        if inventory_views == 0:
            raise NoEmptyStallSlot(
                "Đã thu vàng và kiểm tra đủ 4 view nhưng quầy không có ô trống"
            )

        recognized = tuple(
            best_by_id.get(
                spec.item_id,
                VpRecognition(
                    item_id=spec.item_id,
                    label=spec.label,
                    found=False,
                    template="",
                    score=0.0,
                    center=None,
                ),
            )
            for spec in self.auto.auto_vp.SAMPLE_ITEMS
        )
        self.context.log(
            f"READ-ONLY VP probe • {inventory_views}/4 view mở được kho • "
            f"đã thu vàng {collected_gold} ô"
        )
        self.context.ensure_running()
        self.context.stage("vp-recognition-read-only-finished")
        return VpRecognitionProbeResult(
            profile_id=self.context.profile_id,
            recognized=recognized,
            elapsed_seconds=round(time.monotonic() - started, 3),
            collected_gold_slots=int(collected_gold),
        )
