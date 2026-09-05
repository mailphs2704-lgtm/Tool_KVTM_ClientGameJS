from __future__ import annotations

from dataclasses import asdict, dataclass

from ..context import AutomationContext
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter
from .inventory import InventoryActions


__all__ = ["AutoVpSpec", "VpRecognition", "AutoVpRecognitionActions"]
FILE_FUNCTIONS = (
    "Khai báo ba VP mẫu của AUTO Main",
    "Chọn đúng kho thành phẩm để quét",
    "Nhận diện VP theo template AUTO PRO",
    "Trả kết quả READ-ONLY có score/vị trí",
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

    SAMPLE_ITEMS = (
        AutoVpSpec("tao_say", "Táo sấy", ("kho_tao_say", "tao_say")),
        AutoVpSpec("vai_vang", "Vải vàng", ("kho_vai_vang", "vai_vang")),
        AutoVpSpec(
            "tinh_dau_hh",
            "Tinh dầu hoa hồng",
            ("kho_tinh_dau_hh", "tinh_dau_hh"),
        ),
    )

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

    def scan_samples(self) -> tuple[VpRecognition, ...]:
        """Scan configured samples without clicking an inventory item."""
        self.context.ensure_running()
        self.inventory.select_storage(2)
        results: list[VpRecognition] = []
        for spec in self.SAMPLE_ITEMS:
            best = None
            for template in spec.templates:
                match = self.vision.find(
                    template,
                    threshold=spec.threshold,
                    zone=self.inventory.INVENTORY_ZONE,
                    scales=(0.75, 0.85, 0.95, 1.00, 1.05, 1.15, 1.25),
                    click=False,
                )
                if match is not None and (
                    best is None or match.score > best.score
                ):
                    best = match
            result = VpRecognition(
                item_id=spec.item_id,
                label=spec.label,
                found=best is not None,
                template=best.template.stem if best is not None else "",
                score=float(best.score) if best is not None else 0.0,
                center=best.center if best is not None else None,
            )
            results.append(result)
            self.context.log(
                f"READ-ONLY VP | {spec.label} | "
                + (
                    f"FOUND score={result.score:.3f} center={result.center}"
                    if result.found else "NOT_FOUND"
                )
            )
        return tuple(results)
