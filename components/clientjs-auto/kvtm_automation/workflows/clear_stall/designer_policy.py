from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Any


CONFIG_FILENAME = "clear-stall-workflow-designer.json"
REQUIRED_ORDER = ("scan", "buy", "swipe_1", "swipe_2", "scan_next")


@dataclass(frozen=True)
class ClearStallRuntimePolicy:
    recognition_threshold: float = 0.60
    recognition_retries: int = 2
    recognition_retry_wait: float = 0.35
    swipe_pulses: int = 2
    swipe_duration: float = 0.35
    swipe_settle: float = 0.55
    swipe_start_x: int = 633
    swipe_start_y: int = 546
    swipe_end_x: int = 540
    swipe_end_y: int = 540
    collect_gold_maximum: int = 8
    storage_open_wait: float = 0.40

    def validate(self) -> None:
        if not 0.45 <= self.recognition_threshold <= 0.95:
            raise ValueError("recognition_threshold phải từ 0.45 đến 0.95")
        if not 0 <= self.recognition_retries <= 8:
            raise ValueError("recognition_retries phải từ 0 đến 8")
        if not 0.05 <= self.recognition_retry_wait <= 3.0:
            raise ValueError("recognition_retry_wait phải từ 0.05 đến 3 giây")
        if self.swipe_pulses != 2:
            raise ValueError("Một nhịp quầy bắt buộc gồm đúng 2 swipe")
        if not 0.05 <= self.swipe_duration <= 3.0:
            raise ValueError("swipe_duration phải từ 0.05 đến 3 giây")
        if not 0.05 <= self.swipe_settle <= 3.0:
            raise ValueError("swipe_settle phải từ 0.05 đến 3 giây")
        for name in ("swipe_start_x", "swipe_start_y", "swipe_end_x", "swipe_end_y"):
            if not 0 <= int(getattr(self, name)) <= 1000:
                raise ValueError(f"{name} phải nằm trong 0..1000")
        if not 1 <= self.collect_gold_maximum <= 8:
            raise ValueError("collect_gold_maximum phải từ 1 đến 8")
        if not 0.05 <= self.storage_open_wait <= 3.0:
            raise ValueError("storage_open_wait phải từ 0.05 đến 3 giây")


def default_document() -> dict[str, Any]:
    policy = asdict(ClearStallRuntimePolicy())
    steps = [
        {"id": "open_stall", "enabled": True, "label": "Mở quầy nhà bạn", "template": "quay_hang_friend", "code_file": "actions/stall.py", "code_symbol": "open_friend_stall", "x": 896, "y": 482},
        {"id": "scan", "enabled": True, "label": "Chụp và scan hai hàng", "template": "quay_hang_friend", "code_file": "worker/clear_stall_probe_runtime.py", "code_symbol": "scan_buy_stall", "zone": [195, 345, 605, 390]},
        {"id": "buy", "enabled": True, "label": "Mua VP đúng danh sách", "template": "", "code_file": "actions/buying.py", "code_symbol": "buy_from_listing", "threshold": 0.60},
        {"id": "swipe_1", "enabled": True, "label": "Swipe 1/2", "template": "quay_hang_friend", "code_file": "actions/stall.py", "code_symbol": "next_view", "x": 633, "y": 546, "x2": 540, "y2": 540},
        {"id": "swipe_2", "enabled": True, "label": "Swipe 2/2", "template": "quay_hang_friend", "code_file": "actions/stall.py", "code_symbol": "next_view", "x": 633, "y": 546, "x2": 540, "y2": 540},
        {"id": "scan_next", "enabled": True, "label": "Bắt buộc scan view kế", "template": "quay_hang_friend", "code_file": "worker/clear_stall_probe_runtime.py", "code_symbol": "stall-step-finished-scan-required", "zone": [195, 345, 605, 390]},
        {"id": "inventory_full", "enabled": True, "label": "Đầy kho: về treo rồi mua tiếp", "template": "x", "code_file": "worker/clear_stall_probe_runtime.py", "code_symbol": "flush_pending_inventory", "zone": [669, 351, 91, 88]},
        {"id": "collect_gold", "enabled": True, "label": "Thu vàng quầy nhà", "template": "thu_vang", "code_file": "actions/stall.py", "code_symbol": "collect_own_stall_gold", "maximum": 8},
        {"id": "resell", "enabled": True, "label": "Treo đúng VP đã mua", "template": "", "code_file": "actions/selling.py", "code_symbol": "sell_one_of_exact_purchases"},
    ]
    return {"version": 1, "policy": policy, "steps": steps}


def validate_document(document: dict[str, Any]) -> ClearStallRuntimePolicy:
    if not isinstance(document, dict):
        raise ValueError("Tài liệu workflow phải là object")
    steps = document.get("steps")
    if not isinstance(steps, list):
        raise ValueError("steps phải là danh sách")
    enabled_ids = [str(step.get("id")) for step in steps if isinstance(step, dict) and step.get("enabled", True)]
    positions = []
    for required in REQUIRED_ORDER:
        if required not in enabled_ids:
            raise ValueError(f"Thiếu bước bắt buộc: {required}")
        positions.append(enabled_ids.index(required))
    if positions != sorted(positions):
        raise ValueError("Thứ tự an toàn phải là scan → buy → swipe_1 → swipe_2 → scan_next")
    raw = document.get("policy") or {}
    allowed = set(ClearStallRuntimePolicy.__dataclass_fields__)
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"Policy có khóa không hỗ trợ: {sorted(unknown)}")
    policy = ClearStallRuntimePolicy(**raw)
    policy.validate()
    return policy


def config_path(root: Path | None = None) -> Path:
    data_root = Path(root) if root is not None else Path(
        os.environ.get("KVTM_MULTI_APP_DIR") or Path.cwd() / "data-dev"
    )
    return data_root / CONFIG_FILENAME


def load_runtime_policy(path: Path | None = None) -> ClearStallRuntimePolicy:
    target = Path(path) if path else config_path()
    if not target.is_file():
        return ClearStallRuntimePolicy()
    document = json.loads(target.read_text(encoding="utf-8"))
    return validate_document(document)


def save_document(document: dict[str, Any], path: Path | None = None) -> ClearStallRuntimePolicy:
    policy = validate_document(document)
    target = Path(path) if path else config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)
    return policy
