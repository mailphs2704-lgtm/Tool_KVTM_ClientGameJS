from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import time
import uuid


__all__ = [
    "AutoBuilderPlanStore",
    "default_plan",
    "new_function",
    "new_step_id",
    "step_summary",
]
FILE_FUNCTIONS = (
    "Tạo plan AUTO Builder mặc định và Function tái sử dụng",
    "Đọc/ghi plan chính ở AppData bền qua build DEV",
    "Đọc/ghi thư viện Function riêng theo function_id",
    "Liệt kê/load Function đã lưu cho editor nhiều tab",
    "Đóng gói Function đã lưu vào snapshot plan trước khi chạy",
    "Di chuyển dữ liệu Builder cũ từ data-dev nếu có",
    "Sao chép ảnh nhận diện người dùng vào vùng dữ liệu Builder",
    "Tạo mô tả ngắn của bước cho giao diện Multi DEV",
)


def new_step_id() -> str:
    return "step-" + uuid.uuid4().hex[:12]


def _new_function_id() -> str:
    return "custom_" + uuid.uuid4().hex[:12]


def new_function(name: str = "Function mới") -> dict:
    return {
        "version": 1,
        "kind": "function",
        "function_id": _new_function_id(),
        "name": str(name or "Function mới").strip() or "Function mới",
        "steps": [],
    }


def default_plan() -> dict:
    return {
        "version": 1,
        "kind": "plan",
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
    if step_type == "call_saved_function":
        suffix = ""
        if step.get("sale_after_each_loop"):
            suffix = f" • bán VP {step.get('sale_function_id', 'function_1')} sau mỗi vòng"
        return "FUNCTION TỰ TẠO", (
            f"{step.get('function_name') or step.get('function_id', '?')} "
            f"× {int(step.get('loops', 1) or 1)}{suffix}"
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
    """Persistent DEV-only Builder plan, functions and assets outside ``dist``."""

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
        self.functions_dir = self.root / "functions"
        self.assets_dir = self.root / "assets"
        self.root.mkdir(parents=True, exist_ok=True)
        self.functions_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_document(data: dict, *, kind: str) -> dict:
        if not isinstance(data, dict) or not isinstance(data.get("steps"), list):
            raise ValueError("document Builder không hợp lệ")
        result = dict(data)
        result["version"] = 1
        result["kind"] = kind
        result["name"] = str(result.get("name") or ("Function" if kind == "function" else "AUTO tự tạo")).strip()
        if not result["name"]:
            raise ValueError("Tên document Builder không được rỗng")
        if kind == "function":
            function_id = str(result.get("function_id") or "").strip()
            if not function_id or not function_id.replace("_", "").isalnum():
                raise ValueError("function_id không hợp lệ")
            result["function_id"] = function_id
        result["steps"] = list(result.get("steps") or [])
        return result

    def load(self) -> dict:
        if not self.plan_path.is_file():
            plan = default_plan()
            self.save(plan)
            return plan
        try:
            data = json.loads(self.plan_path.read_text(encoding="utf-8"))
            return self._validate_document(data, kind="plan")
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
        payload = self._validate_document(plan, kind="plan")
        temporary = self.plan_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.plan_path)

    def save_function(self, function: dict) -> Path:
        payload = self._validate_document(function, kind="function")
        path = self.functions_dir / f"{payload['function_id']}.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
        return path

    def load_function(self, function_id: str) -> dict:
        key = str(function_id or "").strip()
        if not key:
            raise ValueError("Thiếu function_id")
        path = self.functions_dir / f"{key}.json"
        if not path.is_file():
            raise FileNotFoundError(f"Không tìm thấy Function đã lưu: {key}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return self._validate_document(data, kind="function")

    def list_functions(self) -> list[dict]:
        result: list[dict] = []
        for path in sorted(self.functions_dir.glob("*.json"), key=lambda item: item.name.lower()):
            try:
                data = self._validate_document(
                    json.loads(path.read_text(encoding="utf-8")), kind="function"
                )
            except Exception:
                continue
            result.append(data)
        return result

    def bundle_plan(self, plan: dict) -> dict:
        payload = self._validate_document(plan, kind="plan")
        functions = {
            item["function_id"]: item
            for item in self.list_functions()
        }
        referenced = {
            str(step.get("function_id") or "")
            for step in payload["steps"]
            if str(step.get("type") or "") == "call_saved_function"
        }
        missing = sorted(function_id for function_id in referenced if function_id not in functions)
        if missing:
            raise ValueError("Thiếu Function đã lưu: " + ", ".join(missing))
        payload["saved_functions"] = functions
        return payload

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
