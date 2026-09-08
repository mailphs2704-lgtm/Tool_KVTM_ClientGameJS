from __future__ import annotations

import json
from pathlib import Path

from auto_builder_ui import install_auto_builder_tab


__all__ = ["install_auto_builder_integration"]
FILE_FUNCTIONS = (
    "Gắn Builder UI sau khi panel Multi DEV gốc được tạo",
    "Đưa plan Builder vào đúng worker run bằng marker riêng trong work-dir",
    "Khởi chạy Builder qua lifecycle/ownership hiện có của AUTO MULTI DEV",
    "Ẩn tab Thiết kế cũ khỏi hàng chức năng của Multi DEV",
    "Thay khối mô tả AUTO MULTI DEV bằng menu chọn Function + số vòng giữa hai lần bán",
    "Hiển thị trực tiếp thời gian chờ giữa các vòng Function trên AUTO MULTI DEV",
    "Bổ sung Tốc độ thu VP vào đúng cửa sổ Cấu hình tốc độ hiện có",
    "Đưa Log hành động + Log chi tiết xuống hàng riêng dưới nút AUTO MULTI DEV",
    "Ghi cấu hình Function AUTO Main theo từng run mà không thay Bridge/capture ownership",
    "Hiển thị kết quả Builder mà không thay đổi handler AUTO chính",
)

_AUTO_MAIN_FUNCTION_OPTIONS = (
    ("function_1", "9 Táo sấy - 9 Vải vàng"),
)


def _install_vp_collect_speed_control(core) -> None:
    """Extend the native Multi DEV speed dialog with one clean-only timing."""
    core.DEFAULT_AUTO_TUNING.setdefault("vp_collect_delay", 0.30)
    keys = tuple(getattr(core, "MULTI_DEV_TUNING_KEYS", ()))
    if "vp_collect_delay" not in keys:
        try:
            index = keys.index("vp_production_delay")
        except ValueError:
            keys = keys + ("vp_collect_delay",)
        else:
            keys = keys[:index] + ("vp_collect_delay",) + keys[index:]
        core.MULTI_DEV_TUNING_KEYS = keys
    core.AUTO_TUNING_SPECS["vp_collect_delay"] = (
        "Thu VP (giây/click)", 0.05, 5.0, False
    )
    core.AUTO_LEGACY_TUNING_KEYS = tuple(
        key for key in core.DEFAULT_AUTO_TUNING
        if key not in core.MULTI_DEV_TUNING_KEYS
    )


def install_auto_builder_integration(app_class, core) -> None:
    """Add Builder and the verified AUTO Main controls to Multi DEV."""
    if getattr(app_class, "_kvtm_auto_builder_installed", False):
        return

    _install_vp_collect_speed_control(core)

    original_build = app_class._build_auto_panel
    original_start_clean_session = app_class._start_clean_auto_session
    original_run_thread = app_class._run_clean_main_thread
    original_finish = app_class._finish_clean_main

    def _select_auto_multi_dev_function(self, function_id: str) -> None:
        options = dict(_AUTO_MAIN_FUNCTION_OPTIONS)
        if function_id not in options:
            return
        self._auto_multi_dev_selected_function_id = function_id
        self.auto_multi_dev_function_label.set(options[function_id])

    def _apply_requested_dev_layout(self) -> None:
        tab_buttons = getattr(self, "auto_tab_buttons", {})
        designer_button = tab_buttons.get("clear_stall_designer")
        if designer_button is not None:
            try:
                designer_button.pack_forget()
            except Exception:
                pass

        start_button = getattr(self, "auto_multi_dev_start_button", None)
        action_log = getattr(self, "auto_multi_dev_action_log_button", None)
        detail_log = getattr(self, "auto_multi_dev_detail_log_button", None)
        multi_dev_tab = getattr(self, "auto_feature_tabs", {}).get("multi_dev")
        if (
            start_button is None
            or action_log is None
            or detail_log is None
            or multi_dev_tab is None
        ):
            return

        clean_actions = start_button.master

        for child in list(multi_dev_tab.winfo_children()):
            if child is clean_actions:
                break
            try:
                child.destroy()
            except Exception:
                pass

        controls = core.ttk.Frame(multi_dev_tab, style="Detail.TFrame")
        controls.pack(fill="x", padx=8, pady=(4, 2), before=clean_actions)
        controls.columnconfigure(0, weight=3)
        controls.columnconfigure(1, weight=2)
        controls.columnconfigure(2, weight=2)
        controls.columnconfigure(3, weight=3)

        function_box = core.ttk.Frame(controls, style="Detail.TFrame")
        function_box.grid(row=0, column=0, sticky="ew", padx=(0, 14))
        core.ttk.Label(
            function_box, text="CHỨC NĂNG", style="AutoKey.TLabel"
        ).pack(anchor="w")

        default_id, default_label = _AUTO_MAIN_FUNCTION_OPTIONS[0]
        self._auto_multi_dev_selected_function_id = default_id
        self.auto_multi_dev_function_label = core.tk.StringVar(value=default_label)
        self.auto_multi_dev_function_button = core.tk.Menubutton(
            function_box,
            textvariable=self.auto_multi_dev_function_label,
            background="#ffffff",
            foreground="#263653",
            activebackground="#e8f1ff",
            activeforeground="#1768c4",
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#c7d3e3",
            highlightcolor="#2f80ed",
            font=("Segoe UI Semibold", 10),
            anchor="w",
            cursor="hand2",
            padx=11,
            pady=7,
            indicatoron=True,
        )
        function_menu = core.tk.Menu(
            self.auto_multi_dev_function_button,
            tearoff=False,
            background="#ffffff",
            foreground="#263653",
            activebackground="#2f80ed",
            activeforeground="#ffffff",
            relief="flat",
            borderwidth=1,
            font=("Segoe UI", 10),
        )
        for function_id, label in _AUTO_MAIN_FUNCTION_OPTIONS:
            function_menu.add_command(
                label=label,
                command=lambda selected=function_id: self._select_auto_multi_dev_function(selected),
            )
        self.auto_multi_dev_function_button.configure(menu=function_menu)
        self.auto_multi_dev_function_button.pack(fill="x", pady=(4, 0))

        sale_box = core.ttk.Frame(controls, style="Detail.TFrame")
        sale_box.grid(row=0, column=1, sticky="ew", padx=(0, 14))
        core.ttk.Label(
            sale_box, text="SỐ VÒNG GIỮA 2 LẦN BÁN", style="AutoKey.TLabel"
        ).pack(anchor="w")
        self.auto_multi_dev_sale_every_loops = core.tk.IntVar(value=1)
        self.auto_multi_dev_sale_every_spin = core.ttk.Spinbox(
            sale_box,
            from_=1,
            to=999,
            width=10,
            textvariable=self.auto_multi_dev_sale_every_loops,
        )
        self.auto_multi_dev_sale_every_spin.pack(anchor="w", pady=(6, 0))

        delay_box = core.ttk.Frame(controls, style="Detail.TFrame")
        delay_box.grid(row=0, column=2, sticky="ew", padx=(0, 14))
        core.ttk.Label(
            delay_box,
            text="CHỜ GIỮA VÒNG FUNCTION (GIÂY)",
            style="AutoKey.TLabel",
        ).pack(anchor="w")
        self.auto_multi_dev_function_loop_delay = core.tk.DoubleVar(value=0.0)
        self.auto_multi_dev_function_loop_delay_spin = core.ttk.Spinbox(
            delay_box,
            from_=0.0,
            to=3600.0,
            increment=1.0,
            width=10,
            textvariable=self.auto_multi_dev_function_loop_delay,
        )
        self.auto_multi_dev_function_loop_delay_spin.pack(anchor="w", pady=(6, 0))

        note_box = core.ttk.Frame(controls, style="Detail.TFrame")
        note_box.grid(row=0, column=3, sticky="ew")
        core.ttk.Label(
            note_box,
            text=(
                "Vào game + đóng popup → bán VP lần 1 → chạy Function. "
                "Ô chờ chỉ áp dụng giữa hai vòng Function; không tác động thao tác khác."
            ),
            style="AutoValue.TLabel",
            anchor="w",
            justify="left",
            wraplength=310,
        ).pack(fill="x", pady=(17, 0))

        start_button.configure(command=self._start_configured_auto_main)

        if action_log.master is clean_actions and detail_log.master is clean_actions:
            try:
                action_log.pack_forget()
                detail_log.pack_forget()
                log_row = core.ttk.Frame(multi_dev_tab, style="Detail.TFrame")
                log_row.pack(fill="x", padx=8, pady=(6, 0), after=clean_actions)
                self.auto_multi_dev_action_log_button = core.ttk.Button(
                    log_row,
                    text="≡ Log hành động",
                    width=18,
                    style="Action.TButton",
                    command=lambda: self._open_clean_main_log("action"),
                )
                self.auto_multi_dev_action_log_button.pack(side="left", padx=(0, 8))
                self.auto_multi_dev_detail_log_button = core.ttk.Button(
                    log_row,
                    text="⌕ Log chi tiết",
                    width=18,
                    style="Action.TButton",
                    command=lambda: self._open_clean_main_log("detail"),
                )
                self.auto_multi_dev_detail_log_button.pack(side="left")
            except Exception:
                try:
                    action_log.pack(side="left", padx=(0, 8))
                    detail_log.pack(side="left")
                    self.auto_multi_dev_action_log_button = action_log
                    self.auto_multi_dev_detail_log_button = detail_log
                except Exception:
                    pass

        refresh_tabs = getattr(self, "_refresh_auto_tab_scroll", None)
        if callable(refresh_tabs):
            self.after_idle(refresh_tabs)

    def build_auto_panel(self) -> None:
        original_build(self)
        self._auto_builder_pending_plans: dict[str, dict] = {}
        self._auto_main_pending_config: dict[str, dict] = {}
        _apply_requested_dev_layout(self)
        install_auto_builder_tab(self, core)

    def start_configured_auto_main(self) -> None:
        selected = list(map(str, self.selected_ids()))
        if not selected:
            core.messagebox.showinfo(
                core.APP_NAME, "Hãy chọn ít nhất một tài khoản để chạy AUTO MULTI DEV."
            )
            return

        function_id = str(
            getattr(self, "_auto_multi_dev_selected_function_id", "function_1")
        )
        valid_ids = {item[0] for item in _AUTO_MAIN_FUNCTION_OPTIONS}
        if function_id not in valid_ids:
            core.messagebox.showerror(core.APP_NAME, "Chức năng AUTO MULTI DEV chưa hợp lệ.")
            return
        try:
            sale_every = int(self.auto_multi_dev_sale_every_loops.get())
        except (TypeError, ValueError, core.tk.TclError):
            sale_every = 0
        if not 1 <= sale_every <= 999:
            core.messagebox.showerror(
                core.APP_NAME, "Số vòng giữa 2 lần bán phải trong khoảng 1..999."
            )
            return
        self.auto_multi_dev_sale_every_loops.set(sale_every)

        try:
            loop_delay = float(self.auto_multi_dev_function_loop_delay.get())
        except (TypeError, ValueError, core.tk.TclError):
            loop_delay = -1.0
        if not 0.0 <= loop_delay <= 3600.0:
            core.messagebox.showerror(
                core.APP_NAME,
                "Thời gian chờ giữa vòng Function phải trong khoảng 0..3600 giây.",
            )
            return
        self.auto_multi_dev_function_loop_delay.set(loop_delay)

        config = {
            "version": 1,
            "function_id": function_id,
            "sale_every_loops": sale_every,
            "function_loop_delay_seconds": loop_delay,
        }
        for profile_id in selected:
            self._auto_main_pending_config[profile_id] = dict(config)

        label = dict(_AUTO_MAIN_FUNCTION_OPTIONS)[function_id]
        self.note.set(
            f"AUTO MULTI DEV • {label} • bán lại sau {sale_every} vòng • "
            f"chờ giữa vòng {loop_delay:g}s"
        )
        original_start_clean_session(self)

    def run_clean_main_thread(self, *args, **kwargs) -> None:
        profile_id = str(args[0] if args else kwargs.get("profile_id") or "")
        work_dir = Path(args[3] if len(args) > 3 else kwargs["work_dir"])
        plan = self._auto_builder_pending_plans.pop(profile_id, None)
        if plan is not None:
            work_dir.mkdir(parents=True, exist_ok=True)
            marker = work_dir / "auto-builder-plan.json"
            marker.write_text(
                json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        else:
            config = self._auto_main_pending_config.pop(profile_id, None)
            if config is not None:
                work_dir.mkdir(parents=True, exist_ok=True)
                marker = work_dir / "auto-main-config.json"
                marker.write_text(
                    json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
        return original_run_thread(self, *args, **kwargs)

    def finish_clean_main(self, profile_id: str, outcome: str, payload: dict) -> None:
        if outcome != "auto_builder_ready":
            return original_finish(self, profile_id, outcome, payload)

        self._clean_main_threads.pop(profile_id, None)
        self._clean_main_workers.pop(profile_id, None)
        self._clean_main_stop_events.pop(profile_id, None)
        completed = int(payload.get("completed_steps", 0) or 0)
        total = int(payload.get("total_steps", 0) or 0)
        plan_name = str(payload.get("plan_name") or "AUTO tự tạo")
        outcome_text = str(payload.get("outcome") or "completed").upper()
        status = (
            f"AUTO Builder {outcome_text} • {plan_name} • bước {completed}/{total}"
        )
        self.auto_multi_dev_status.set(status)
        self.note.set(status)
        controller = getattr(self, "auto_builder_ui", None)
        if controller is not None and controller.status_var is not None:
            controller.status_var.set(status)

    def start_auto_builder_plan(self, plan: dict) -> None:
        selected = list(map(str, self.selected_ids()))
        if not selected:
            core.messagebox.showinfo(
                core.APP_NAME, "Hãy chọn ít nhất một tài khoản để chạy AUTO Builder."
            )
            return
        try:
            frozen = json.loads(json.dumps(plan, ensure_ascii=False))
        except (TypeError, ValueError) as exc:
            core.messagebox.showerror(
                core.APP_NAME, f"Plan AUTO Builder không thể chạy:\n{exc}"
            )
            return
        if not isinstance(frozen, dict) or not isinstance(frozen.get("steps"), list):
            core.messagebox.showerror(core.APP_NAME, "Plan AUTO Builder không hợp lệ.")
            return

        previous_threads = {
            profile_id: self._clean_main_threads.get(profile_id)
            for profile_id in selected
        }
        for profile_id in selected:
            self._auto_builder_pending_plans[profile_id] = frozen

        self._start_clean_auto_session()

        launched = 0
        for profile_id in selected:
            current = self._clean_main_threads.get(profile_id)
            if current is None or current is previous_threads[profile_id]:
                self._auto_builder_pending_plans.pop(profile_id, None)
                continue
            launched += 1
        if launched:
            name = str(frozen.get("name") or "AUTO tự tạo")
            status = f"AUTO Builder • đang chạy {name} • {launched} tài khoản"
            self.auto_multi_dev_status.set(status)
            self.note.set(status)
            controller = getattr(self, "auto_builder_ui", None)
            if controller is not None and controller.status_var is not None:
                controller.status_var.set(status)

    app_class._build_auto_panel = build_auto_panel
    app_class._run_clean_main_thread = run_clean_main_thread
    app_class._finish_clean_main = finish_clean_main
    app_class._start_auto_builder_plan = start_auto_builder_plan
    app_class._select_auto_multi_dev_function = _select_auto_multi_dev_function
    app_class._start_configured_auto_main = start_configured_auto_main
    app_class._kvtm_auto_builder_installed = True
