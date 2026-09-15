from __future__ import annotations

"""Persistent per-profile AUTO error journal for later diagnosis/fix work."""

from datetime import datetime
from pathlib import Path
import re
import threading


__all__ = [
    "error_log_file_for_profile",
    "explain_error_vi",
    "record_auto_error",
]

_ERROR_DIRNAME = "auto-error-log"
_SAFE_PROFILE_RE = re.compile(r"[^A-Za-z0-9_.-]+")
_SECRET_PATTERN = re.compile(
    r"(?i)(password|token|cookie|authorization|secret|launch_args)\s*[:=]\s*([^\s,;]+)"
)
_LOCK = threading.RLock()


def _safe_text(value: object) -> str:
    text = str(value or "")
    return _SECRET_PATTERN.sub(
        lambda match: f"{match.group(1)}=<redacted>",
        text,
    )


def _safe_profile_id(profile_id: str) -> str:
    value = _SAFE_PROFILE_RE.sub("_", str(profile_id or "").strip())
    return value or "unknown-profile"


def error_log_file_for_profile(app_dir: Path, profile_id: str) -> Path:
    root = Path(app_dir).resolve() / _ERROR_DIRNAME
    return root / f"{_safe_profile_id(profile_id)}.txt"


def _app_dir_from_context(context) -> Path:
    profile_file = getattr(context, "profile_file", None)
    if profile_file is not None:
        return Path(profile_file).resolve().parent
    work_dir = Path(getattr(context, "work_dir")).resolve()
    for parent in (work_dir, *work_dir.parents):
        if parent.name.lower() == "auto-multi-dev":
            return parent.parent
    return work_dir


def explain_error_vi(error: BaseException) -> str:
    """Return a compact Vietnamese explanation suitable for operator/error logs."""
    error_type = type(error).__name__
    message = str(error or "")
    lowered = f"{error_type} {message}".lower()

    if error_type == "InventoryFull" or "kho đầy" in lowered or "full_kho" in lowered:
        return "Kho chứa VP đã đầy; AUTO cần giải phóng chỗ trước khi tiếp tục."
    if error_type == "WrongProductionMachine" or "sai máy" in lowered:
        return "Đang ở sai máy/sai tầng hoặc panel sản xuất không đúng sản phẩm cần làm."
    if error_type == "MaterialShortage" or "thiếu nguyên liệu" in lowered:
        return "Thiếu nguyên liệu cho bước sản xuất hiện tại."
    if error_type == "ScreenTimeout":
        return "Không chứng minh được trạng thái màn hình mong đợi trong giới hạn an toàn."
    if error_type == "TemplateNotFound":
        return "Không tìm thấy ảnh mẫu bắt buộc để xác minh thao tác an toàn."
    if error_type == "NavigationError":
        return "Điều hướng không đạt được trạng thái/tầng đã yêu cầu."
    if error_type == "TransactionError":
        return "Thao tác giao dịch không vượt qua hậu kiểm an toàn."
    if error_type == "NoEmptyStallSlot":
        return "Quầy bán không còn ô trống phù hợp cho giao dịch hiện tại."
    if error_type == "InsufficientBatch":
        return "Vật phẩm hiện có không đủ điều kiện tạo một lô x10 đã xác minh."
    if any(token in lowered for token in ("bridge", "capture3", "pipe", "clientjs")):
        return "Kết nối Bridge/ClientJS hoặc kênh capture/input không còn ở trạng thái sử dụng được."
    if "exact-main" in lowered or "exact main" in lowered:
        return "Không chứng minh được vị trí exact MAIN trước khi tiếp tục nghiệp vụ."
    return f"Lỗi chưa có policy chuyên biệt ({error_type}); AUTO sẽ dùng recovery tổng quát."


def record_auto_error(
    context,
    error: BaseException,
    *,
    traceback_text: str = "",
    phase: str = "runtime",
    recovery_state: str = "chưa xử lý",
) -> Path:
    """Append one diagnostic block and return the persistent profile TXT path."""
    profile_id = str(getattr(context, "profile_id", "") or "")
    profile_name = str(getattr(context, "profile_name", "") or profile_id)
    path = error_log_file_for_profile(_app_dir_from_context(context), profile_id)
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    explanation = explain_error_vi(error)
    lines = [
        f"[{timestamp}] Tài khoản: {_safe_text(profile_name)}",
        f"Loại lỗi: {type(error).__name__}",
        f"Giải thích: {_safe_text(explanation)}",
        f"Nội dung: {_safe_text(error)}",
        f"Giai đoạn: {_safe_text(phase)}",
        f"Trạng thái xử lý: {_safe_text(recovery_state)}",
    ]
    trace = _safe_text(traceback_text).strip()
    if trace:
        lines.extend(("Traceback:", trace))
    lines.append("-" * 80)
    block = "\n".join(lines) + "\n"

    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="") as stream:
            stream.write(block)
            stream.flush()
    return path
