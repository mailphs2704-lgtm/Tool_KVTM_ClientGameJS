from __future__ import annotations

import json
from pathlib import Path
import subprocess
from tkinter import ttk


_TERMINAL_STATES = {"activated", "no_update", "pending_restart", "error"}


def _find_repo_root(package_root: Path) -> Path | None:
    for candidate in (package_root, *package_root.parents):
        if (candidate / ".git").is_dir() and (
            candidate / "tools" / "KVTM_RUNTIME_UPDATE.ps1"
        ).is_file():
            return candidate
    return None


def _find_controls(widget):
    try:
        if str(widget.cget("text")) == "BẢNG ĐIỀU KHIỂN":
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


def install_runtime_update_ui(app) -> None:
    """Add a one-click staged updater to the DEV control panel.

    Updating while Multi is open is safe: source is pulled and a sibling runtime
    is built while the current process keeps using its already loaded files. The
    updater activates the staged runtime automatically after the current Multi
    process exits, avoiding in-process Python/DLL hot replacement.
    """

    package_root = Path(__file__).resolve().parent.parent
    repo_root = _find_repo_root(package_root)
    controls = _find_controls(app)
    if controls is None:
        return

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
        message = str(payload.get("message") or "")
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
        elif current == "no_update":
            button.configure(text="Cập nhật DEV", state="normal")
        elif current == "error":
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
        show_note("Đang kiểm tra cập nhật DEV...")
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

    button = ttk.Button(
        controls,
        text="Cập nhật DEV",
        command=start_update,
        style="Action.TButton",
    )
    button.grid(row=1, column=3, sticky="ew", padx=4, pady=4)
    app.runtime_update_button = button

    existing = _read_status(status_path)
    if str(existing.get("state") or "") == "pending_restart":
        redraw(existing)
