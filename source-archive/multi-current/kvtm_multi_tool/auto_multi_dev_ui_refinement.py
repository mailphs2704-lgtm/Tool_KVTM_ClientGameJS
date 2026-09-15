from __future__ import annotations


__all__ = ["install_auto_multi_dev_ui_refinement"]

FILE_FUNCTIONS = (
    "Nới rộng ô Chức năng và bỏ cột Tài khoản áp dụng khỏi AUTO MULTI DEV",
    "Khóa trạng thái operator chỉ còn Đang chạy hoặc Đã dừng",
    "Mở Cấu hình gọn bên trong cửa sổ Multi rồi vẫn cho phép kéo tự do",
    "Giữ Vòng lặp/Thời gian chờ trong Cấu hình bằng Entry nhập trực tiếp",
    "Không hủy widget scheduler ẩn đang giữ persistence theo tài khoản",
)


def install_auto_multi_dev_ui_refinement(app_class, core) -> None:
    """Apply the operator's second-pass compact UI without touching AUTO logic."""
    if getattr(app_class, "_kvtm_auto_multi_dev_ui_refinement_installed", False):
        return

    original_apply_layout = app_class._apply_compact_auto_multi_dev_layout
    original_start_clean = app_class._start_clean_auto_session
    original_stop_clean = app_class._stop_clean_auto_session
    original_finish_clean = app_class._finish_clean_main

    def _place_auto_child_window(
        self,
        window,
        *,
        preferred_width: int,
        preferred_height: int,
        min_width: int,
        min_height: int,
    ) -> None:
        """Place a new child fully inside Multi on first show; movement stays free."""
        try:
            self.update_idletasks()
            window.update_idletasks()
            parent_x = int(self.winfo_rootx())
            parent_y = int(self.winfo_rooty())
            parent_w = max(1, int(self.winfo_width()))
            parent_h = max(1, int(self.winfo_height()))
            margin = 22
            available_w = max(320, parent_w - margin * 2)
            available_h = max(260, parent_h - margin * 2)
            effective_min_w = min(int(min_width), available_w)
            effective_min_h = min(int(min_height), available_h)
            width = max(effective_min_w, min(int(preferred_width), available_w))
            height = max(effective_min_h, min(int(preferred_height), available_h))
            x = parent_x + max(margin, (parent_w - width) // 2)
            y = parent_y + max(margin, (parent_h - height) // 2)
            window.minsize(effective_min_w, effective_min_h)
            window.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            # Geometry is cosmetic only; never block AUTO because a window manager
            # rejected one placement request.
            pass

    def _auto_multi_dev_has_running_worker(self) -> bool:
        for thread in tuple(getattr(self, "_clean_main_threads", {}).values()):
            try:
                if thread is not None and thread.is_alive():
                    return True
            except Exception:
                continue
        for worker in tuple(getattr(self, "_clean_main_workers", {}).values()):
            try:
                if worker is not None and worker.poll() is None:
                    return True
            except Exception:
                continue
        return False

    def _set_auto_multi_dev_operator_status(self, value: str) -> None:
        status = getattr(self, "auto_multi_dev_operator_status", None)
        if status is None:
            return
        normalized = "Đang chạy" if str(value) == "Đang chạy" else "Đã dừng"
        try:
            status.set(normalized)
        except Exception:
            pass

    def _sync_auto_multi_dev_operator_status(self) -> None:
        self._set_auto_multi_dev_operator_status(
            "Đang chạy" if self._auto_multi_dev_has_running_worker() else "Đã dừng"
        )

    def _apply_refined_auto_multi_dev_layout(self) -> None:
        original_apply_layout(self)

        function_button = getattr(self, "auto_multi_dev_function_button", None)
        if function_button is None:
            return
        function_box = function_button.master
        controls = function_box.master

        # Preserve hidden scheduler controls because profile persistence still
        # reads/writes those widget variables even though they are not operator UI.
        protected_parents = set()
        for attribute in (
            "auto_multi_dev_sale_every_spin",
            "auto_multi_dev_function_loop_delay_spin",
            "auto_multi_dev_friend_refresh_button",
            "auto_multi_dev_pirate_chest_button",
        ):
            widget = getattr(self, attribute, None)
            parent = getattr(widget, "master", None)
            if parent is not None:
                protected_parents.add(parent)

        # Remove only the visible Tài khoản/Trạng thái boxes from the previous
        # compact layer. Hidden scheduler frames remain alive.
        try:
            visible = list(controls.grid_slaves())
        except Exception:
            visible = []
        for child in visible:
            if child is function_box or child in protected_parents:
                continue
            try:
                info = child.grid_info()
                row = int(info.get("row", -1))
                column = int(info.get("column", -1))
            except Exception:
                continue
            if row == 0 and column in (1, 2, 3, 4):
                try:
                    child.destroy()
                except Exception:
                    pass

        for column in range(5):
            controls.columnconfigure(column, weight=0)
        controls.columnconfigure(0, weight=5, minsize=470)
        controls.columnconfigure(1, weight=2, minsize=150)
        function_box.grid_configure(
            row=0,
            column=0,
            columnspan=1,
            sticky="ew",
            padx=(0, 18),
        )
        try:
            function_button.configure(width=48, anchor="w")
        except Exception:
            pass

        self.auto_multi_dev_operator_status = core.tk.StringVar(
            value=(
                "Đang chạy"
                if self._auto_multi_dev_has_running_worker()
                else "Đã dừng"
            )
        )
        status_box = core.ttk.Frame(controls, style="Detail.TFrame")
        status_box.grid(row=0, column=1, sticky="ew")
        core.ttk.Label(
            status_box,
            text="TRẠNG THÁI",
            style="AutoKey.TLabel",
        ).pack(anchor="w")
        core.ttk.Label(
            status_box,
            textvariable=self.auto_multi_dev_operator_status,
            style="AutoValue.TLabel",
            anchor="w",
        ).pack(fill="x", pady=(8, 0))
        self.auto_multi_dev_operator_status_box = status_box

    def _open_refined_auto_multi_dev_config(self) -> None:
        dialog = core.tk.Toplevel(self)
        dialog.title("Cấu hình AUTO MULTI DEV")
        dialog.transient(self)
        try:
            dialog.grab_set()
        except Exception:
            pass

        header = core.ttk.Frame(
            dialog, padding=(16, 13, 16, 8), style="Detail.TFrame"
        )
        header.pack(fill="x")
        core.ttk.Label(
            header,
            text="CẤU HÌNH AUTO MULTI DEV",
            style="Section.TLabel",
        ).pack(anchor="w")
        core.ttk.Label(
            header,
            text=(
                "Nhập trực tiếp giá trị. Vòng lặp và thời gian chờ "
                "được lưu riêng theo tài khoản."
            ),
            style="AutoValue.TLabel",
            anchor="w",
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        body = core.ttk.Frame(
            dialog, padding=(16, 4, 16, 12), style="Detail.TFrame"
        )
        body.pack(fill="both", expand=True)

        speed_frame = core.ttk.LabelFrame(
            body,
            text="TỐC ĐỘ",
            padding=(12, 10),
            style="Auto.TLabelframe",
        )
        speed_frame.pack(fill="x")
        speed_frame.columnconfigure(1, weight=1)
        speed_frame.columnconfigure(3, weight=1)

        current = self._collect_auto_tuning()
        speed_vars: dict[str, object] = {}
        keys = tuple(getattr(core, "MULTI_DEV_TUNING_KEYS", ()))
        for index, key in enumerate(keys):
            label, _minimum, _maximum, _integer = core.AUTO_TUNING_SPECS[key]
            row = index // 2
            group = index % 2
            label_column = group * 2
            entry_column = label_column + 1
            core.ttk.Label(
                speed_frame,
                text=label,
                style="AutoValue.TLabel",
            ).grid(
                row=row,
                column=label_column,
                sticky="w",
                padx=(0 if group == 0 else 24, 8),
                pady=6,
            )
            variable = core.tk.StringVar(
                value=str(current.get(key, core.DEFAULT_AUTO_TUNING[key]))
            )
            speed_vars[key] = variable
            core.ttk.Entry(
                speed_frame,
                textvariable=variable,
                width=14,
            ).grid(row=row, column=entry_column, sticky="ew", pady=6)

        schedule_frame = core.ttk.LabelFrame(
            body,
            text="LỊCH CHẠY",
            padding=(12, 10),
            style="Auto.TLabelframe",
        )
        schedule_frame.pack(fill="x", pady=(12, 0))
        schedule_frame.columnconfigure(1, weight=1)
        schedule_frame.columnconfigure(3, weight=1)

        loop_var = core.tk.StringVar(
            value=str(self.auto_multi_dev_sale_every_loops.get())
        )
        wait_var = core.tk.StringVar(
            value=str(self.auto_multi_dev_function_loop_delay.get())
        )
        core.ttk.Label(
            schedule_frame,
            text="Vòng lặp",
            style="AutoValue.TLabel",
        ).grid(row=0, column=0, sticky="w", padx=(0, 8), pady=6)
        core.ttk.Entry(
            schedule_frame,
            textvariable=loop_var,
            width=14,
        ).grid(row=0, column=1, sticky="ew", pady=6)
        core.ttk.Label(
            schedule_frame,
            text="Thời gian chờ (giây)",
            style="AutoValue.TLabel",
        ).grid(row=0, column=2, sticky="w", padx=(24, 8), pady=6)
        core.ttk.Entry(
            schedule_frame,
            textvariable=wait_var,
            width=14,
        ).grid(row=0, column=3, sticky="ew", pady=6)
        core.ttk.Label(
            schedule_frame,
            text="Vòng lặp = số vòng Function giữa hai lần bán VP.",
            style="AutoValue.TLabel",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(3, 0))

        action_row = core.ttk.Frame(body, style="Detail.TFrame")
        action_row.pack(fill="x", pady=(14, 0))

        def reset_defaults() -> None:
            for key, variable in speed_vars.items():
                variable.set(str(core.DEFAULT_AUTO_TUNING[key]))
            loop_var.set("1")
            wait_var.set("0.0")

        def save_config() -> None:
            validated = {}
            for key, variable in speed_vars.items():
                label, minimum, maximum, integer = core.AUTO_TUNING_SPECS[key]
                try:
                    value = int(variable.get()) if integer else float(variable.get())
                except (TypeError, ValueError):
                    core.messagebox.showerror(
                        core.APP_NAME,
                        f"{label}: giá trị không hợp lệ.",
                        parent=dialog,
                    )
                    return
                if not minimum <= value <= maximum:
                    core.messagebox.showerror(
                        core.APP_NAME,
                        f"{label}: chỉ nhận từ {minimum} đến {maximum}.",
                        parent=dialog,
                    )
                    return
                validated[key] = value

            try:
                loop_value = int(str(loop_var.get()).strip())
            except (TypeError, ValueError):
                loop_value = 0
            if not 1 <= loop_value <= 999:
                core.messagebox.showerror(
                    core.APP_NAME,
                    "Vòng lặp chỉ nhận số nguyên từ 1 đến 999.",
                    parent=dialog,
                )
                return

            try:
                wait_value = float(str(wait_var.get()).strip())
            except (TypeError, ValueError):
                wait_value = -1.0
            if not 0.0 <= wait_value <= 3600.0:
                core.messagebox.showerror(
                    core.APP_NAME,
                    "Thời gian chờ chỉ nhận từ 0 đến 3600 giây.",
                    parent=dialog,
                )
                return

            saved = dict(self.settings.get("auto_tuning", {}))
            saved.update(validated)
            self.settings["auto_tuning"] = saved
            self.auto_multi_dev_sale_every_loops.set(loop_value)
            self.auto_multi_dev_function_loop_delay.set(wait_value)
            saver = getattr(self, "_save_auto_multi_dev_profile_settings", None)
            if callable(saver):
                saver()
            else:
                core.save_settings(self.settings)

            updated = self._broadcast_auto_tuning()
            self.note.set(
                f"Đã lưu Cấu hình AUTO MULTI DEV • vòng lặp={loop_value} • "
                f"chờ={wait_value:g}s"
                + (f" • cập nhật {updated} AUTO đang chạy" if updated else "")
            )
            dialog.destroy()

        core.ttk.Button(
            action_row,
            text="Lưu cấu hình",
            style="AutoStart.TButton",
            command=save_config,
        ).pack(side="left", padx=(0, 8))
        core.ttk.Button(
            action_row,
            text="Mặc định",
            style="Action.TButton",
            command=reset_defaults,
        ).pack(side="left", padx=(0, 8))
        core.ttk.Button(
            action_row,
            text="Đóng",
            style="Action.TButton",
            command=dialog.destroy,
        ).pack(side="left")

        self._place_auto_child_window(
            dialog,
            preferred_width=700,
            preferred_height=520,
            min_width=590,
            min_height=430,
        )

    def _start_clean_with_operator_status(self, *args, **kwargs):
        result = original_start_clean(self, *args, **kwargs)
        for delay in (0, 100, 500):
            try:
                self.after(delay, self._sync_auto_multi_dev_operator_status)
            except Exception:
                break
        return result

    def _stop_clean_with_operator_status(self, *args, **kwargs):
        result = original_stop_clean(self, *args, **kwargs)
        for delay in (0, 150, 500, 1200):
            try:
                self.after(delay, self._sync_auto_multi_dev_operator_status)
            except Exception:
                break
        return result

    def _finish_clean_with_operator_status(self, *args, **kwargs):
        result = original_finish_clean(self, *args, **kwargs)
        for delay in (0, 150, 500):
            try:
                self.after(delay, self._sync_auto_multi_dev_operator_status)
            except Exception:
                break
        return result

    app_class._place_auto_child_window = _place_auto_child_window
    app_class._auto_multi_dev_has_running_worker = _auto_multi_dev_has_running_worker
    app_class._set_auto_multi_dev_operator_status = _set_auto_multi_dev_operator_status
    app_class._sync_auto_multi_dev_operator_status = _sync_auto_multi_dev_operator_status
    app_class._apply_compact_auto_multi_dev_layout = _apply_refined_auto_multi_dev_layout
    app_class._open_auto_multi_dev_config = _open_refined_auto_multi_dev_config
    app_class._start_clean_auto_session = _start_clean_with_operator_status
    app_class._stop_clean_auto_session = _stop_clean_with_operator_status
    app_class._finish_clean_main = _finish_clean_with_operator_status
    app_class._kvtm_auto_multi_dev_ui_refinement_installed = True

    print(
        "[KVTM DEV] AUTO MULTI DEV UI refinement READY • "
        "Function=wide • account-column=removed • status=running/stopped only • "
        "config initial-placement=inside-Multi",
        flush=True,
    )
