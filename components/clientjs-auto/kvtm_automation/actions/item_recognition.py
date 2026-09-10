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
    "Native 1000 ưu tiên template kho chính scale 1.00 để chọn VP nhanh, fallback full scan khi chưa đủ chắc chắn",
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

    FUNCTION_1_ITEM_IDS = ("tao_say", "vai_vang")
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
    N1000_FAST_PRIMARY_SCALE = (1.00,)
    N1000_FAST_PRIMARY_THRESHOLD = 0.82

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

    def _specs_for(self, item_ids: tuple[str, ...] | None) -> tuple[AutoVpSpec, ...]:
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
        return tuple(specs_by_id[item_id] for item_id in requested)

    def scan_first_native1000(
        self,
        *,
        log_prefix: str = "AUTO SELL VP FAST",
        item_ids: tuple[str, ...],
    ) -> VpRecognition | None:
        """Fast discovery for native 1000 inventory.

        The first template of each VP spec is the warehouse-specific reference.
        Probe only that template at exact scale 1.00 on one fresh frame, in the
        caller's preferred sale order. A strong match can be clicked immediately;
        the sale dialog still performs the existing selected-item proof before any
        listing is committed. When no strong warehouse match exists, callers must
        fall back to ``scan_samples`` unchanged.
        """
        self.context.ensure_running()
        specs = self._specs_for(item_ids)
        frame = self.vision.frame()
        frame_h, frame_w = frame.shape[:2]
        if (frame_w, frame_h) != (1000, 1000):
            return None

        self.context.detail(
            f"{log_prefix} | FAST_SNAPSHOT frame=1000x1000 | "
            f"primary_scale=1.00 | threshold={self.N1000_FAST_PRIMARY_THRESHOLD:.2f} | "
            f"items={','.join(spec.item_id for spec in specs)}"
        )
        for spec in specs:
            primary_template = spec.templates[0]
            match = self.vision.find(
                primary_template,
                threshold=self.N1000_FAST_PRIMARY_THRESHOLD,
                zone=self.inventory.INVENTORY_ZONE,
                scales=self.N1000_FAST_PRIMARY_SCALE,
                click=False,
                frame=frame,
            )
            if match is None:
                continue
            result = VpRecognition(
                item_id=spec.item_id,
                label=spec.label,
                found=True,
                template=match.template.stem,
                score=float(match.score),
                center=match.center,
            )
            self.context.log(
                f"{log_prefix} | FAST_FOUND {spec.label} | "
                f"template={result.template} score={result.score:.3f} "
                f"threshold={self.N1000_FAST_PRIMARY_THRESHOLD:.2f} "
                f"center={result.center}"
            )
            return result

        self.context.detail(
            f"{log_prefix} | FAST_MISS | fallback=full-scan | "
            f"items={','.join(spec.item_id for spec in specs)}"
        )
        return None

    def scan_samples(
        self,
        *,
        log_prefix: str = "READ-ONLY VP",
        item_ids: tuple[str, ...] | None = None,
    ) -> tuple[VpRecognition, ...]:
        """Scan the Function-owned VP policy against one fresh inventory frame.

        Capture once and reuse that immutable frame for every candidate. Matching
        at -1.0 retains the best raw score for diagnostics; acceptance remains
        fail-closed at each spec's threshold.
        """
        self.context.ensure_running()
        specs = self._specs_for(item_ids)
        requested = tuple(spec.item_id for spec in specs)

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
