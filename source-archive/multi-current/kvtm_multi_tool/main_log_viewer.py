from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk


__all__ = ["open_log_window"]
FILE_FUNCTIONS = (
    "Mở cửa sổ log nền tối theo phong cách console",
    "Đọc bổ sung nội dung UTF-8 khi file log thay đổi",
    "Tự cuộn đến dòng mới nhất trong lúc AUTO chạy",
)


def open_log_window(parent, path: Path, title: str) -> None:
    """Open one live-tail text window without blocking the Multi GUI."""
    log_path = Path(path)
    window = tk.Toplevel(parent)
    window.title(str(title))
    window.geometry("1050x620")
    window.minsize(720, 360)

    frame = ttk.Frame(window)
    frame.pack(fill="both", expand=True)
    text = tk.Text(
        frame,
        bg="#202020",
        fg="#f1f1f1",
        insertbackground="#f1f1f1",
        selectbackground="#365f8d",
        font=("Consolas", 11),
        wrap="word",
        relief="flat",
        padx=10,
        pady=8,
    )
    scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    text.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    text.configure(state="disabled")

    state = {"offset": 0}

    def refresh() -> None:
        if not window.winfo_exists():
            return
        try:
            size = log_path.stat().st_size
            if size < state["offset"]:
                state["offset"] = 0
                text.configure(state="normal")
                text.delete("1.0", "end")
                text.configure(state="disabled")
            if size > state["offset"]:
                with log_path.open("r", encoding="utf-8", errors="replace") as stream:
                    stream.seek(state["offset"])
                    chunk = stream.read()
                    state["offset"] = stream.tell()
                text.configure(state="normal")
                text.insert("end", chunk)
                text.see("end")
                text.configure(state="disabled")
        except OSError:
            pass
        window.after(500, refresh)

    refresh()
