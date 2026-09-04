from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

DEFAULT_STEPS = [
    {"id": "open_stall", "label": "Mở quầy", "template": "quay_hang_friend", "code": "stall.py: open_friend_stall", "x": 896, "y": 482},
    {"id": "scan", "label": "Scan cả hai hàng", "template": "quay_hang_friend", "code": "clear_stall_probe_runtime.py: scan_buy_stall", "x": 500, "y": 550},
    {"id": "buy", "label": "Mua VP hợp lệ", "template": "", "code": "buying.py: buy_from_listing", "x": 500, "y": 550},
    {"id": "swipe_1", "label": "Kéo quầy swipe 1/2", "template": "quay_hang_friend", "code": "stall.py: next_view", "x": 633, "y": 546, "x2": 540, "y2": 540},
    {"id": "swipe_2", "label": "Kéo quầy swipe 2/2", "template": "quay_hang_friend", "code": "stall.py: next_view", "x": 633, "y": 546, "x2": 540, "y2": 540},
    {"id": "scan_next", "label": "Bắt buộc scan view kế", "template": "quay_hang_friend", "code": "clear_stall_probe_runtime.py: stall-step-finished-scan-required", "x": 500, "y": 550},
]


class ClearStallDesigner:
    def __init__(self, parent, app_dir: Path, tool_dir: Path):
        self.parent = parent
        self.config_path = Path(app_dir) / "clear-stall-workflow-designer.json"
        self.tool_dir = Path(tool_dir)
        self.steps = self._load()
        self._photo = None
        self._drag_item = None
        self._build()
        self._render_rows()

    def _load(self):
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass
        return [dict(item) for item in DEFAULT_STEPS]

    def _build(self):
        left = ttk.Frame(self.parent)
        left.pack(side="left", fill="both", expand=True, padx=(4, 8))
        self.tree = ttk.Treeview(left, columns=("step", "code"), show="headings", height=7)
        self.tree.heading("step", text="Bước thực thi")
        self.tree.heading("code", text="Vị trí code PY")
        self.tree.column("step", width=190)
        self.tree.column("code", width=310)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._select)
        self.tree.bind("<ButtonPress-1>", self._drag_start)
        self.tree.bind("<ButtonRelease-1>", self._drag_end)
        bar = ttk.Frame(left)
        bar.pack(fill="x", pady=(4, 0))
        ttk.Button(bar, text="+ Thêm", command=self._add).pack(side="left")
        ttk.Button(bar, text="− Bớt", command=self._remove).pack(side="left", padx=4)
        ttk.Button(bar, text="Lưu bố cục", command=self._save).pack(side="right")

        right = ttk.Frame(self.parent)
        right.pack(side="right", fill="y")
        self.canvas = tk.Canvas(right, width=210, height=150, background="#18202b", highlightthickness=1)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._move_point)
        self.detail = tk.StringVar(value="Chọn một bước")
        ttk.Label(right, textvariable=self.detail, wraplength=220).pack(fill="x", pady=(4, 2))
        row = ttk.Frame(right)
        row.pack()
        self.x = tk.IntVar(value=0); self.y = tk.IntVar(value=0)
        ttk.Label(row, text="X").pack(side="left")
        ttk.Spinbox(row, from_=0, to=1000, width=5, textvariable=self.x, command=self._coordinate_changed).pack(side="left")
        ttk.Label(row, text="Y").pack(side="left", padx=(6, 0))
        ttk.Spinbox(row, from_=0, to=1000, width=5, textvariable=self.y, command=self._coordinate_changed).pack(side="left")

    def _render_rows(self):
        self.tree.delete(*self.tree.get_children())
        for index, step in enumerate(self.steps):
            self.tree.insert("", "end", iid=str(index), values=(step.get("label"), step.get("code")))

    def _selected_index(self):
        selected = self.tree.selection()
        return int(selected[0]) if selected else None

    def _select(self, _event=None):
        index = self._selected_index()
        if index is None: return
        step = self.steps[index]
        self.x.set(int(step.get("x", 0))); self.y.set(int(step.get("y", 0)))
        self.detail.set(f"Template: {step.get('template') or '(không có)'}\n{step.get('code', '')}")
        self._draw(step)

    def _draw(self, step):
        self.canvas.delete("all")
        template = str(step.get("template") or "")
        candidates = list(self.tool_dir.parent.rglob(template + ".png")) if template else []
        if candidates:
            try:
                from PIL import Image, ImageTk
                image = Image.open(candidates[0]).convert("RGB")
                image.thumbnail((210, 150))
                self._photo = ImageTk.PhotoImage(image)
                self.canvas.create_image(105, 75, image=self._photo)
            except Exception:
                pass
        x = int(step.get("x", 0)) * 210 / 1000
        y = int(step.get("y", 0)) * 150 / 1000
        self.canvas.create_oval(x-5, y-5, x+5, y+5, fill="#ff3b30", outline="white", tags="point")

    def _move_point(self, event):
        index = self._selected_index()
        if index is None: return
        self.steps[index]["x"] = round(event.x * 1000 / 210)
        self.steps[index]["y"] = round(event.y * 1000 / 150)
        self._select()

    def _coordinate_changed(self):
        index = self._selected_index()
        if index is None: return
        self.steps[index]["x"] = int(self.x.get()); self.steps[index]["y"] = int(self.y.get())
        self._draw(self.steps[index])

    def _drag_start(self, event):
        self._drag_item = self.tree.identify_row(event.y)

    def _drag_end(self, event):
        target = self.tree.identify_row(event.y)
        if self._drag_item and target and self._drag_item != target:
            item = self.steps.pop(int(self._drag_item))
            self.steps.insert(int(target), item)
            self._render_rows()
            self.tree.selection_set(str(int(target)))
        self._drag_item = None

    def _add(self):
        label = simpledialog.askstring("Thêm bước", "Tên bước thực thi:", parent=self.parent)
        if label:
            self.steps.append({"id": "custom", "label": label, "template": "", "code": "custom", "x": 500, "y": 500})
            self._render_rows()

    def _remove(self):
        index = self._selected_index()
        if index is not None:
            self.steps.pop(index); self._render_rows()

    def _save(self):
        required = {"scan", "buy", "swipe_1", "swipe_2", "scan_next"}
        present = {str(item.get("id")) for item in self.steps}
        if not required.issubset(present):
            messagebox.showerror("Dọn quầy", "Không được thiếu scan, buy, 2 swipe và scan view kế.")
            return
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(self.steps, ensure_ascii=False, indent=2), encoding="utf-8")
        messagebox.showinfo("Dọn quầy", "Đã lưu bố cục thiết kế và tọa độ.")


def build_clear_stall_designer(parent, app_dir: Path, tool_dir: Path):
    return ClearStallDesigner(parent, app_dir, tool_dir)
