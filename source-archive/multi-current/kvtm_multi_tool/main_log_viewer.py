from __future__ import annotations

from pathlib import Path
import re
import tkinter as tk
from tkinter import ttk


__all__ = ["open_log_window", "open_auto_log_window"]
FILE_FUNCTIONS = (
    "Mở live-tail text window tương thích cho caller cũ",
    "Mở một cửa sổ Log AUTO theo phong cách Log Dọn quầy với ba tab",
    "Log hành động hiển thị dạng bảng Thời gian/Tài khoản/Hành động",
    "Log chi tiết và Log lỗi tự cập nhật mỗi giây",
    "Nút xuất TXT lỗi nằm bên trong tab Log lỗi",
)

_ACTION_RE = re.compile(
    r"^\[(?P<time>[^\]]+)\]\s*\.\s*(?P<account>.*?)\s*\.\s*(?P<message>.*)$"
)


def _safe_read(path: Path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _build_live_text(parent, *, font=("Consolas", 10)):
    frame = ttk.Frame(parent, style="Detail.TFrame")
    frame.pack(fill="both", expand=True)
    text = tk.Text(
        frame,
        bg="#ffffff",
        fg="#263653",
        insertbackground="#263653",
        selectbackground="#cfe2fb",
        selectforeground="#173b67",
        font=font,
        wrap="word",
        relief="flat",
        borderwidth=0,
        highlightthickness=1,
        highlightbackground="#c7d3e3",
        padx=10,
        pady=8,
    )
    scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    text.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    text.configure(state="disabled")
    return text


def _replace_text(text: tk.Text, raw: str) -> None:
    try:
        current = text.get("1.0", "end-1c")
    except tk.TclError:
        return
    if current == raw:
        return
    text.configure(state="normal")
    text.delete("1.0", "end")
    text.insert("1.0", raw)
    text.see("end")
    text.configure(state="disabled")


def open_log_window(parent, path: Path, title: str) -> None:
    """Open one compatibility live-tail text window without blocking Multi GUI."""
    log_path = Path(path)
    window = tk.Toplevel(parent)
    window.title(str(title))
    window.geometry("1050x620")
    window.minsize(720, 360)

    header = ttk.Frame(window, padding=(12, 10, 12, 6), style="Detail.TFrame")
    header.pack(fill="x")
    ttk.Label(header, text=str(title), style="Section.TLabel").pack(side="left")
    ttk.Label(
        header, text="Tự cập nhật mỗi giây", style="AutoValue.TLabel"
    ).pack(side="right")

    body = ttk.Frame(window, padding=(12, 4, 12, 12), style="Detail.TFrame")
    body.pack(fill="both", expand=True)
    text = _build_live_text(body, font=("Consolas", 10))
    state = {"raw": None}

    def refresh() -> None:
        if not window.winfo_exists():
            return
        raw = _safe_read(log_path)
        if raw != state["raw"]:
            state["raw"] = raw
            _replace_text(text, raw)
        window.after(1000, refresh)

    refresh()


def open_auto_log_window(
    parent,
    *,
    action_path: Path,
    detail_path: Path,
    error_path: Path,
    title: str,
    account_name: str,
    export_error_callback=None,
) -> None:
    """Open the operator AUTO log surface with three live tabs.

    The window deliberately mirrors the Dọn quầy log language: one compact
    header, a ttk Notebook, white data surfaces, and one-second refresh. Error
    export is scoped to the Log lỗi tab instead of occupying the main AUTO UI.
    """
    action_path = Path(action_path)
    detail_path = Path(detail_path)
    error_path = Path(error_path)
    for path in (action_path, detail_path, error_path):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
        except OSError:
            pass

    window = tk.Toplevel(parent)
    window.title(str(title))
    window.geometry("980x620")
    window.minsize(760, 430)

    style = ttk.Style(window)
    style.configure(
        "AutoLog.Treeview",
        background="#ffffff",
        fieldbackground="#ffffff",
        foreground="#263653",
        rowheight=27,
        borderwidth=0,
    )
    style.configure(
        "AutoLog.Treeview.Heading",
        background="#e8f1ff",
        foreground="#164b8a",
        relief="flat",
        font=("Segoe UI Semibold", 9),
    )
    style.map(
        "AutoLog.Treeview",
        background=[("selected", "#d8e9ff")],
        foreground=[("selected", "#173b67")],
    )

    header = ttk.Frame(window, padding=(12, 10, 12, 6), style="Detail.TFrame")
    header.pack(fill="x")
    left = ttk.Frame(header, style="Detail.TFrame")
    left.pack(side="left", fill="x", expand=True)
    ttk.Label(left, text="LOG AUTO MULTI DEV", style="Section.TLabel").pack(
        side="left"
    )
    ttk.Label(
        left,
        text=f"  •  {account_name}",
        style="AutoValue.TLabel",
    ).pack(side="left")
    ttk.Label(
        header, text="Tự cập nhật mỗi giây", style="AutoValue.TLabel"
    ).pack(side="right")

    notebook = ttk.Notebook(window)
    notebook.pack(fill="both", expand=True, padx=12, pady=(4, 12))

    action_tab = ttk.Frame(notebook, padding=8, style="Detail.TFrame")
    detail_tab = ttk.Frame(notebook, padding=8, style="Detail.TFrame")
    error_tab = ttk.Frame(notebook, padding=8, style="Detail.TFrame")
    notebook.add(action_tab, text="Log hành động")
    notebook.add(detail_tab, text="Log chi tiết")
    notebook.add(error_tab, text="Log lỗi")

    action_tree = ttk.Treeview(
        action_tab,
        columns=("time", "account", "action"),
        show="headings",
        style="AutoLog.Treeview",
    )
    action_tree.heading("time", text="THỜI GIAN")
    action_tree.heading("account", text="TÀI KHOẢN")
    action_tree.heading("action", text="HÀNH ĐỘNG")
    action_tree.column("time", width=110, minwidth=90, stretch=False, anchor="center")
    action_tree.column("account", width=160, minwidth=110, stretch=False, anchor="w")
    action_tree.column("action", width=620, minwidth=300, stretch=True, anchor="w")
    action_scroll = ttk.Scrollbar(
        action_tab, orient="vertical", command=action_tree.yview
    )
    action_tree.configure(yscrollcommand=action_scroll.set)
    action_tree.pack(side="left", fill="both", expand=True)
    action_scroll.pack(side="right", fill="y")

    detail_text = _build_live_text(detail_tab)

    error_toolbar = ttk.Frame(error_tab, style="Detail.TFrame")
    error_toolbar.pack(fill="x", pady=(0, 7))
    ttk.Label(
        error_toolbar,
        text="Lỗi vận hành đã lưu theo tài khoản",
        style="AutoValue.TLabel",
    ).pack(side="left")
    if callable(export_error_callback):
        ttk.Button(
            error_toolbar,
            text="⇩ Xuất lỗi TXT",
            style="Action.TButton",
            command=export_error_callback,
        ).pack(side="right")
    error_body = ttk.Frame(error_tab, style="Detail.TFrame")
    error_body.pack(fill="both", expand=True)
    error_text = _build_live_text(error_body)

    state = {"action": None, "detail": None, "error": None}

    def refresh_actions(raw: str) -> None:
        if raw == state["action"]:
            return
        state["action"] = raw
        action_tree.delete(*action_tree.get_children())
        for line in raw.splitlines():
            match = _ACTION_RE.match(line.strip())
            if match:
                values = (
                    match.group("time"),
                    match.group("account").strip(),
                    match.group("message").strip(),
                )
            else:
                fallback = line.strip()
                if not fallback:
                    continue
                values = ("", account_name, fallback)
            action_tree.insert("", "end", values=values)
        children = action_tree.get_children()
        if children:
            action_tree.see(children[-1])

    def refresh() -> None:
        if not window.winfo_exists():
            return
        action_raw = _safe_read(action_path)
        detail_raw = _safe_read(detail_path)
        error_raw = _safe_read(error_path)
        refresh_actions(action_raw)
        if detail_raw != state["detail"]:
            state["detail"] = detail_raw
            _replace_text(detail_text, detail_raw)
        if error_raw != state["error"]:
            state["error"] = error_raw
            _replace_text(error_text, error_raw)
        window.after(1000, refresh)

    refresh()
