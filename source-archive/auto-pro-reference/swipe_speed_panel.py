from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from engine_driver import SPEED_FILE, load_swipe_speed


class SwipeSpeedPanel(ttk.LabelFrame):
    """Live speed control embedded in the recovered AUTO window."""

    def __init__(self, parent) -> None:
        super().__init__(parent, text="Tốc độ kéo giỏ (Engine Bridge)", padding=6)
        current = load_swipe_speed()
        self.value = tk.DoubleVar(value=current["segment_ms"])
        self.status = tk.StringVar(value=self._description(current["segment_ms"]))

        ttk.Label(self, text="Nhanh").pack(side="left", padx=(4, 2))
        self.scale = ttk.Scale(
            self, from_=20, to=300, orient="horizontal", length=280,
            variable=self.value, command=self._changed,
        )
        self.scale.pack(side="left", padx=4)
        ttk.Label(self, text="Chậm").pack(side="left", padx=(2, 8))
        ttk.Label(self, textvariable=self.status, width=24).pack(side="left", padx=4)
        ttk.Button(self, text="Lưu tốc độ", command=self.save).pack(side="left", padx=6)

    @staticmethod
    def _description(value: int) -> str:
        return f"{int(value)} ms / mỗi đoạn"

    def _changed(self, _value=None) -> None:
        self.status.set(self._description(self.value.get()))

    def save(self) -> None:
        value = max(20, min(300, int(self.value.get())))
        SPEED_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp = Path(str(SPEED_FILE) + ".tmp")
        temp.write_text(json.dumps({
            "segment_ms": value,
            "duration_multiplier": 2.0,
            "minimum_ms": 300,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(SPEED_FILE)
        self.value.set(value)
        self.status.set(self._description(value) + " — đã lưu")
        messagebox.showinfo(
            "KVTM Engine Bridge",
            "Đã lưu tốc độ. Lần kéo giỏ tiếp theo sẽ dùng giá trị mới.",
            parent=self.winfo_toplevel(),
        )


def install_swipe_speed_panel(app) -> SwipeSpeedPanel:
    window = tk.Toplevel(app)
    window.title("KVTM - Chỉnh tốc độ kéo")
    window.resizable(False, False)
    panel = SwipeSpeedPanel(window)
    panel.pack(fill="both", expand=True, padx=8, pady=8)
    panel.speed_window = window
    return panel
