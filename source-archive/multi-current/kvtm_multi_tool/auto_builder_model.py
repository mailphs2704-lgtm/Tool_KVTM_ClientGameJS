from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import uuid

import auto_builder_function1_manifest as function1_manifest


__all__ = [
    "AutoBuilderPlanStore",
    "builtin_function_templates",
    "default_plan",
    "new_function",
    "new_function_from_builtin",
    "new_step_id",
    "step_summary",
]
FILE_FUNCTIONS = (
    "Tạo plan AUTO Builder mặc định và Function tái sử dụng",
    "Đọc/ghi plan chính ở AppData bền qua build DEV",
    "Đọc/ghi thư viện Function riêng theo function_id",
    "Seed Function 9 Táo sấy - 9 Vải vàng với full execution manifest vào Load Function",
    "Tách blueprint hiển thị khỏi runtime wrapper proven function_1",
    "Đóng gói Function đã lưu vào snapshot plan trước khi chạy",
    "Quản lý/liệt kê thư viện ảnh riêng của Multi DEV ngoài dist",
    "Liệt kê ảnh AUTO PRO và copy ảnh được chọn sang thư viện Multi DEV",
    "Tạo mô tả ngắn của bước cho giao diện Multi DEV",
)

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
_BUILTIN_WRAPPER_ID = "builtin_function_1_existing"


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


def builtin_function_templates() -> list[dict]:
    return [
        {
            "template_id": "builtin_function_1",
            "name": "9 Táo sấy - 9 Vải vàng",
            "description": "Function 1 có sẵn: Táo sấy / Nước táo / Vải vàng",
        }
    ]


def _builtin_function_document(function_id: str) -> dict:
    return {
        "version": 1,
        "kind": "function",
        "function_id": function_id,
        "name": "9 Táo sấy - 9 Vải vàng",
        "source_template_id": "builtin_function_1",
        "manifest_version": function1_manifest.MANIFEST_VERSION,
        "steps": function1_manifest.display_steps(new_step_id),
        "runtime_steps": function1_manifest.runtime_steps(new_step_id),
    }


def new_function_from_builtin(template_id: str) -> dict:
    key = str(template_id or "").strip()
    if key != "builtin_function_1":
        raise KeyError(f"Built-in Function template chưa hỗ trợ: {key}")
    function = _builtin_function_document(_new_function_id())
    return function


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


def _normalized_swipe_points(step: dict) -> list[list[int]]:
    raw = step.get("points")
    points: list[list[int]] = []
    if isinstance(raw, (list, tuple)):
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                try:
                    points.append([int(item[0]), int(item[1])])
                except (TypeError, ValueError):
                    pass
    if len(points) >= 2:
        return points
    try:
        return [
            [int(step.get("x1", 500)), int(step.get("y1", 700))],
            [int(step.get("x2", 500)), int(step.get("y2", 300))],
        ]
    except (TypeError, ValueError):
        return []


def step_summary(step: dict) -> tuple[str, str]:
    step_type = str(step.get("type") or "")
    if step_type.startswith("trace_"):
        kind = step_type.removeprefix("trace_")
        labels = {
            "module": "MODULE",
            "click": "CLICK",
            "swipe": "SWIPE",
            "wait": "WAIT",
            "recognize": "NHẬN DIỆN",
            "gate": "GATE / HẬU KIỂM",
            "loop": "LOOP / NHÁNH",
        }
        return labels.get(kind, kind.upper()), str(step.get("detail") or "")
    if step_type == "enter_game_popup":
        return "MODULE", "Vào game + đóng popup"
    if step_type == "sell_function_vp":
        return "MODULE", f"Bán VP • {step.get('function_id', 'function_1')}"
    if step_type == "function":
        suffix = " • bán VP sau mỗi vòng" if step.get("sale_after_each_loop") else ""
        name = "9 Táo sấy - 9 Vải vàng" if step.get("function_id") == "function_1" else str(step.get("function_id", "Function"))
        return "FUNCTION", f"{name} × {int(step.get('loops', 1) or 1)}{suffix}"
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
        source = str(step.get("image_source") or "multi_library")
        source_label = "Multi DEV" if source == "multi_library" else "AUTO PRO→Multi"
        return "NHẬN DIỆN", (
            f"{name} • {source_label} • threshold={float(step.get('threshold', 0.8)):.2f}"
        )
    if step_type == "click":
        return "CLICK", f"({step.get('x')}, {step.get('y')})"
    if step_type == "swipe":
        points = _normalized_swipe_points(step)
        if len(points) >= 2:
            return "SWIPE", (
                f"{len(points)} điểm / {len(points) - 1} đoạn • "
                f"{points[0][0]},{points[0][1]} → {points[-1][0]},{points[-1][1]} • "
                f"{float(step.get('duration', 0.35)):.2f}s"
            )
        return "SWIPE", "Chưa có đường kéo hợp lệ"
    if step_type == "wait":
        return "WAIT", f"{float(step.get('seconds', 0.5)):.2f}s"
    if step_type == "finish_pass":
        return "KẾT THÚC", "PASS"
    if step_type == "finish_fail":
        return "KẾT THÚC", "FAIL"
    return step_type.upper() or "?", str(step)


class AutoBuilderPlanStore:
    """Persistent DEV-only Builder plan, functions and image library outside ``dist``."""

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
        self.image_library_dir = self.root / "image-library"
        self.root.mkdir(parents=True, exist_ok=True)
        self.functions_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.image_library_dir.mkdir(parents=True, exist_ok=True)
        self._migrate_legacy_assets_to_image_library()
        self._seed_existing_function_one()

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

    @staticmethod
    def _is_image(path: Path) -> bool:
        return path.is_file() and path.suffix.lower() in _IMAGE_SUFFIXES

    @staticmethod
    def _under(path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            return False

    def _seed_existing_function_one(self) -> None:
        path = self.functions_dir / f"{_BUILTIN_WRAPPER_ID}.json"
        current = None
        if path.is_file():
            try:
                current = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                current = None
        if (
            isinstance(current, dict)
            and current.get("source_template_id") == "builtin_function_1"
            and int(current.get("manifest_version", 0) or 0) >= function1_manifest.MANIFEST_VERSION
            and isinstance(current.get("steps"), list)
            and len(current.get("steps") or []) > 1
            and isinstance(current.get("runtime_steps"), list)
            and current.get("runtime_steps")
        ):
            return
        payload = _builtin_function_document(_BUILTIN_WRAPPER_ID)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    def _migrate_legacy_assets_to_image_library(self) -> None:
        for path in self.assets_dir.iterdir():
            if not self._is_image(path):
                continue
            try:
                self._copy_image_to_library(path)
            except OSError:
                continue

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
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.plan_path)

    def save_function(self, function: dict) -> Path:
        payload = self._validate_document(function, kind="function")
        path = self.functions_dir / f"{payload['function_id']}.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
                data = self._validate_document(json.loads(path.read_text(encoding="utf-8")), kind="function")
            except Exception:
                continue
            result.append(data)
        return sorted(
            result,
            key=lambda item: (0 if item.get("function_id") == _BUILTIN_WRAPPER_ID else 1, str(item.get("name") or "").lower()),
        )

    def bundle_plan(self, plan: dict) -> dict:
        payload = self._validate_document(plan, kind="plan")
        functions: dict[str, dict] = {}
        for item in self.list_functions():
            runtime_item = dict(item)
            if runtime_item.get("source_template_id") == "builtin_function_1":
                runtime_steps = runtime_item.get("runtime_steps")
                if not isinstance(runtime_steps, list) or not runtime_steps:
                    runtime_steps = function1_manifest.runtime_steps(new_step_id)
                runtime_item["steps"] = list(runtime_steps)
            functions[runtime_item["function_id"]] = runtime_item
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

    def list_library_images(self) -> list[Path]:
        return sorted(
            (path.resolve() for path in self.image_library_dir.iterdir() if self._is_image(path)),
            key=lambda item: item.name.lower(),
        )

    @staticmethod
    def resolve_auto_pro_root(tool_dir: str | Path) -> Path:
        tool = Path(tool_dir).expanduser().resolve()
        candidate = tool.parent / "AUTO_PRO"
        if not candidate.is_dir():
            raise FileNotFoundError(f"Không tìm thấy thư mục AUTO_PRO cùng package Multi DEV: {candidate}")
        return candidate

    def list_auto_pro_images(self, auto_pro_root: str | Path) -> list[Path]:
        root = Path(auto_pro_root).expanduser().resolve()
        if not root.is_dir():
            raise FileNotFoundError(root)
        return sorted(
            (path.resolve() for path in root.rglob("*") if self._is_image(path)),
            key=lambda item: str(item.relative_to(root)).lower(),
        )

    def use_library_image(self, source: str | Path) -> Path:
        path = Path(source).expanduser().resolve()
        if not self._is_image(path):
            raise ValueError("Ảnh thư viện Multi DEV không hợp lệ")
        if not self._under(path, self.image_library_dir):
            raise ValueError("Chỉ được chọn ảnh nằm trong thư viện Multi DEV")
        return path

    def _copy_image_to_library(self, source: str | Path) -> Path:
        path = Path(source).expanduser().resolve()
        if not self._is_image(path):
            raise ValueError("Ảnh Builder phải là PNG/JPG/JPEG/BMP/WEBP")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        target = self.image_library_dir / f"{digest}-{path.name}"
        if not target.is_file():
            shutil.copy2(path, target)
        return target.resolve()

    def import_auto_pro_image(self, source: str | Path, auto_pro_root: str | Path) -> Path:
        path = Path(source).expanduser().resolve()
        root = Path(auto_pro_root).expanduser().resolve()
        if not self._under(path, root):
            raise ValueError("Ảnh đã chọn không nằm trong mục ảnh AUTO PRO")
        return self._copy_image_to_library(path)

    def import_asset(self, source: str | Path) -> Path:
        """Backward-compatible alias: all new imports land in Multi image library."""
        return self._copy_image_to_library(source)
