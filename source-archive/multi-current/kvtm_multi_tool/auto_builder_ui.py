from __future__ import annotations

import copy

import auto_builder_model as model
from auto_builder_step_dialogs import configure_step


__all__ = ["install_auto_builder_tab", "AutoBuilderUI"]
FILE_FUNCTIONS = (
    "Gắn tab TỰ TẠO AUTO vào thanh tab Multi DEV",
    "Hiển thị editor nhiều tab theo đúng style Multi DEV",
    "Tạo và mở đồng thời nhiều Function tự tạo",
    "Load/save Function đã có trong thư viện AppData",
    "Load Function 1 cũ thành full source view module/click/swipe theo đúng thứ tự",
    "Khóa chỉnh sửa blueprint built-in để không giả vờ thay đổi runtime proven workflow",
    "Thêm/sửa/xóa/đổi thứ tự block trong từng tab tự tạo",
    "Chèn block gọi Function đã lưu vào plan/function khác",
    "Lưu/nạp plan chính và chạy snapshot đã bundle Function",
    "Chạy thử riêng tab Function mà không tự chèn module ẩn",
)


class AutoBuilderUI:
    def __init__(self, app, core) -> None:
        self.app = app
        self.core = core
        self.store = model.AutoBuilderPlanStore(core.APP_DIR)
        self.plan = self.store.load()
        self.window = None
        self.notebook = None
        self.documents: dict[str, dict] = {}
        self.status_var = None
        self._build_tab()

    def _build_tab(self) -> None:
        app, core = self.app, self.core
        tab_host = next(iter(app.auto_feature_tabs.values())).master
        frame = core.ttk.Frame(tab_host, padding=(4, 7), style="Detail.TFrame")
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        frame.place_forget()
        app.auto_feature_tabs["auto_builder"] = frame

        # Canvas.create_window returns an integer item id. The real Tk parent is
        # the master of an existing native tab button.
        anchor = app.auto_tab_buttons.get("multi_dev")
        if anchor is None or not hasattr(anchor, "master"):
            raise RuntimeError("Không tìm thấy tab AUTO MULTI DEV để gắn TỰ TẠO AUTO")
        tab_bar = anchor.master
        button = core.tk.Button(
            tab_bar, text="TỰ TẠO AUTO", relief="flat",
            borderwidth=0, highlightthickness=0,
            background="#e8eef7", foreground="#263653",
            activebackground="#dce8f8", activeforeground="#1768c4",
            font=("Segoe UI Semibold", 9), cursor="hand2", padx=6, pady=7,
            command=lambda: app._show_auto_tab("auto_builder"),
        )
        button.pack(side="left", fill="y", padx=(3, 0), after=anchor)
        app.auto_tab_buttons["auto_builder"] = button

        header = core.ttk.Frame(frame, style="Detail.TFrame")
        header.pack(fill="x", padx=8, pady=(4, 0))
        core.ttk.Label(header, text="TỰ TẠO AUTO", style="AutoKey.TLabel").pack(side="left")
        self.status_var = core.tk.StringVar()
        core.ttk.Label(
            header, textvariable=self.status_var, style="AutoValue.TLabel", anchor="e",
        ).pack(side="right", fill="x", expand=True, padx=(18, 0))
        core.ttk.Separator(frame, orient="horizontal").pack(
            fill="x", padx=8, pady=(7, 9)
        )

        body = core.ttk.Frame(frame, style="Detail.TFrame")
        body.pack(fill="x", padx=8)
        core.ttk.Label(body, text="Kiến trúc", style="AutoKey.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        core.ttk.Label(
            body,
            text="Plan chính + nhiều tab Function • thứ tự block = thứ tự chạy",
            style="AutoValue.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(5, 0))
        core.ttk.Label(body, text="Thao tác trực quan", style="AutoKey.TLabel").grid(
            row=0, column=1, sticky="w", padx=(30, 0)
        )
        core.ttk.Label(
            body,
            text="Swipe kéo trực tiếp trên game • ảnh nhận diện • click • wait",
            style="AutoValue.TLabel",
        ).grid(row=1, column=1, sticky="w", padx=(30, 0), pady=(5, 0))
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=2)

        actions = core.ttk.Frame(frame, style="Detail.TFrame")
        actions.pack(fill="x", padx=8, pady=(16, 0))
        core.ttk.Button(
            actions, text="＋ Mở trình tạo AUTO", width=24,
            style="Action.TButton", command=self.open_editor,
        ).pack(side="left", padx=(0, 8))
        core.ttk.Button(
            actions, text="▶ Chạy quy trình chính", width=24,
            style="AutoStart.TButton", command=self.run_main_plan,
        ).pack(side="left", padx=(0, 8))
        core.ttk.Button(
            actions, text="↻ Nạp lại plan", width=18,
            style="Action.TButton", command=self.reload_plan,
        ).pack(side="left")
        self._refresh_status()
        app.after_idle(app._refresh_auto_tab_scroll)

    def open_editor(self) -> None:
        core = self.core
        if self.window is not None and self.window.winfo_exists():
            self.window.lift()
            self.window.focus_force()
            return
        win = core.tk.Toplevel(self.app)
        self.window = win
        self.documents = {}
        win.title("KVTM Multi DEV - Tự tạo AUTO")
        win.geometry("1120x700")
        win.minsize(900, 560)
        win.configure(background="#f3f6fa")

        def close_window() -> None:
            self.window = None
            self.notebook = None
            self.documents = {}
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", close_window)

        toolbar = core.ttk.Frame(win, padding=(12, 10), style="App.TFrame")
        toolbar.pack(fill="x")
        core.ttk.Label(
            toolbar, text="AUTO Builder", style="Key.TLabel"
        ).pack(side="left", padx=(0, 14))
        core.ttk.Button(
            toolbar, text="＋ Function mới", width=18,
            style="Action.TButton", command=self.new_function_tab,
        ).pack(side="left", padx=(0, 8))
        core.ttk.Button(
            toolbar, text="📂 Load Function", width=18,
            style="Action.TButton", command=self.load_function_tab,
        ).pack(side="left", padx=(0, 8))
        core.ttk.Button(
            toolbar, text="💾 Lưu tab hiện tại", width=19,
            style="Action.TButton", command=self.save_current_document,
        ).pack(side="left", padx=(0, 8))
        core.ttk.Button(
            toolbar, text="▶ Chạy tab hiện tại", width=20,
            style="AutoStart.TButton", command=self.run_current_document,
        ).pack(side="left")
        core.ttk.Label(
            toolbar,
            text="Có thể mở nhiều Function cùng lúc; mỗi tab lưu độc lập",
            style="AutoValue.TLabel",
        ).pack(side="right")

        self.notebook = core.ttk.Notebook(win)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._open_document(self.plan, kind="plan", select=True)

    def _open_document(self, data: dict, *, kind: str, select: bool = True) -> None:
        if self.notebook is None:
            return
        key = (
            "plan:main" if kind == "plan"
            else f"function:{str(data.get('function_id') or '')}"
        )
        for tab_id, document in self.documents.items():
            if document["key"] == key:
                if select:
                    self.notebook.select(tab_id)
                return

        core = self.core
        inspection_only = bool(
            kind == "function" and data.get("source_template_id") == "builtin_function_1"
        )
        frame = core.ttk.Frame(self.notebook, padding=(10, 8), style="App.TFrame")
        tab_title = "QUY TRÌNH CHÍNH" if kind == "plan" else str(data.get("name") or "Function")
        self.notebook.add(frame, text=tab_title)
        tab_id = str(frame)
        name_var = core.tk.StringVar(value=str(data.get("name") or tab_title))
        document = {
            "key": key,
            "kind": kind,
            "data": copy.deepcopy(data),
            "frame": frame,
            "tree": None,
            "name_var": name_var,
            "inspection_only": inspection_only,
        }
        self.documents[tab_id] = document

        header = core.ttk.Frame(frame, style="App.TFrame")
        header.pack(fill="x", pady=(0, 8))
        core.ttk.Label(
            header,
            text="Tên quy trình:" if kind == "plan" else "Tên Function:",
            style="Key.TLabel",
        ).pack(side="left")
        name_entry = core.ttk.Entry(header, textvariable=name_var, width=42)
        name_entry.pack(side="left", padx=(8, 12))
        if inspection_only:
            name_entry.configure(state="readonly")
        if kind == "function":
            core.ttk.Label(
                header,
                text=f"ID: {data.get('function_id')}",
                style="AutoValue.TLabel",
            ).pack(side="left")
            if inspection_only:
                core.ttk.Label(
                    header,
                    text="FULL SOURCE VIEW • chỉ đọc • runtime vẫn gọi proven function_1",
                    style="AutoValue.TLabel",
                ).pack(side="left", padx=(14, 0))
        else:
            core.ttk.Label(
                header,
                text="Function tự tạo được gọi bằng block riêng trong plan",
                style="AutoValue.TLabel",
            ).pack(side="left")

        content = core.ttk.Frame(frame, style="App.TFrame")
        content.pack(fill="both", expand=True)
        tree = core.ttk.Treeview(
            content, columns=("index", "kind", "detail"), show="headings",
            style="Queue.Treeview", selectmode="browse",
        )
        document["tree"] = tree
        for column, label in (
            ("index", "#"), ("kind", "LOẠI"), ("detail", "CẤU HÌNH / THỨ TỰ")
        ):
            tree.heading(column, text=label)
        tree.column("index", width=48, anchor="center", stretch=False)
        tree.column("kind", width=150, anchor="w", stretch=False)
        tree.column("detail", width=670, anchor="w")
        tree.pack(side="left", fill="both", expand=True)
        scrollbar = core.ttk.Scrollbar(content, orient="vertical", command=tree.yview)
        scrollbar.pack(side="left", fill="y")
        tree.configure(yscrollcommand=scrollbar.set)
        if not inspection_only:
            tree.bind("<Double-1>", lambda _event, tid=tab_id: self.modify_step("edit", tid))

        tools = core.ttk.Frame(content, padding=(10, 0), style="App.TFrame")
        tools.pack(side="right", fill="y")
        if not inspection_only:
            add_button = core.ttk.Button(
                tools, text="＋ Thêm bước", width=22, style="Action.TButton"
            )
            add_button.pack(fill="x", pady=(0, 8))
            menu = core.tk.Menu(self.window, tearoff=False)
            for label, step_type in (
                ("MODULE • Vào game + đóng popup", "enter_game_popup"),
                ("MODULE • Bán VP theo Function", "sell_function_vp"),
                ("FUNCTION CÓ SẴN • Function 1", "function"),
                ("FUNCTION TỰ TẠO • Gọi Function đã lưu", "call_saved_function"),
                ("NHẬN DIỆN • Chọn ảnh", "recognize_image"),
                ("CLICK", "click"),
                ("SWIPE • kéo trực tiếp trên game", "swipe"),
                ("WAIT", "wait"),
                ("KẾT THÚC PASS", "finish_pass"),
                ("KẾT THÚC FAIL", "finish_fail"),
            ):
                menu.add_command(
                    label=label,
                    command=lambda kind0=step_type, tid=tab_id: self.add_step(kind0, tid),
                )

            def show_add_menu() -> None:
                try:
                    menu.tk_popup(
                        add_button.winfo_rootx(),
                        add_button.winfo_rooty() + add_button.winfo_height(),
                    )
                finally:
                    menu.grab_release()

            add_button.configure(command=show_add_menu)
            for text, action in (
                ("✎ Sửa bước", "edit"),
                ("↑ Đưa lên", "up"),
                ("↓ Đưa xuống", "down"),
                ("✕ Xóa", "delete"),
            ):
                core.ttk.Button(
                    tools, text=text, width=22, style="Action.TButton",
                    command=lambda op=action, tid=tab_id: self.modify_step(op, tid),
                ).pack(fill="x", pady=(0, 8))
            core.ttk.Separator(tools, orient="horizontal").pack(fill="x", pady=(4, 10))
            core.ttk.Button(
                tools, text="💾 Lưu tab", width=22,
                style="AutoStart.TButton",
                command=lambda tid=tab_id: self.save_document(tid),
            ).pack(fill="x", pady=(0, 8))
        else:
            core.ttk.Label(
                tools,
                text="VIEW FULL\nMODULE / CLICK / SWIPE\nWAIT / NHẬN DIỆN\nGATE / LOOP",
                style="AutoValue.TLabel",
                justify="left",
            ).pack(anchor="w", pady=(0, 12))
            core.ttk.Separator(tools, orient="horizontal").pack(fill="x", pady=(4, 10))

        core.ttk.Button(
            tools, text="▶ Chạy tab", width=22,
            style="AutoStart.TButton",
            command=lambda tid=tab_id: self.run_document(tid),
        ).pack(fill="x", pady=(0, 8))
        if kind == "function":
            core.ttk.Button(
                tools, text="＋ Chèn vào plan chính", width=22,
                style="Action.TButton",
                command=lambda tid=tab_id: self.insert_function_into_main(tid),
            ).pack(fill="x", pady=(0, 8))
            core.ttk.Button(
                tools, text="✕ Đóng tab Function", width=22,
                style="Action.TButton",
                command=lambda tid=tab_id: self.close_function_tab(tid),
            ).pack(fill="x")

        self.refresh_document(tab_id)
        if select:
            self.notebook.select(frame)

    def current_tab_id(self) -> str | None:
        if self.notebook is None:
            return None
        selected = self.notebook.select()
        return str(selected) if selected else None

    def new_function_tab(self) -> None:
        if self.window is None:
            self.open_editor()
            return
        name = self.core.simpledialog.askstring(
            "Tạo Function mới", "Tên Function:", initialvalue="Function mới",
            parent=self.window,
        )
        if name is None:
            return
        function = model.new_function(name)
        self.store.save_function(function)
        self._open_document(function, kind="function", select=True)
        self._refresh_status()

    def load_function_tab(self) -> None:
        if self.window is None:
            self.open_editor()
            return
        functions = self.store.list_functions()
        if not functions:
            self.core.messagebox.showinfo(
                self.core.APP_NAME, "Chưa có Function tự tạo đã lưu.", parent=self.window
            )
            return
        prompt = "Chọn số Function cần mở:\n\n" + "\n".join(
            f"{index}. {item['name']}  [{item['function_id']}]"
            for index, item in enumerate(functions, start=1)
        )
        choice = self.core.simpledialog.askinteger(
            "Load Function", prompt, initialvalue=1,
            minvalue=1, maxvalue=len(functions), parent=self.window,
        )
        if choice is None:
            return
        self._open_document(functions[int(choice) - 1], kind="function", select=True)

    def refresh_document(self, tab_id: str) -> None:
        document = self.documents.get(str(tab_id))
        if document is None:
            return
        tree = document["tree"]
        if tree is None or not tree.winfo_exists():
            return
        selected = tree.selection()
        selected_id = selected[0] if selected else ""
        for item in tree.get_children():
            tree.delete(item)
        for index, step in enumerate(document["data"].get("steps") or [], start=1):
            kind, detail = model.step_summary(step)
            item_id = str(step.get("id") or model.new_step_id())
            step["id"] = item_id
            tree.insert("", "end", iid=item_id, values=(index, kind, detail))
        if selected_id and tree.exists(selected_id):
            tree.selection_set(selected_id)
            tree.see(selected_id)

    def add_step(self, step_type: str, tab_id: str | None = None) -> None:
        tab_id = str(tab_id or self.current_tab_id() or "")
        document = self.documents.get(tab_id)
        if document is None:
            return
        if document.get("inspection_only"):
            return
        step = configure_step(
            self.core, self.store, self.window,
            {"id": model.new_step_id(), "type": step_type}, app=self.app,
        )
        if step is None:
            return
        document["data"].setdefault("steps", []).append(step)
        self.save_document(tab_id, quiet=True)
        self.refresh_document(tab_id)
        tree = document["tree"]
        if tree.exists(step["id"]):
            tree.selection_set(step["id"])
            tree.see(step["id"])

    def modify_step(self, action: str, tab_id: str | None = None) -> None:
        tab_id = str(tab_id or self.current_tab_id() or "")
        document = self.documents.get(tab_id)
        if document is None:
            return
        if document.get("inspection_only"):
            self.core.messagebox.showinfo(
                self.core.APP_NAME,
                "Function built-in đang ở FULL SOURCE VIEW chỉ đọc. "
                "Các dòng này phản ánh workflow proven hiện tại, không phải block JSON giả lập.",
                parent=self.window,
            )
            return
        tree = document["tree"]
        selected = tree.selection()
        if not selected:
            self.core.messagebox.showinfo(
                self.core.APP_NAME, "Hãy chọn một bước trong tab hiện tại.", parent=self.window
            )
            return
        step_id = selected[0]
        steps = document["data"].setdefault("steps", [])
        index = next(
            (i for i, step in enumerate(steps) if str(step.get("id")) == step_id), -1
        )
        if index < 0:
            return
        if action == "edit":
            updated = configure_step(
                self.core, self.store, self.window, dict(steps[index]), app=self.app,
            )
            if updated is None:
                return
            steps[index] = updated
        elif action == "up" and index > 0:
            steps[index - 1], steps[index] = steps[index], steps[index - 1]
        elif action == "down" and index + 1 < len(steps):
            steps[index + 1], steps[index] = steps[index], steps[index + 1]
        elif action == "delete":
            if not self.core.messagebox.askyesno(
                self.core.APP_NAME, "Xóa bước đang chọn?", parent=self.window
            ):
                return
            steps.pop(index)
        self.save_document(tab_id, quiet=True)
        self.refresh_document(tab_id)
        if tree.exists(step_id):
            tree.selection_set(step_id)
            tree.see(step_id)

    def save_document(self, tab_id: str, quiet: bool = False) -> bool:
        document = self.documents.get(str(tab_id))
        if document is None:
            return False
        if document.get("inspection_only"):
            return True
        data = document["data"]
        data["name"] = document["name_var"].get().strip()
        if not data["name"]:
            self.core.messagebox.showerror(
                self.core.APP_NAME, "Tên tab không được rỗng.", parent=self.window
            )
            return False
        try:
            if document["kind"] == "plan":
                self.store.save(data)
                self.plan = copy.deepcopy(data)
                title = "QUY TRÌNH CHÍNH"
            else:
                self.store.save_function(data)
                title = data["name"]
            if self.notebook is not None:
                self.notebook.tab(document["frame"], text=title)
        except Exception as exc:
            self.core.messagebox.showerror(
                self.core.APP_NAME, f"Không lưu được Builder tab:\n{exc}", parent=self.window
            )
            return False
        if not quiet:
            self.app.note.set(f"AUTO Builder đã lưu: {data['name']}")
        self._refresh_status()
        return True

    def save_current_document(self) -> None:
        tab_id = self.current_tab_id()
        if tab_id:
            self.save_document(tab_id)

    def save_all_open_documents(self) -> bool:
        for tab_id in tuple(self.documents):
            if not self.save_document(tab_id, quiet=True):
                return False
        return True

    def insert_function_into_main(self, function_tab_id: str) -> None:
        function_document = self.documents.get(str(function_tab_id))
        if function_document is None or function_document["kind"] != "function":
            return
        if not self.save_document(function_tab_id, quiet=True):
            return
        main_id = next(
            (tab_id for tab_id, doc in self.documents.items() if doc["kind"] == "plan"),
            None,
        )
        if main_id is None:
            return
        function = function_document["data"]
        step = {
            "id": model.new_step_id(),
            "type": "call_saved_function",
            "function_id": function["function_id"],
            "function_name": function["name"],
            "loops": 1,
            "sale_after_each_loop": False,
            "sale_function_id": "function_1",
            "sale_timeout": 120.0,
        }
        main = self.documents[main_id]
        main["data"].setdefault("steps", []).append(step)
        self.save_document(main_id, quiet=True)
        self.refresh_document(main_id)
        self.notebook.select(main["frame"])

    def close_function_tab(self, tab_id: str) -> None:
        document = self.documents.get(str(tab_id))
        if document is None or document["kind"] != "function":
            return
        if not self.save_document(tab_id, quiet=True):
            return
        if self.notebook is not None:
            self.notebook.forget(document["frame"])
        self.documents.pop(str(tab_id), None)

    def run_document(self, tab_id: str) -> None:
        document = self.documents.get(str(tab_id))
        if document is None:
            return
        if not self.save_all_open_documents():
            return
        if document["kind"] == "plan":
            self.run_main_plan()
            return
        function = document["data"]
        if not function.get("steps"):
            self.core.messagebox.showerror(
                self.core.APP_NAME, "Function hiện tại chưa có bước nào.", parent=self.window
            )
            return
        test_plan = {
            "version": 1,
            "kind": "plan",
            "name": f"TEST • {function['name']}",
            "steps": [{
                "id": model.new_step_id(),
                "type": "call_saved_function",
                "function_id": function["function_id"],
                "function_name": function["name"],
                "loops": 1,
                "sale_after_each_loop": False,
            }],
        }
        try:
            bundled = self.store.bundle_plan(test_plan)
        except Exception as exc:
            self.core.messagebox.showerror(
                self.core.APP_NAME, f"Không đóng gói được Function:\n{exc}", parent=self.window
            )
            return
        self.app._start_auto_builder_plan(bundled)

    def run_current_document(self) -> None:
        tab_id = self.current_tab_id()
        if tab_id:
            self.run_document(tab_id)
        else:
            self.run_main_plan()

    def run_main_plan(self) -> None:
        if self.window is not None and self.window.winfo_exists():
            if not self.save_all_open_documents():
                return
        else:
            self.plan = self.store.load()
        if not self.plan.get("steps"):
            self.core.messagebox.showerror(
                self.core.APP_NAME, "Quy trình chính phải có ít nhất một bước."
            )
            return
        try:
            bundled = self.store.bundle_plan(self.plan)
        except Exception as exc:
            self.core.messagebox.showerror(
                self.core.APP_NAME, f"Không đóng gói được AUTO Builder:\n{exc}"
            )
            return
        self.app._start_auto_builder_plan(bundled)

    def reload_plan(self) -> None:
        self.plan = self.store.load()
        if self.window is not None and self.window.winfo_exists():
            main_id = next(
                (tab_id for tab_id, doc in self.documents.items() if doc["kind"] == "plan"),
                None,
            )
            if main_id is not None:
                self.documents[main_id]["data"] = copy.deepcopy(self.plan)
                self.documents[main_id]["name_var"].set(self.plan["name"])
                self.refresh_document(main_id)
        self._refresh_status()

    def _refresh_status(self) -> None:
        if self.status_var is None:
            return
        plan = self.store.load()
        functions = self.store.list_functions()
        self.status_var.set(
            f"{plan['name']} • {len(plan.get('steps') or [])} bước • "
            f"{len(functions)} Function đã lưu"
        )


def install_auto_builder_tab(app, core) -> AutoBuilderUI:
    controller = AutoBuilderUI(app, core)
    app.auto_builder_ui = controller
    return controller
