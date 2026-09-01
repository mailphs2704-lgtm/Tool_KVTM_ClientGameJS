from __future__ import annotations

import json
from pathlib import Path
import subprocess
from tkinter import ttk


_TERMINAL_STATES = {"activated", "no_update", "pending_restart", "error"}
_STATE_MESSAGES = {
    "checking": "Đang kiểm tra cập nhật DEV...",
    "pulling": "Có bản mới, đang tải source...",
    "building": "Đang build runtime DEV mới...",
    "activating": "Đang kích hoạt runtime DEV mới...",
    "pending_restart": "Bản mới đã sẵn sàng; sẽ tự kích hoạt khi đóng Multi.",
    "activated": "Đã cập nhật runtime DEV.",
    "no_update": "Runtime đã là bản mới nhất.",
}


def _find_repo_root(package_root: Path) -> Path | None:
    for candidate in (package_root, *package_root.parents):
        if (candidate / ".git").is_dir() and (
            candidate / "tools" / "KVTM_RUNTIME_UPDATE.ps1"
        ).is_file():
            return candidate
    return None


def _find_controls(widget):
    """Find the existing BẢNG ĐIỀU KHIỂN frame without changing core UI."""
    try:
        if str(widget.cget("text")).strip() == "BẢNG ĐIỀU KHIỂN":
            return widget
    except Exception:
        pass
    try:
        children = widget.winfo_children()
    except Exception:
        return None
    for child in children:
        found = _find_controls(child)
        if found is not None:
            return found
    return None


def _read_status(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _repair_mojibake(value: object) -> str:
    """Repair the common UTF-8-as-Windows-1252 text produced by PS 5.1."""
    text = str(value or "")
    if not text:
        return ""
    try:
        repaired = text.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
    # Only accept the conversion when it actually removes typical mojibake.
    bad_tokens = ("Ã", "Ä", "Â", "áº", "á»")
    before = sum(text.count(token) for token in bad_tokens)
    after = sum(repaired.count(token) for token in bad_tokens)
    return repaired if after < before else text


def install_runtime_update_ui(app) -> None:
    """Install a one-click staged updater inside the existing control panel.

    Source is pulled and a sibling runtime is built while the current process
    keeps using its already-loaded Python/native modules. If Multi is running,
    activation is deferred until the process exits; no in-process DLL hot swap
    is attempted.
    """

    package_root = Path(__file__).resolve().parent.parent
    repo_root = _find_repo_root(package_root)
    status_path = package_root / "data-dev" / "runtime-update-status.json"
    update_script = (
        repo_root / "tools" / "KVTM_RUNTIME_UPDATE.ps1" if repo_root else None
    )
    state = {"process": None, "last_state": ""}

    def show_note(message: str) -> None:
        try:
            app.note.set(message)
        except Exception:
            pass

    def redraw(payload: dict) -> None:
        current = str(payload.get("state") or "")
        if current == "error":
            detail = _repair_mojibake(payload.get("message"))
            show_note(
                f"Cập nhật DEV lỗi: {detail}"
                if detail
                else "Cập nhật DEV lỗi; dùng [8] gửi report nếu cần."
            )
        else:
            message = _STATE_MESSAGES.get(current)
            if message:
                show_note(message)

        if current == "checking":
            button.configure(text="Đang kiểm tra...", state="disabled")
        elif current == "pulling":
            button.configure(text="Đang tải source...", state="disabled")
        elif current == "building":
            button.configure(text="Đang build update...", state="disabled")
        elif current == "activating":
            button.configure(text="Đang kích hoạt...", state="disabled")
        elif current == "pending_restart":
            button.configure(text="✓ Đã tải • chờ đóng", state="disabled")
        elif current == "activated":
            button.configure(text="✓ Đã cập nhật", state="disabled")
        elif current in {"no_update", "error"}:
            button.configure(text="Cập nhật DEV", state="normal")

    def poll() -> None:
        payload = _read_status(status_path)
        current = str(payload.get("state") or "")
        if current and current != state["last_state"]:
            state["last_state"] = current
            redraw(payload)

        proc = state.get("process")
        running = bool(proc and proc.poll() is None)
        if running or (current and current not in _TERMINAL_STATES):
            app.after(500, poll)
            return

        if proc and proc.poll() not in (None, 0) and current != "error":
            button.configure(text="Cập nhật DEV", state="normal")
            show_note("Updater DEV kết thúc có lỗi; dùng [8] gửi report nếu cần.")
        state["process"] = None

    def start_update() -> None:
        if update_script is None or not update_script.is_file():
            show_note("Không tìm thấy repo/tools/KVTM_RUNTIME_UPDATE.ps1")
            return
        proc = state.get("process")
        if proc and proc.poll() is None:
            return

        button.configure(text="Đang kiểm tra...", state="disabled")
        show_note(_STATE_MESSAGES["checking"])
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            state["process"] = subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(update_script),
                    "-Mode",
                    "Update",
                    "-RuntimePath",
                    str(package_root),
                ],
                cwd=str(repo_root),
                creationflags=flags,
            )
        except Exception as exc:
            state["process"] = None
            button.configure(text="Cập nhật DEV", state="normal")
            show_note(f"Không mở được updater DEV: {exc}")
            return
        app.after(300, poll)

    controls = _find_controls(app)
    if controls is None:
        # Safe fallback only: keep it visible if the main layout changes later.
        button = ttk.Button(
            app,
            text="Cập nhật DEV",
            command=start_update,
            style="Action.TButton",
        )
        button.place(relx=1.0, x=-14, y=14, anchor="ne")
        button.lift()
    else:
        # Natural empty area in row 2: below Dừng chọn + Xóa hồ sơ.
        button = ttk.Button(
            controls,
            text="Cập nhật DEV",
            command=start_update,
            style="Action.TButton",
        )
        button.grid(
            row=1,
            column=3,
            columnspan=2,
            sticky="ew",
            padx=4,
            pady=4,
        )
    app.runtime_update_button = button

    existing = _read_status(status_path)
    if str(existing.get("state") or ""):
        redraw(existing)

    print(
        "[KVTM DEV] Runtime updater UI READY "
        f"repo={'FOUND' if repo_root else 'MISSING'} "
        f"controls={'FOUND' if controls is not None else 'FALLBACK'}",
        flush=True,
    )
