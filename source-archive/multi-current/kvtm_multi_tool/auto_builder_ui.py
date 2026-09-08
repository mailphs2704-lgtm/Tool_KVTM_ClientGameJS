from __future__ import annotations

import auto_builder_model as model
from auto_builder_step_dialogs import configure_step


__all__ = ["install_auto_builder_tab", "AutoBuilderUI"]
FILE_FUNCTIONS = (
    "Gắn tab TỰ TẠO AUTO vào thanh tab Multi DEV",
    "Hiển thị editor theo đúng style hiện tại của Multi DEV",
    "Thêm/sửa/xóa/đổi thứ tự block",
    "Lưu/nạp plan trong data-dev",
    "Gửi plan đã lưu sang isolated AUTO MULTI DEV worker",
)


class AutoBuilderUI:
    def __init__(self, app, core) -> None:
        self.app = app
        self.core = core
        self.store = model.AutoBuilderPlanStore(core.APP_DIR)
        self.plan = self.store.load()
        self.window = None
        self.tree = None
        self.name_var = None
        self.status_var = None
        self._build_tab()

    def _build_tab(self) -> None:
        app, core = self.app, self.core
        tab_host = next(iter(app.auto_feature_tabs.values())).master
        frame = core.ttk.Frame(tab_host, padding=(4, 7), style="Detail.TFrame")
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        frame.place_forget()
        app.auto_feature_tabs["auto_builder"] = frame

        # Match the existing flat Multi DEV tab strip exactly. Do not create a
        # second visual language for Builder.
        button = core.tk.Button(
            app.auto_tabs_window,
            text="TỰ TẠO AUTO",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            background="#e8eef7",
            foreground="#263653",
            activebackground="#dce8f8",
            activeforeground="#1768c4",
            font=("Segoe UI Semibold", 9),
            cursor="hand2",
            padx=6,
            pady=7,
            command=lambda: app._show_auto_tab("auto_builder"),
        )
        anchor = app.auto_tab_buttons.get("multi_dev")
        button.pack(side="left", fill="y", padx=(3, 0), after=anchor)
        app.auto_tab_buttons["auto_builder"] = button

        header = core.ttk.Frame(frame, style="Detail.TFrame")
        header.pack(fill="x", padx=8, pady=(4, 0))
        core.ttk.Label(
            header, text="TỰ TẠO AUTO", style="AutoKey.TLabel"
        ).pack(side="left")
        self.status_var = core.tk.StringVar()
        core.ttk.Label(
            header, textvariable=self.status_var,
            style="AutoValue.TLabel", anchor="e",
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
            text="Module riêng • Function vòng lặp • thứ tự danh sách = thứ tự chạy",
            style="AutoValue.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(5, 0))
        core.ttk.Label(body, text="Block có sẵn", style="AutoKey.TLabel").grid(
            row=0, column=1, sticky="w", padx=(30, 0)
        )
        core.ttk.Label(
            body,
            text="Vào game • Bán VP Function • Function 1 • Nhận diện • Click • Swipe • Wait",
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
            actions, text="▶ Chạy quy trình đã lưu", width=26,
            style="AutoStart.TButton", command=self.run_plan,
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
        win.title("KVTM Multi DEV - Tự tạo AUTO")
        win.geometry("980x620")
        win.minsize(820, 520)
        win.configure(background="#f3f6fa")
        win.protocol("WM_DELETE_WINDOW", lambda: (setattr(self, "window", None), win.destroy()))

        top = core.ttk.Frame(win, padding=(12, 10), style="App.TFrame")
        top.pack(fill="x")
        core.ttk.Label(top, text="Tên quy trình:", style="Key.TLabel").pack(side="left")
        self.name_var = core.tk.StringVar(
            value=str(self.plan.get("name") or "AUTO tự tạo 1")
        )
        core.ttk.Entry(top, textvariable=self.name_var, width=42).pack(
            side="left", padx=(8, 12)
        )
        core.ttk.Label(
            top, text="Thứ tự trong danh sách = thứ tự thực thi",
            style="AutoValue.TLabel",
        ).pack(side="left")

        content = core.ttk.Frame(win, padding=(12, 4), style="App.TFrame")
        content.pack(fill="both", expand=True)
        tree = core.ttk.Treeview(
            content,
            columns=("index", "kind", "detail"),
            show="headings",
            style="Queue.Treeview",
            selectmode="browse",
        )
        self.tree = tree
        tree.heading("index", text="#")
        tree.heading("kind", text="LOẠI")
        tree.heading("detail", text="CẤU HÌNH / THỨ TỰ")
        tree.column("index", width=48, anchor="center", stretch=False)
        tree.column("kind", width=120, anchor="w", stretch=False)
        tree.column("detail", width=620, anchor="w")
        tree.pack(side="left", fill="both", expand=True)
        scroll = core.ttk.Scrollbar(content, orient="vertical", command=tree.yview)
        scroll.pack(side="left", fill="y")
        tree.configure(yscrollcommand=scroll.set)
        tree.bind("<Double-1>", lambda _event: self.modify_step("edit"))

        tools = core.ttk.Frame(content, padding=(10, 0), style="App.TFrame")
        tools.pack(side="right", fill="y")
        add_button = core.ttk.Button(
            tools, text="＋ Thêm bước", width=20, style="Action.TButton"
        )
        add_button.pack(fill="x", pady=(0, 8))
        menu = core.tk.Menu(win, tearoff=False)
        for label, step_type in (
            ("MODULE • Vào game + đóng popup", "enter_game_popup"),
            ("MODULE • Bán VP theo Function", "sell_function_vp"),
            ("FUNCTION • Function 1", "function"),
            ("NHẬN DIỆN • Chọn ảnh", "recognize_image"),
            ("CLICK", "click"),
            ("SWIPE", "swipe"),
            ("WAIT", "wait"),
            ("KẾT THÚC PASS", "finish_pass"),
            ("KẾT THÚC FAIL", "finish_fail"),
        ):
            menu.add_command(
                label=label, command=lambda kind=step_type: self.add_step(kind)
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
                tools, text=text, width=20, style="Action.TButton",
                command=lambda op=action: self.modify_step(op),
            ).pack(fill="x", pady=(0, 8))
        core.ttk.Separator(tools, orient="horizontal").pack(
            fill="x", pady=(4, 10)
        )
        core.ttk.Button(
            tools, text="💾 Lưu quy trình", width=20,
            style="AutoStart.TButton", command=self.save_plan,
        ).pack(fill="x", pady=(0, 8))
        core.ttk.Button(
            tools, text="▶ Lưu + chạy", width=20,
            style="AutoStart.TButton", command=self.run_plan,
        ).pack(fill="x", pady=(0, 8))
        self.refresh_editor()

    def refresh_editor(self) -> None:
        self._refresh_status()
        tree = self.tree
        if tree is None or not tree.winfo_exists():
            return
        selected = tree.selection()
        selected_id = selected[0] if selected else ""
        for item in tree.get_children():
            tree.delete(item)
        for index, step in enumerate(self.plan.get("steps") or [], start=1):
            kind, detail = model.step_summary(step)
            item_id = str(step.get("id") or model.new_step_id())
            step["id"] = item_id
            tree.insert("", "end", iid=item_id, values=(index, kind, detail))
        if selected_id and tree.exists(selected_id):
            tree.selection_set(selected_id)
            tree.see(selected_id)

    def add_step(self, step_type: str) -> None:
        step = configure_step(
            self.core,
            self.store,
            self.window,
            {"id": model.new_step_id(), "type": step_type},
        )
        if step is None:
            return
        self.plan.setdefault("steps", []).append(step)
        self.store.save(self.plan)
        self.refresh_editor()
        if self.tree is not None and self.tree.exists(step["id"]):
            self.tree.selection_set(step["id"])
            self.tree.see(step["id"])

    def modify_step(self, action: str) -> None:
        if self.tree is None:
            return
        selected = self.tree.selection()
        if not selected:
            self.core.messagebox.showinfo(
                self.core.APP_NAME, "Hãy chọn một bước trong quy trình."
            )
            return
        step_id = selected[0]
        steps = self.plan.setdefault("steps", [])
        index = next(
            (i for i, step in enumerate(steps) if str(step.get("id")) == step_id),
            -1,
        )
        if index < 0:
            return
        if action == "edit":
            updated = configure_step(
                self.core, self.store, self.window, dict(steps[index])
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
        self.store.save(self.plan)
        self.refresh_editor()
        if self.tree is not None and self.tree.exists(step_id):
            self.tree.selection_set(step_id)
            self.tree.see(step_id)

    def save_plan(self) -> bool:
        if self.name_var is not None:
            self.plan["name"] = self.name_var.get().strip() or "AUTO tự tạo 1"
        if not self.plan.get("steps"):
            self.core.messagebox.showerror(
                self.core.APP_NAME, "Quy trình phải có ít nhất một bước."
            )
            return False
        self.store.save(self.plan)
        self._refresh_status()
        self.app.note.set(f"AUTO Builder đã lưu: {self.store.plan_path}")
        return True

    def reload_plan(self) -> None:
        self.plan = self.store.load()
        if self.name_var is not None:
            self.name_var.set(str(self.plan.get("name") or "AUTO tự tạo 1"))
        self.refresh_editor()

    def run_plan(self) -> None:
        if not self.save_plan():
            return
        # JSON roundtrip/copy happens in the app before starting each worker, so
        # editor mutations after pressing Run cannot alter an active plan.
        self.app._start_auto_builder_plan(dict(self.plan))

    def _refresh_status(self) -> None:
        if self.status_var is None:
            return
        name = str(self.plan.get("name") or "AUTO tự tạo 1")
        count = len(self.plan.get("steps") or [])
        self.status_var.set(
            f"{name} • {count} bước • lưu trong data-dev/auto-builder"
        )


def install_auto_builder_tab(app, core) -> AutoBuilderUI:
    controller = AutoBuilderUI(app, core)
    app.auto_builder_ui = controller
    return controller
