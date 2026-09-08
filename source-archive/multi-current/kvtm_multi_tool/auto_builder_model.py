from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import time
import uuid


__all__ = ["AutoBuilderPlanStore", "default_plan", "new_step_id", "step_summary"]
FILE_FUNCTIONS = (
    "Tạo plan AUTO Builder mặc định",
    "Đọc/ghi plan JSON ở vùng AppData bền qua build DEV",
    "Di chuyển plan Builder cũ từ data-dev nếu có",
    "Sao chép ảnh nhận diện người dùng vào vùng dữ liệu Builder",
    "Tạo mô tả ngắn của bước cho giao diện Multi DEV",
)


def new_step_id() -> str:
    return "step-" + uuid.uuid4().hex[:12]


def default_plan() -> dict:
    return {
        "version": 1,
        "name": "AUTO tự tạo 1",
        "steps": [
            {"id": new_step_id(), "type": "enter_game_popup", "timeout": 180.0},
            {
                "id": new_step_id(),
                "type": "sell_function_vp",
                "function_id": "function_1",
                "timeout": 120.0,
            },
            {
                "id": new_step_id(),
                "type": "function",
                "function_id": "function_1",
                "loops": 1,
                "sale_after_each_loop": True,
                "sale_timeout": 120.0,
            },
        ],
    }


def step_summary(step: dict) -> tuple[str, str]:
    step_type = str(step.get("type") or "")
    if step_type == "enter_game_popup":
        return "MODULE", "Vào game + đóng popup"
    if step_type == "sell_function_vp":
        return "MODULE", f"Bán VP • {step.get('function_id', 'function_1')}"
    if step_type == "function":
        suffix = " • bán VP sau mỗi vòng" if step.get("sale_after_each_loop") else ""
        return "FUNCTION", (
            f"{step.get('function_id', 'function_1')} × {int(step.get('loops', 1) or 1)}{suffix}"
        )
    if step_type == "recognize_image":
        name = Path(str(step.get("template_path") or "ảnh")).name
        return "NHẬN DIỆN", f"{name} • threshold={float(step.get('threshold', 0.8)):.2f}"
    if step_type == "click":
        return "CLICK", f"({step.get('x')}, {step.get('y')})"
    if step_type == "swipe":
        return "SWIPE", (
            f"({step.get('x1')},{step.get('y1')}) → ({step.get('x2')},{step.get('y2')}) "
            f"• {float(step.get('duration', 0.35)):.2f}s"
        )
    if step_type == "wait":
        return "WAIT", f"{float(step.get('seconds', 0.5)):.2f}s"
    if step_type == "finish_pass":
        return "KẾT THÚC", "PASS"
    if step_type == "finish_fail":
        return "KẾT THÚC", "FAIL"
    return step_type.upper() or "?", str(step)


class AutoBuilderPlanStore:
    """Persistent DEV-only Builder plans/assets outside the rebuilt dist tree."""

    def __init__(self, app_dir: Path) -> None:
        legacy_root = Path(app_dir).resolve() / "auto-builder"
        appdata = Path(os.environ.get("APPDATA") or Path.home()).resolve()
        self.root = appdata / "KVTM Multi DEV" / "auto-builder"
        if not self.root.exists() and legacy_root.is_dir():
            try:
                self.root.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(legacy_root, self.root)
            except OSError:
                pass
        self.plan_path = self.root / "current-plan.json"
        self.assets_dir = self.root / "assets"
        self.root.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict:
        if not self.plan_path.is_file():
            plan = default_plan()
            self.save(plan)
            return plan
        try:
            data = json.loads(self.plan_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("steps"), list):
                raise ValueError("plan không hợp lệ")
            return data
        except Exception:
            broken = self.root / f"current-plan-broken-{int(time.time())}.json"
            try:
                shutil.copy2(self.plan_path, broken)
            except OSError:
                pass
            plan = default_plan()
            self.save(plan)
            return plan

    def save(self, plan: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = dict(plan)
        payload["version"] = 1
        payload["name"] = str(payload.get("name") or "AUTO tự tạo 1").strip() or "AUTO tự tạo 1"
        payload["steps"] = list(payload.get("steps") or [])
        temporary = self.plan_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.plan_path)

    def import_asset(self, source: str | Path) -> Path:
        path = Path(source).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        suffix = path.suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
            raise ValueError("Ảnh Builder phải là PNG/JPG/JPEG/BMP/WEBP")
        target = self.assets_dir / f"{uuid.uuid4().hex[:10]}-{path.name}"
        shutil.copy2(path, target)
        return target.resolve()
