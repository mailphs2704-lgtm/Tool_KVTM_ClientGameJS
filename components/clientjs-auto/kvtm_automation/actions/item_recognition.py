from __future__ import annotations

from dataclasses import asdict, dataclass

from ..context import AutomationContext
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter
from .inventory import InventoryActions


__all__ = ["AutoVpSpec", "VpRecognition", "AutoVpRecognitionActions"]
FILE_FUNCTIONS = (
    "Khai báo thư viện VP mẫu dùng chung cho AUTO Main",
    "Mặc định Function 1 chỉ quét Táo sấy/Vải vàng; Function khác phải truyền policy riêng",
    "Quét vùng kho thành phẩm đã mở trên đúng một fresh frame",
    "Nhận diện VP theo template AUTO PRO",
    "Trả kết quả READ-ONLY có raw score/vị trí kể cả khi dưới threshold",
    "Ghi kết quả vào log hành động và chi tiết",
)


@dataclass(frozen=True)
class AutoVpSpec:
    item_id: str
    label: str
    templates: tuple[str, ...]
    storage_id: int = 2
    threshold: float = 0.72


@dataclass(frozen=True)
class VpRecognition:
    item_id: str
    label: str
    found: bool
    template: str
    score: float
    center: tuple[int, int] | None

    def to_dict(self) -> dict:
        return asdict(self)


class AutoVpRecognitionActions:
    """READ-ONLY recognition for items produced by AUTO Main."""

    # Function 1 was the pilot flow. Rose oil was only present there as an early
    # recognition test, so the default scan must stay limited to its real sale VP.
    FUNCTION_1_ITEM_IDS = ("tao_say", "vai_vang")

    # Function 2 starts from the same shared recognition library but owns rose oil.
    # Its production runner is developed separately from Function 1.
    FUNCTION_2_ITEM_IDS = ("tao_say", "vai_vang", "tinh_dau_hh")

    SAMPLE_ITEMS = (
        AutoVpSpec("tao_say", "Táo sấy", ("kho_tao_say", "tao_say")),
        AutoVpSpec("vai_vang", "Vải vàng", ("kho_vai_vang", "vai_vang")),
        AutoVpSpec(
            "tinh_dau_hh",
            "Tinh dầu hoa hồng",
            ("kho_tinh_dau_hh", "tinh_dau_hh"),
        ),
    )
    RECOGNITION_SCALES = (0.75, 0.85, 0.95, 1.00, 1.05, 1.15, 1.25)

    def __init__(
        self,
        context: AutomationContext,
        vision: VisionEngine,
        waiter: Waiter,
        inventory: InventoryActions,
    ) -> None:
        self.context = context
        self.vision = vision
        self.waiter = waiter
        self.inventory = inventory

    def scan_samples(
        self,
        *,
        log_prefix: str = "READ-ONLY VP",
        item_ids: tuple[str, ...] | None = None,
    ) -> tuple[VpRecognition, ...]:
        """Scan the Function-owned VP policy against one fresh inventory frame.

        ``VisionEngine.find`` normally captures a frame when ``frame`` is omitted.
        Calling it once per template therefore mixed independent CAPTURE3 frames
        in one logical inventory scan. Immediately after a storage-tab transition
        that can pair a visible inventory with a stale/transition frame for the
        exact VP template being tested. Capture once here, then reuse that
        immutable frame for every candidate in this scan attempt.

        Function 1 is the default caller and intentionally scans only Táo sấy and
        Vải vàng. Tinh dầu hoa hồng remains in the shared library for Function 2,
        which must opt in explicitly through ``item_ids`` when its runner is ready.

        Matching is requested at -1.0 only to retain the best raw score for
        diagnostics. Acceptance remains fail-closed at each spec's unchanged
        threshold (0.72 by default); no weaker match can become clickable.
        """
        self.context.ensure_running()
        requested = (
            self.FUNCTION_1_ITEM_IDS
            if item_ids is None
            else tuple(str(item_id) for item_id in item_ids)
        )
        if not requested:
            raise ValueError("AUTO VP scan cần ít nhất một item_id")

        specs_by_id = {spec.item_id: spec for spec in self.SAMPLE_ITEMS}
        unknown = [item_id for item_id in requested if item_id not in specs_by_id]
        if unknown:
            raise ValueError(
                "AUTO VP scan chưa có template cho: " + ", ".join(unknown)
            )
        specs = tuple(specs_by_id[item_id] for item_id in requested)

        frame = self.vision.frame()
        frame_h, frame_w = frame.shape[:2]
        self.context.detail(
            f"{log_prefix} | SNAPSHOT frame={frame_w}x{frame_h} | "
            f"one-frame-all-templates=true | items={','.join(requested)}"
        )

        results: list[VpRecognition] = []
        for spec in specs:
            best = None
            for template in spec.templates:
                match = self.vision.find(
                    template,
                    threshold=-1.0,
                    zone=self.inventory.INVENTORY_ZONE,
                    scales=self.RECOGNITION_SCALES,
                    click=False,
                    frame=frame,
                )
                if match is not None and (
                    best is None or match.score > best.score
                ):
                    best = match

            score = float(best.score) if best is not None else -1.0
            found = best is not None and score >= float(spec.threshold)
            result = VpRecognition(
                item_id=spec.item_id,
                label=spec.label,
                found=found,
                template=best.template.stem if best is not None else "",
                score=score,
                center=best.center if found and best is not None else None,
            )
            results.append(result)
            if result.found:
                self.context.log(
                    f"{log_prefix} | {spec.label} | FOUND "
                    f"template={result.template} score={result.score:.3f} "
                    f"threshold={spec.threshold:.2f} center={result.center}"
                )
            else:
                self.context.log(
                    f"{log_prefix} | {spec.label} | NOT_FOUND "
                    f"best_template={result.template or 'NONE'} "
                    f"best_score={result.score:.3f} threshold={spec.threshold:.2f}"
                )
        return tuple(results)
