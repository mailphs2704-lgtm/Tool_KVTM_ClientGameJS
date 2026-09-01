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


def _read_status(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def install_runtime_update_ui(app) -> None:
    """Install an always-visible one-click staged updater in Multi DEV.

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

    # Do not depend on the internal control-panel layout. A root-level button
    # stays visible even when the panel is refactored, resized, or packed
    # differently on another machine.
    button = ttk.Button(
        app,
        text="Cập nhật DEV",
        command=start_update,
        style="Action.TButton",
    )
    button.place(relx=1.0, x=-14, y=14, anchor="ne")
    button.lift()
    app.runtime_update_button = button

    existing = _read_status(status_path)
    if str(existing.get("state") or "") == "pending_restart":
        redraw(existing)

    print(
        "[KVTM DEV] Runtime updater UI READY "
        f"repo={'FOUND' if repo_root else 'MISSING'}",
        flush=True,
    )
