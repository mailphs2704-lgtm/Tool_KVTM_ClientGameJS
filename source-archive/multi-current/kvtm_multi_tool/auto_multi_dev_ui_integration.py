from __future__ import annotations

import json
from pathlib import Path

from main_log_viewer import open_auto_log_window


__all__ = ["install_auto_multi_dev_ui_integration"]

FILE_FUNCTIONS = (
    "Chuẩn hóa mặt AUTO MULTI DEV theo bố cục Chức năng chính",
    "Ẩn nút test Function 3 khỏi UI vận hành",
    "Đưa Mở rương và Thăm bạn thành hai toggle nhanh cạnh nhau",
    "Đưa Vòng lặp và Thời gian chờ vào cửa sổ Cấu hình cùng tốc độ",
    "Dùng Entry nhập trực tiếp, không dùng Spinbox tăng/giảm trong cấu hình mới",
    "Gộp Log hành động, Log chi tiết và Log lỗi vào một nút/cửa sổ",
)


def install_auto_multi_dev_ui_integration(app_class, core) -> None:
    if getattr(app_class, "_kvtm_auto_multi_dev_ui_installed", False):
        return

    original_build_auto_panel = app_class._build_auto_panel
    original_refresh_profile_settings = getattr(
        app_class, "_refresh_auto_multi_dev_profile_settings", None
    )

    def _profile_name_for_id(self, profile_id: str) -> str:
        profile_id = str(profile_id or "")
        profile = next(
            (
                item
                for item in self.profiles
                if str(item.get("id") or "") == profile_id
            ),
            None,
        )
        return str((profile or {}).get("name") or profile_id)

    def _selected_account_summary(self) -> str:
        selected = list(map(str, self.selected_ids()))
        if not selected:
            return "Chưa chọn tài khoản"
        names = [self._profile_name_for_id(profile_id) for profile_id in selected]
        if len(names) <= 2:
            return ", ".join(names)
        return f"{names[0]}, {names[1]} +{len(names) - 2} acc"

    def _latest_main_log_paths(self, profile_id: str) -> tuple[Path, Path]:
        profile_id = str(profile_id)
        mapped = getattr(self, "_clean_main_log_paths", {}).get(profile_id)
        if isinstance(mapped, tuple) and len(mapped) == 2:
            return Path(mapped[0]), Path(mapped[1])

        root = Path(core.APP_DIR) / "auto-multi-dev" / profile_id
        candidates: list[Path] = []
        try:
            candidates = sorted(
                (path for path in root.iterdir() if path.is_dir()),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
        except OSError:
            candidates = []
        for run_dir in candidates:
            action_path = run_dir / "action.log"
            detail_path = run_dir / "detail.log"
            if action_path.exists() or detail_path.exists():
                return action_path, detail_path

        empty = root / "_ui-empty"
        return empty / "action.log", empty / "detail.log"

    def _open_auto_multi_dev_logs(self) -> None:
        profile_id = None
        profile = None
        resolver = getattr(self, "_error_log_profile", None)
        if callable(resolver):
            profile_id, profile = resolver()
        if not profile_id or profile is None:
            core.messagebox.showinfo(
                core.APP_NAME,
                "Hãy chọn một tài khoản để xem Log AUTO.",
            )
            return

        action_path, detail_path = self._latest_main_log_paths(profile_id)
        error_path = self._persistent_error_log_path(profile_id)
        name = str(profile.get("name") or profile_id)
        open_auto_log_window(
            self,
            action_path=action_path,
            detail_path=detail_path,
            error_path=error_path,
            title=f"Log AUTO - {name}",
            account_name=name,
            export_error_callback=self._export_auto_error_log_txt,
        )

    def _broadcast_auto_tuning(self) -> int:
        full_tuning = self._collect_auto_tuning()
        payload = json.dumps(
            {"command": "update_tuning", "tuning": full_tuning},
            ensure_ascii=True,
            separators=(",", ":"),
        ) + "\n"
        workers = []
        for attribute in (
            "_auto_workers",
            "_clean_auto_workers",
            "_clean_main_workers",
        ):
            group = getattr(self, attribute, None)
            if isinstance(group, dict):
                workers.extend(group.values())
        updated = 0
        seen = set()
        for worker in workers:
            marker = id(worker)
            if marker in seen:
                continue
            seen.add(marker)
            try:
                if worker.poll() is None and worker.stdin:
                    worker.stdin.write(payload)
                    worker.stdin.flush()
                    updated += 1
            except (OSError, ValueError):
                pass
        return updated

    def _open_auto_multi_dev_config(self) -> None:
        dialog = core.tk.Toplevel(self)
        dialog.title("Cấu hình AUTO MULTI DEV")
        dialog.transient(self)
        dialog.geometry("760x560")
        dialog.minsize(660, 480)
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
            text="Nhập trực tiếp giá trị. Vòng lặp và thời gian chờ được lưu riêng theo tài khoản.",
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

    def _hide_grid_parent(widget) -> None:
        if widget is None:
            return
        try:
            widget.master.grid_remove()
        except Exception:
            pass

    def _remove_old_log_rows(self) -> None:
        old_buttons = []
        for attribute in (
            "auto_multi_dev_function_3_step_1_button",
            "auto_multi_dev_action_log_button",
            "auto_multi_dev_detail_log_button",
            "auto_multi_dev_error_log_button",
            "auto_multi_dev_export_error_button",
        ):
            button = getattr(self, attribute, None)
            if button is not None:
                old_buttons.append(button)
        rows = []
        for button in old_buttons:
            try:
                parent = button.master
                if parent not in rows:
                    rows.append(parent)
                button.destroy()
            except Exception:
                pass
        for row in rows:
            try:
                if not row.winfo_children():
                    row.pack_forget()
            except Exception:
                pass

    def _refresh_compact_auto_multi_dev_controls(self) -> None:
        target_var = getattr(self, "auto_multi_dev_target_summary", None)
        if target_var is not None:
            target_var.set(self._selected_account_summary())
        selected = list(map(str, self.selected_ids()))
        state = "normal" if selected else "disabled"
        cursor = "hand2" if selected else "arrow"
        for attribute in (
            "auto_multi_dev_quick_chest_button",
            "auto_multi_dev_quick_friend_button",
            "auto_multi_dev_quick_feed_button",
            "auto_multi_dev_logs_button",
        ):
            button = getattr(self, attribute, None)
            if button is not None:
                try:
                    button.configure(state=state, cursor=cursor)
                except Exception:
                    pass

    def _apply_compact_auto_multi_dev_layout(self) -> None:
        start_button = getattr(self, "auto_multi_dev_start_button", None)
        speed_button = getattr(self, "auto_multi_dev_speed_button", None)
        stop_button = getattr(self, "auto_multi_dev_stop_button", None)
        function_button = getattr(self, "auto_multi_dev_function_button", None)
        if (
            start_button is None
            or speed_button is None
            or stop_button is None
            or function_button is None
        ):
            return

        self._remove_old_log_rows()

        clean_actions = start_button.master
        multi_dev_tab = clean_actions.master
        function_box = function_button.master
        controls = function_box.master

        _hide_grid_parent(getattr(self, "auto_multi_dev_sale_every_spin", None))
        _hide_grid_parent(
            getattr(self, "auto_multi_dev_function_loop_delay_spin", None)
        )
        _hide_grid_parent(
            getattr(self, "auto_multi_dev_friend_refresh_button", None)
        )
        _hide_grid_parent(
            getattr(self, "auto_multi_dev_pirate_chest_button", None)
        )

        for child in tuple(controls.winfo_children()):
            if child is function_box:
                continue
            try:
                child.grid_remove()
            except Exception:
                pass

        for column in range(5):
            controls.columnconfigure(column, weight=0)
        controls.columnconfigure(0, weight=3)
        controls.columnconfigure(1, weight=2)
        controls.columnconfigure(2, weight=2)
        function_box.grid_configure(
            row=0, column=0, columnspan=1, sticky="ew", padx=(0, 14)
        )

        self.auto_multi_dev_target_summary = core.tk.StringVar(
            value=self._selected_account_summary()
        )
        target_box = core.ttk.Frame(controls, style="Detail.TFrame")
        target_box.grid(row=0, column=1, sticky="ew", padx=(0, 14))
        core.ttk.Label(
            target_box,
            text="TÀI KHOẢN ÁP DỤNG",
            style="AutoKey.TLabel",
        ).pack(anchor="w")
        core.ttk.Label(
            target_box,
            textvariable=self.auto_multi_dev_target_summary,
            style="AutoValue.TLabel",
            anchor="w",
        ).pack(fill="x", pady=(8, 0))

        status_box = core.ttk.Frame(controls, style="Detail.TFrame")
        status_box.grid(row=0, column=2, sticky="ew")
        core.ttk.Label(
            status_box,
            text="TRẠNG THÁI",
            style="AutoKey.TLabel",
        ).pack(anchor="w")
        core.ttk.Label(
            status_box,
            textvariable=self.auto_multi_dev_status,
            style="AutoValue.TLabel",
            anchor="w",
        ).pack(fill="x", pady=(8, 0))

        old_quick = getattr(self, "auto_multi_dev_quick_options_row", None)
        if old_quick is not None:
            try:
                old_quick.destroy()
            except Exception:
                pass
        quick = core.ttk.Frame(multi_dev_tab, style="Detail.TFrame")
        quick.pack(fill="x", padx=8, pady=(4, 2), before=clean_actions)
        self.auto_multi_dev_quick_options_row = quick

        chest_var = getattr(self, "auto_multi_dev_pirate_chest_enabled", None)
        if chest_var is not None:
            chest_button = self._make_toggle_button(
                quick,
                "Mở rương",
                chest_var,
                getattr(self, "_save_optional_features", None),
            )
            chest_button.configure(anchor="center", width=14, padx=10, pady=5)
            chest_button.pack(side="left", padx=(0, 8))
            self.auto_multi_dev_quick_chest_button = chest_button

        friend_var = getattr(self, "auto_multi_dev_friend_refresh_enabled", None)
        if friend_var is not None:
            friend_button = self._make_toggle_button(
                quick,
                "Thăm bạn",
                friend_var,
                getattr(self, "_save_auto_multi_dev_friend_refresh", None),
            )
            friend_button.configure(anchor="center", width=14, padx=10, pady=5)
            friend_button.pack(side="left", padx=(0, 8))
            self.auto_multi_dev_quick_friend_button = friend_button

        feed_var = getattr(self, "auto_multi_dev_feed_mill_enabled", None)
        if feed_var is not None:
            feed_button = self._make_toggle_button(
                quick,
                "Sx cám",
                feed_var,
                getattr(self, "_save_optional_features", None),
            )
            feed_button.configure(anchor="center", width=14, padx=10, pady=5)
            feed_button.pack(side="left")
            self.auto_multi_dev_quick_feed_button = feed_button

        warehouse_button = core.ttk.Button(
            quick,
            text="Nâng kho",
            width=14,
            style="Action.TButton",
            command=self._open_warehouse_upgrade_panel,
        )
        warehouse_button.pack(side="left", padx=(8, 0))
        self.auto_multi_dev_quick_warehouse_button = warehouse_button

        for child in tuple(clean_actions.winfo_children()):
            try:
                child.pack_forget()
            except Exception:
                pass
        start_button.configure(text="▶ Bắt đầu")
        start_button.pack(side="left", padx=(0, 8))
        stop_button.configure(text="■ Dừng")
        stop_button.pack(side="left", padx=(0, 8))
        speed_button.configure(
            text="Cấu hình",
            command=self._open_auto_multi_dev_config,
        )
        speed_button.pack(side="left", padx=(0, 8))
        self.auto_multi_dev_logs_button = core.ttk.Button(
            clean_actions,
            text="≡ Log",
            width=16,
            style="Action.TButton",
            command=self._open_auto_multi_dev_logs,
        )
        self.auto_multi_dev_logs_button.pack(side="left")

        self._refresh_compact_auto_multi_dev_controls()
        refresh_tabs = getattr(self, "_refresh_auto_tab_scroll", None)
        if callable(refresh_tabs):
            self.after_idle(refresh_tabs)

    def build_auto_panel(self) -> None:
        original_build_auto_panel(self)
        self._apply_compact_auto_multi_dev_layout()

    def refresh_profile_settings(self) -> None:
        if callable(original_refresh_profile_settings):
            original_refresh_profile_settings(self)
        self._refresh_compact_auto_multi_dev_controls()

    app_class._build_auto_panel = build_auto_panel
    if callable(original_refresh_profile_settings):
        app_class._refresh_auto_multi_dev_profile_settings = refresh_profile_settings
    app_class._profile_name_for_id = _profile_name_for_id
    app_class._selected_account_summary = _selected_account_summary
    app_class._latest_main_log_paths = _latest_main_log_paths
    app_class._open_auto_multi_dev_logs = _open_auto_multi_dev_logs
    app_class._broadcast_auto_tuning = _broadcast_auto_tuning
    app_class._open_auto_multi_dev_config = _open_auto_multi_dev_config
    app_class._remove_old_log_rows = _remove_old_log_rows
    app_class._refresh_compact_auto_multi_dev_controls = (
        _refresh_compact_auto_multi_dev_controls
    )
    app_class._apply_compact_auto_multi_dev_layout = (
        _apply_compact_auto_multi_dev_layout
    )
    app_class._kvtm_auto_multi_dev_ui_installed = True

    print(
        "[KVTM DEV] AUTO MULTI DEV UI READY • main-style compact layout • "
        "test button hidden • quick=Mở rương+Thăm bạn+Sx cám • Config=Entry • Log=3 tabs",
        flush=True,
    )
