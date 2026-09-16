from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "components" / "clear_stall_tool" / "app.py"
MAIN = ROOT / "components" / "clear_stall_tool" / "main.py"
README = ROOT / "components" / "clear_stall_tool" / "README.md"


def require(text: str, needle: str, message: str) -> None:
    if needle not in text:
        raise SystemExit(f"FAIL: {message}: missing {needle!r}")


def parse(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path))
    return text


def main() -> int:
    app = parse(APP)
    entry = parse(MAIN)
    readme = README.read_text(encoding="utf-8")

    for token in (
        "KVTM - Dọn Quầy", "Bắt đầu tất cả", "Dừng tất cả", "Thêm tài khoản",
        "Đồng bộ profile", "Cấu hình nhanh", "Tổng tài khoản", "Đang chạy",
        "Sẵn sàng", "Đã dừng", "Chu kỳ mặc định", "TÊN TÀI KHOẢN",
        "PROFILE", "TRẠNG THÁI", "LẦN DỌN CUỐI", "CHU KỲ", "GHI CHÚ",
        "THAO TÁC", "PAGE_SIZE = 8",
    ):
        require(app, token, "Mẫu 8 UI contract")

    require(entry, "SetProcessDpiAwareness", "Windows DPI-awareness hook")
    require(entry, "install_runtime_integration", "runtime integration entrypoint")
    require(readme, "kế thừa nghiệp vụ Dọn quầy", "shared runtime boundary")
    require(readme, "không có ô nhập account/profile tự do", "profile-only account chooser")
    require(readme, "mọi tài khoản đều bắt đầu ở trạng thái `Đã dừng`", "startup stopped contract")

    for token in ("clear_stall_probe_runtime", "kvtm_automation.workflows.clear_stall", "subprocess.Popen", "ClientOwnershipRegistry"):
        if token in app:
            raise SystemExit(f"FAIL: app.py must remain presentation-only: {token}")

    print("CLEAR STALL STANDALONE UI CONTRACT PASS")
    print("layout=model-8")
    print("page_size=8")
    print("runtime_integration=ADAPTER")
    print("profile_chooser=PROFILE_ONLY")
    print("startup_state=STOPPED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
