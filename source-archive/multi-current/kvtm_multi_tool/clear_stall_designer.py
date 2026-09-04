from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import shutil
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk


class ClearStallDesigner:
    def __init__(self, parent, app_dir: Path, tool_dir: Path):
        self.parent = parent
        self.app_dir = Path(app_dir)
        self.tool_dir = Path(tool_dir)
        self.package_root = self.tool_dir.parent
        self.component_root = self.package_root / "components" / "clientjs-auto"
        self.policy_file = (
            self.component_root / "kvtm_automation" / "workflows"
            / "clear_stall" / "designer_policy.py"
        )
        self.config_path = self.app_dir / "clear-stall-workflow-designer.json"
        self.policy_module = self._load_policy_module()
        self.document = self._load_document()
        self._photo = None
        self._drag_index = None
        self._build_launcher()

    def _load_policy_module(self):
        if not self.policy_file.is_file():
            raise RuntimeError(f"Thiếu folder Python Dọn quầy: {self.policy_file}")
        spec = importlib.util.spec_from_file_location("kvtm_clear_stall_designer_policy", self.policy_file)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module

    def _load_document(self):
        if self.config_path.is_file():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                self.policy_module.validate_document(data)
                return data
            except Exception:
                pass
        return self.policy_module.default_document()

    def _build_launcher(self):
        box = ttk.Frame(self.parent)
        box.pack(fill="both", expand=True, padx=12, pady=10)
        ttk.Label(box, text="BẢNG XÂY DỰNG CHỨC NĂNG DỌN QUẦY").pack(anchor="w")
        ttk.Label(
            box,
            text="Chỉnh workflow, template, tọa độ, nhận diện, thời gian và source Python.",
            wraplength=900,
        ).pack(anchor="w", pady=(5, 12))
        ttk.Button(
            box, text="Mở bảng tạo / chỉnh sửa chức năng",
            command=self.open_window,
        ).pack(anchor="w")

    def open_window(self):
        window = tk.Toplevel(self.parent)
        window.title("KVTM • Xây dựng chức năng Dọn quầy")
        window.geometry("1180x760")
        window.minsize(980, 650)
        window.transient(self.parent.winfo_toplevel())
        self.window = window

        toolbar = ttk.Frame(window, padding=8)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Kiểm tra", command=self.validate).pack(side="left")
        ttk.Button(toolbar, text="Áp dụng runtime", command=self.save).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Khôi phục mặc định", command=self.reset).pack(side="left")
        self.status = tk.StringVar(value=f"Folder PY: {self.policy_file.parent}")
        ttk.Label(toolbar, textvariable=self.status).pack(side="right")

        paned = ttk.Panedwindow(window, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        left = ttk.Frame(paned, padding=5)
        right = ttk.Frame(paned, padding=5)
        paned.add(left, weight=2); paned.add(right, weight=5)

        self.tree = ttk.Treeview(
            left, columns=("on", "step", "symbol"), show="headings", selectmode="browse"
        )
        self.tree.heading("on", text="Bật")
        self.tree.heading("step", text="Bước thực thi")
        self.tree.heading("symbol", text="Hàm Python")
        self.tree.column("on", width=42, anchor="center")
        self.tree.column("step", width=210)
        self.tree.column("symbol", width=190)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._select_step)
        self.tree.bind("<Double-1>", self._toggle_step)
        self.tree.bind("<ButtonPress-1>", self._drag_start)
        self.tree.bind("<ButtonRelease-1>", self._drag_end)
        buttons = ttk.Frame(left)
        buttons.pack(fill="x", pady=(5, 0))
        for label, command in (
            ("+ Thêm", self.add_step), ("Nhân bản", self.duplicate_step),
            ("− Xóa", self.remove_step),
        ):
            ttk.Button(buttons, text=label, command=command).pack(side="left", padx=(0, 4))

        tabs = ttk.Notebook(right)
        tabs.pack(fill="both", expand=True)
        detail = ttk.Frame(tabs, padding=10)
        visual = ttk.Frame(tabs, padding=10)
        source = ttk.Frame(tabs, padding=10)
        raw = ttk.Frame(tabs, padding=10)
        tabs.add(detail, text="Chi tiết bước")
        tabs.add(visual, text="Template / tọa độ")
        tabs.add(source, text="Source Python")
        tabs.add(raw, text="JSON runtime")
        self._build_detail(detail)
        self._build_visual(visual)
        self._build_source(source)
        self.raw_text = tk.Text(raw, wrap="none", font=("Consolas", 10))
        self.raw_text.pack(fill="both", expand=True)
        ttk.Button(raw, text="Nạp JSON đang sửa", command=self.load_raw).pack(anchor="e", pady=(5, 0))
        self._refresh_tree()
        self._refresh_raw()

    def _build_detail(self, frame):
        self.fields = {}
        specs = (
            ("label", "Tên bước", "text"), ("id", "Mã bước", "text"),
            ("template", "Template", "text"), ("code_file", "File Python", "text"),
            ("code_symbol", "Hàm / checkpoint", "text"),
        )
        for row, (key, label, _kind) in enumerate(specs):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4)
            var = tk.StringVar()
            entry = ttk.Entry(frame, textvariable=var, width=62)
            entry.grid(row=row, column=1, sticky="ew", pady=4)
            var.trace_add("write", lambda *_args, k=key, v=var: self._field_changed(k, v.get()))
            self.fields[key] = var
        self.policy_vars = {}
        policy_specs = (
            ("recognition_threshold", "Ngưỡng nhận diện"),
            ("recognition_retries", "Số lần retry"),
            ("recognition_retry_wait", "Chờ giữa retry"),
            ("swipe_pulses", "Swipe / một nhịp"),
            ("swipe_duration", "Thời gian swipe"),
            ("swipe_settle", "Chờ render"),
            ("collect_gold_maximum", "Số ô thu vàng/view"),
            ("storage_open_wait", "Chờ mở kho"),
        )
        start = len(specs) + 1
        ttk.Separator(frame).grid(row=start-1, column=0, columnspan=2, sticky="ew", pady=8)
        for offset, (key, label) in enumerate(policy_specs):
            ttk.Label(frame, text=label).grid(row=start+offset, column=0, sticky="w", pady=3)
            var = tk.StringVar()
            ttk.Entry(frame, textvariable=var, width=16).grid(row=start+offset, column=1, sticky="w")
            var.trace_add("write", lambda *_args, k=key, v=var: self._policy_changed(k, v.get()))
            self.policy_vars[key] = var
        frame.columnconfigure(1, weight=1)

    def _build_visual(self, frame):
        self.canvas = tk.Canvas(frame, width=600, height=520, background="#18202b")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._canvas_click)
        self.visual_note = tk.StringVar(value="Chọn bước để xem template và vị trí")
        ttk.Label(frame, textvariable=self.visual_note).pack(fill="x", pady=(5, 0))

    def _build_source(self, frame):
        top = ttk.Frame(frame); top.pack(fill="x")
        self.source_path = tk.StringVar()
        ttk.Entry(top, textvariable=self.source_path).pack(side="left", fill="x", expand=True)
        ttk.Button(top, text="Mở file bước", command=self.open_step_source).pack(side="left", padx=4)
        ttk.Button(top, text="Lưu + backup + AST", command=self.save_source).pack(side="left")
        self.source_text = tk.Text(frame, wrap="none", font=("Consolas", 10), undo=True)
        self.source_text.pack(fill="both", expand=True, pady=(6, 0))

    def _steps(self): return self.document.setdefault("steps", [])
    def _index(self):
        selected = self.tree.selection()
        return int(selected[0]) if selected else None

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for index, step in enumerate(self._steps()):
            self.tree.insert("", "end", iid=str(index), values=(
                "✓" if step.get("enabled", True) else "—",
                step.get("label", step.get("id", "")),
                step.get("code_symbol", ""),
            ))

    def _select_step(self, _event=None):
        index = self._index()
        if index is None: return
        step = self._steps()[index]
        for key, var in self.fields.items(): var.set(str(step.get(key, "")))
        for key, var in self.policy_vars.items(): var.set(str(self.document["policy"].get(key, "")))
        self._draw_step(step)

    def _field_changed(self, key, value):
        index = self._index()
        if index is None: return
        self._steps()[index][key] = value

    def _policy_changed(self, key, value):
        try:
            old = self.document["policy"].get(key)
            self.document["policy"][key] = int(value) if isinstance(old, int) else float(value)
        except (ValueError, TypeError):
            pass

    def _toggle_step(self, _event=None):
        index = self._index()
        if index is not None:
            step = self._steps()[index]
            step["enabled"] = not step.get("enabled", True)
            self._refresh_tree(); self.tree.selection_set(str(index))

    def _drag_start(self, event): self._drag_index = self.tree.identify_row(event.y)
    def _drag_end(self, event):
        target = self.tree.identify_row(event.y)
        if self._drag_index and target and self._drag_index != target:
            step = self._steps().pop(int(self._drag_index))
            self._steps().insert(int(target), step)
            self._refresh_tree(); self.tree.selection_set(target)
        self._drag_index = None

    def add_step(self):
        label = simpledialog.askstring("Thêm bước", "Tên bước:", parent=self.window)
        if label:
            self._steps().append({"id": "custom", "enabled": True, "label": label, "template": "", "code_file": "", "code_symbol": "", "x": 500, "y": 500})
            self._refresh_tree()

    def duplicate_step(self):
        index = self._index()
        if index is not None:
            clone = json.loads(json.dumps(self._steps()[index]))
            clone["id"] = str(clone.get("id", "step")) + "_copy"
            self._steps().insert(index + 1, clone); self._refresh_tree()

    def remove_step(self):
        index = self._index()
        if index is not None:
            self._steps().pop(index); self._refresh_tree()

    def _template_candidates(self, name):
        roots = [self.package_root / "AUTO_PRO", self.component_root]
        found = []
        for root in roots:
            if root.exists() and name:
                found.extend(root.rglob(name + ".png"))
        return found

    def _draw_step(self, step):
        self.canvas.delete("all")
        width = max(1, self.canvas.winfo_width()); height = max(1, self.canvas.winfo_height())
        name = str(step.get("template") or "")
        candidates = self._template_candidates(name)
        if candidates:
            try:
                from PIL import Image, ImageTk
                image = Image.open(candidates[0]).convert("RGB").resize((width, height))
                self._photo = ImageTk.PhotoImage(image)
                self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
            except Exception: pass
        zone = step.get("zone")
        if isinstance(zone, list) and len(zone) == 4:
            x, y, w, h = zone
            self.canvas.create_rectangle(x*width/1000, y*height/1000, (x+w)*width/1000, (y+h)*height/1000, outline="#00ff88", width=2)
        if "x" in step and "y" in step:
            x = int(step["x"])*width/1000; y = int(step["y"])*height/1000
            self.canvas.create_oval(x-6,y-6,x+6,y+6,fill="#ff3b30",outline="white")
        if "x2" in step and "y2" in step:
            x1=int(step.get("x",0))*width/1000; y1=int(step.get("y",0))*height/1000
            x2=int(step["x2"])*width/1000; y2=int(step["y2"])*height/1000
            self.canvas.create_line(x1,y1,x2,y2,fill="#ffd60a",width=3,arrow="last")
        self.visual_note.set(f"Template: {name or '(không có)'} • click ảnh để đổi điểm chính")

    def _canvas_click(self, event):
        index=self._index()
        if index is None:return
        step=self._steps()[index]
        step["x"]=round(event.x*1000/max(1,self.canvas.winfo_width()))
        step["y"]=round(event.y*1000/max(1,self.canvas.winfo_height()))
        self._draw_step(step)

    def _resolve_source(self, step):
        rel=str(step.get("code_file") or "")
        if rel.startswith("worker/"): return self.component_root / rel
        return self.component_root / "kvtm_automation" / rel

    def open_step_source(self):
        index=self._index()
        if index is None:return
        path=self._resolve_source(self._steps()[index])
        self.source_path.set(str(path))
        if path.is_file():
            self.source_text.delete("1.0","end")
            self.source_text.insert("1.0",path.read_text(encoding="utf-8"))

    def save_source(self):
        path=Path(self.source_path.get())
        try:
            text=self.source_text.get("1.0","end-1c")
            ast.parse(text,filename=str(path))
            backup=path.with_suffix(path.suffix+".designer.bak")
            if path.exists(): shutil.copy2(path,backup)
            path.write_text(text,encoding="utf-8")
            self.status.set(f"Đã lưu source; backup: {backup.name}")
        except Exception as exc:
            messagebox.showerror("Source Python",f"Không lưu: {exc}",parent=self.window)

    def _refresh_raw(self):
        if not hasattr(self,"raw_text"):return
        self.raw_text.delete("1.0","end")
        self.raw_text.insert("1.0",json.dumps(self.document,ensure_ascii=False,indent=2))

    def load_raw(self):
        try:
            document=json.loads(self.raw_text.get("1.0","end-1c"))
            self.policy_module.validate_document(document)
            self.document=document; self._refresh_tree()
            self.status.set("JSON hợp lệ và đã nạp")
        except Exception as exc:
            messagebox.showerror("JSON runtime",str(exc),parent=self.window)

    def validate(self):
        try:
            self.policy_module.validate_document(self.document)
            self.status.set("VALID: workflow và policy có thể áp dụng")
            messagebox.showinfo("Dọn quầy","Cấu hình hợp lệ.",parent=self.window)
            return True
        except Exception as exc:
            messagebox.showerror("Dọn quầy",str(exc),parent=self.window)
            return False

    def save(self):
        if not self.validate(): return
        self.policy_module.save_document(self.document,self.config_path)
        self._refresh_raw()
        self.status.set(f"Đã áp dụng runtime: {self.config_path}")

    def reset(self):
        if messagebox.askyesno("Dọn quầy","Khôi phục toàn bộ workflow mặc định?",parent=self.window):
            self.document=self.policy_module.default_document()
            self._refresh_tree(); self._refresh_raw()


def build_clear_stall_designer(parent, app_dir: Path, tool_dir: Path):
    return ClearStallDesigner(parent, app_dir, tool_dir)
