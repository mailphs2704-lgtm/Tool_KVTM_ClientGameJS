from __future__ import annotations

from dataclasses import replace
import time
import tkinter as tk
from tkinter import messagebox, ttk

try:
    from .app import AccountRecord, BLUE, BORDER, MUTED, SURFACE, TEXT
except ImportError:
    from app import AccountRecord, BLUE, BORDER, MUTED, SURFACE, TEXT


VP_OPTIONS = (
    ("nuoc_hoa_hong", "Nước hoa hồng"),
    ("tinh_dau_hh", "Tinh dầu hoa hồng"),
    ("vai_vang", "Vải vàng"),
    ("tao_say", "Táo sấy"),
    ("tra_da", "Trà đá"),
)


def install_runtime_integration(app_class) -> None:
    """Wire Model-8 GUI controls to the standalone Dọn quầy controller."""
    if getattr(app_class, "_standalone_runtime_integration_installed", False):
        return

    def _record_for_profile(self, profile_id: str) -> AccountRecord | None:
        return next((row for row in self.accounts if row.account_id == str(profile_id)), None)

    def _reload_rows(self) -> None:
        old = {row.account_id: row for row in self.accounts}
        rows = []
        for fresh in self.profile_store.account_rows():
            previous = old.get(fresh.account_id)
            if previous is not None and self.runtime_controller.enabled(fresh.account_id):
                fresh = replace(fresh, status="running", note=previous.note)
            rows.append(fresh)
        self.accounts = rows
        self.selected = {
            row.account_id: self.selected.get(row.account_id, tk.BooleanVar(value=False))
            for row in rows
        }
        self.page = min(self.page, max(0, (len(rows) - 1) // self.PAGE_SIZE))
        if rows:
            self.default_cycle = int(rows[0].cycle_minutes)
        self.refresh()

    def set_status(self, account_id: str, status: str) -> None:
        pid = str(account_id)
        if status == "running":
            self.runtime_controller.start(pid)
        else:
            self.runtime_controller.stop(pid)

    def enqueue_account(self, account_id: str) -> None:
        """Choose how the next cycle is delayed; later cycles use normal settings."""
        pid = str(account_id)
        row = _record_for_profile(self, pid)
        if row is None:
            return
        job = self.profile_store.ensure_job(pid)
        interval = max(5, int(job.get("interval_minutes", 65) or 65))
        last_success = self.profile_store.last_success_at(pid)
        remaining_from_success = max(
            0.0, (last_success + interval * 60) - time.time()
        ) if last_success > 0 else 0.0

        w = self._modal("Thêm lịch Dọn quầy", 570, 350)
        body = tk.Frame(w, bg=SURFACE)
        body.pack(fill="both", expand=True, padx=24, pady=20)
        tk.Label(
            body, text=row.account_name, bg=SURFACE, fg=TEXT,
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")
        tk.Label(
            body,
            text="Chọn cách chờ cho phiên sắp tới. Các phiên sau luôn quay lại theo Chu kỳ đã cài.",
            bg=SURFACE, fg=MUTED, justify="left", wraplength=515,
        ).pack(anchor="w", pady=(3, 16))

        mode = tk.StringVar(value="custom")
        custom_minutes = tk.StringVar(value=str(interval))
        custom = tk.Frame(body, bg=SURFACE)
        custom.pack(fill="x", pady=5)
        tk.Radiobutton(
            custom, text="Chờ riêng cho phiên đầu", variable=mode,
            value="custom", bg=SURFACE, fg=TEXT, activebackground=SURFACE,
            selectcolor=SURFACE, font=("Segoe UI", 10, "bold"),
        ).pack(side="left")
        ttk.Entry(
            custom, textvariable=custom_minutes, style="Modern.TEntry", width=9,
        ).pack(side="left", padx=(12, 6))
        tk.Label(custom, text="phút", bg=SURFACE, fg=MUTED).pack(side="left")

        success_text = (
            f"Còn {max(0, int(round(remaining_from_success / 60)))} phút "
            f"(lần thành công cuối: {row.last_clean})"
            if last_success > 0
            else "Chưa có lần thành công • sẽ chạy ngay"
        )
        previous = tk.Frame(body, bg=SURFACE)
        previous.pack(fill="x", pady=5)
        tk.Radiobutton(
            previous, text="Theo thời gian lần cuối thành công", variable=mode,
            value="last_success", bg=SURFACE, fg=TEXT,
            activebackground=SURFACE, selectcolor=SURFACE,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")
        tk.Label(
            previous, text=success_text, bg=SURFACE, fg=MUTED,
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=(26, 0), pady=(2, 0))

        def submit() -> None:
            if mode.get() == "last_success":
                delay = remaining_from_success
            else:
                try:
                    minutes = int(custom_minutes.get().strip())
                except ValueError:
                    messagebox.showerror(
                        "KVTM - Dọn Quầy", "Thời gian chờ phải là số nguyên.", parent=w
                    )
                    return
                if not 0 <= minutes <= 1440:
                    messagebox.showerror(
                        "KVTM - Dọn Quầy",
                        "Thời gian chờ phiên đầu phải từ 0 đến 1440 phút.",
                        parent=w,
                    )
                    return
                delay = minutes * 60.0
            self.runtime_controller.enqueue(pid, first_delay_seconds=delay)
            w.destroy()

        controls = tk.Frame(body, bg=SURFACE)
        controls.pack(fill="x", pady=(24, 0))
        self._button(controls, "Thêm vào lịch", submit, True, 12).pack(side="right")
        self._button(controls, "Hủy", w.destroy, False, 9).pack(side="right", padx=8)

    def start_all(self) -> None:
        for row in list(self.accounts):
            self.runtime_controller.start(row.account_id)

    def stop_all(self) -> None:
        self.runtime_controller.stop_all()

    def add_account(self) -> None:
        available = self.profile_store.available_profiles()
        if not available:
            messagebox.showinfo(
                "KVTM - Dọn Quầy",
                "Không còn tài khoản nào để thêm.\nHãy bấm Đồng bộ profile nếu AUTO MULTI DEV vừa có tài khoản mới.",
                parent=self.root,
            )
            return
        w = self._modal("Thêm tài khoản từ profile", 600, 450)
        body = tk.Frame(w, bg=SURFACE)
        body.pack(fill="both", expand=True, padx=22, pady=18)
        tk.Label(body, text="Chọn tài khoản có trong profile", bg=SURFACE, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        tk.Label(body, text="Chỉ profile đã đồng bộ từ AUTO MULTI DEV mới xuất hiện ở đây.", bg=SURFACE, fg=MUTED).pack(anchor="w", pady=(3, 2))
        tk.Label(
            body,
            text=f"Nguồn: {self.profile_store.multi_profile_file}",
            bg=SURFACE,
            fg=MUTED,
            anchor="w",
            justify="left",
            wraplength=550,
        ).pack(anchor="w", pady=(0, 12))
        box = tk.Listbox(
            body, selectmode="extended", exportselection=False,
            relief="flat", bd=0, highlightthickness=1, highlightbackground=BORDER,
            font=("Segoe UI", 10), activestyle="none",
        )
        box.pack(fill="both", expand=True)
        for profile in available:
            name = str(profile.get("name") or profile.get("id") or "Tài khoản")
            box.insert("end", name)

        def save() -> None:
            indices = list(box.curselection())
            if not indices:
                return
            ids = [str(available[index].get("id") or "") for index in indices]
            self.profile_store.add_selected(ids)
            _reload_rows(self)
            w.destroy()

        controls = tk.Frame(body, bg=SURFACE)
        controls.pack(fill="x", pady=(14, 0))
        self._button(controls, "Thêm đã chọn", save, True, 12).pack(side="right")
        self._button(controls, "Hủy", w.destroy, False, 9).pack(side="right", padx=8)

    def sync_profiles(self) -> None:
        try:
            count = self.profile_store.sync_from_multi()
            _reload_rows(self)
        except Exception as exc:
            messagebox.showerror("KVTM - Dọn Quầy", str(exc), parent=self.root)
            return
        messagebox.showinfo(
            "KVTM - Dọn Quầy",
            (
                f"Đã đồng bộ {count} profile từ AUTO MULTI DEV.\n"
                f"Nguồn: {self.profile_store.multi_profile_file}\n\n"
                "Thiết lập Dọn quầy riêng của tool không bị ghi đè."
            ),
            parent=self.root,
        )

    def quick_config(self) -> None:
        w = self._modal("Cấu hình nhanh", 470, 270)
        body = tk.Frame(w, bg=SURFACE)
        body.pack(fill="both", expand=True, padx=22, pady=18)
        tk.Label(body, text="Cấu hình nhanh", bg=SURFACE, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        current = self.default_cycle if self.accounts else 65
        var = tk.StringVar(value=str(current))
        row = tk.Frame(body, bg=SURFACE)
        row.pack(fill="x", pady=18)
        tk.Label(row, text="Chu kỳ Dọn quầy (phút)", bg=SURFACE, fg=MUTED, width=24, anchor="w").pack(side="left")
        ttk.Entry(row, textvariable=var, style="Modern.TEntry").pack(side="left", fill="x", expand=True)

        def save() -> None:
            try:
                value = self.profile_store.set_interval_all(int(var.get()))
            except (ValueError, TypeError):
                return
            self.default_cycle = value
            _reload_rows(self)
            w.destroy()

        self._button(body, "Lưu", save, True, 9).pack(side="right", pady=14)
        self._button(body, "Hủy", w.destroy, False, 9).pack(side="right", padx=8, pady=14)

    def show_log(self, account_id: str) -> None:
        row = _record_for_profile(self, account_id)
        if row is None:
            return
        w = tk.Toplevel(self.root)
        w.title(f"Log Dọn quầy - {row.account_name}")
        w.configure(bg=SURFACE)
        w.geometry("900x560")
        w.minsize(680, 400)
        w.transient(self.root)

        top = tk.Frame(w, bg=SURFACE)
        top.pack(fill="x", padx=18, pady=(16, 8))
        tk.Label(
            top,
            text=f"Log runtime · {row.account_name}",
            bg=SURFACE,
            fg=TEXT,
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w")
        log_path = self.runtime_controller.log_path(account_id)
        tk.Label(
            top,
            text=f"File: {log_path}",
            bg=SURFACE,
            fg=MUTED,
            font=("Segoe UI", 8),
            anchor="w",
            justify="left",
            wraplength=850,
        ).pack(anchor="w", pady=(3, 0))

        host = tk.Frame(w, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        host.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        host.grid_rowconfigure(0, weight=1)
        host.grid_columnconfigure(0, weight=1)
        text = tk.Text(
            host,
            bg="#0F1724",
            fg="#DCE7F5",
            insertbackground="#FFFFFF",
            relief="flat",
            bd=0,
            wrap="none",
            font=("Consolas", 9),
            padx=10,
            pady=8,
            state="disabled",
        )
        ybar = ttk.Scrollbar(host, orient="vertical", command=text.yview)
        xbar = ttk.Scrollbar(host, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        text.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")

        footer = tk.Frame(w, bg=SURFACE)
        footer.pack(fill="x", padx=18, pady=(0, 14))
        status = tk.StringVar(value="Tự động làm mới log mỗi 0.7 giây")
        tk.Label(footer, textvariable=status, bg=SURFACE, fg=MUTED, font=("Segoe UI", 8)).pack(side="left")

        refresh_job = {"id": None}
        last_text = {"value": None}

        def refresh_log(force: bool = False) -> None:
            if not w.winfo_exists():
                return
            try:
                payload = self.runtime_controller.read_log(account_id, max_lines=1200)
            except Exception as exc:
                payload = f"Không đọc được log: {exc}\n"
            if force or payload != last_text["value"]:
                try:
                    at_end = text.yview()[1] >= 0.98
                except tk.TclError:
                    at_end = True
                text.configure(state="normal")
                text.delete("1.0", "end")
                text.insert("1.0", payload)
                text.configure(state="disabled")
                if at_end or last_text["value"] is None:
                    text.see("end")
                last_text["value"] = payload
            refresh_job["id"] = w.after(700, refresh_log)

        def close_log() -> None:
            job = refresh_job.get("id")
            if job is not None:
                try:
                    w.after_cancel(job)
                except tk.TclError:
                    pass
            w.destroy()

        self._button(footer, "Đóng", close_log, True, 9).pack(side="right")
        self._button(footer, "Làm mới", lambda: refresh_log(True), False, 9).pack(side="right", padx=8)
        w.protocol("WM_DELETE_WINDOW", close_log)
        refresh_log(True)

    def details(self, account_id: str) -> None:
        row = _record_for_profile(self, account_id)
        if row is None:
            return
        job = self.profile_store.ensure_job(account_id)
        w = self._modal("Cấu hình Dọn quầy", 590, 510)
        body = tk.Frame(w, bg=SURFACE)
        body.pack(fill="both", expand=True, padx=24, pady=20)

        tk.Label(
            body,
            text=row.account_name,
            bg=SURFACE,
            fg=TEXT,
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")
        tk.Label(
            body,
            text="Thiết lập riêng cho tài khoản này",
            bg=SURFACE,
            fg=MUTED,
        ).pack(anchor="w", pady=(2, 16))

        form = tk.Frame(body, bg=SURFACE)
        form.pack(fill="x")
        form.grid_columnconfigure(1, weight=1)

        tk.Label(
            form,
            text="Chọn VP dọn",
            bg=SURFACE,
            fg=TEXT,
            font=("Segoe UI", 10, "bold"),
            anchor="nw",
        ).grid(row=0, column=0, sticky="nw", padx=(0, 22), pady=(2, 14))

        vp_frame = tk.Frame(form, bg=SURFACE)
        vp_frame.grid(row=0, column=1, sticky="ew", pady=(0, 14))
        current_items = set(job.get("allowed_item_ids", ()))
        vp_vars: dict[str, tk.BooleanVar] = {}
        for index, (item_id, label) in enumerate(VP_OPTIONS):
            variable = tk.BooleanVar(value=item_id in current_items)
            vp_vars[item_id] = variable
            tk.Checkbutton(
                vp_frame,
                text=label,
                variable=variable,
                bg=SURFACE,
                fg=TEXT,
                activebackground=SURFACE,
                activeforeground=TEXT,
                selectcolor=SURFACE,
                highlightthickness=0,
                bd=0,
                font=("Segoe UI", 10),
            ).grid(
                row=index // 2,
                column=index % 2,
                sticky="w",
                padx=(0, 24),
                pady=3,
            )

        house_var = tk.StringVar(value=str(job.get("target_friend_ordinal", 1)))
        quantity_var = tk.StringVar(value=str(job.get("buy_quantity", 10)))
        interval_var = tk.StringVar(value=str(job.get("interval_minutes", 65)))

        def add_number_row(grid_row: int, label: str, variable: tk.StringVar, hint: str) -> None:
            tk.Label(
                form,
                text=label,
                bg=SURFACE,
                fg=TEXT,
                font=("Segoe UI", 10, "bold"),
                anchor="w",
            ).grid(row=grid_row, column=0, sticky="w", padx=(0, 22), pady=9)
            holder = tk.Frame(form, bg=SURFACE)
            holder.grid(row=grid_row, column=1, sticky="ew", pady=9)
            ttk.Entry(
                holder,
                textvariable=variable,
                style="Modern.TEntry",
                width=18,
            ).pack(side="left")
            tk.Label(
                holder,
                text=hint,
                bg=SURFACE,
                fg=MUTED,
                font=("Segoe UI", 9),
            ).pack(side="left", padx=(10, 0))

        add_number_row(1, "Số lượng nhà", house_var, "1 - 7 nhà")
        add_number_row(2, "Số lượng VP dọn", quantity_var, "10 - 1000 VP, bội số 10")
        add_number_row(3, "Thời gian chu kỳ", interval_var, "5 - 1440 phút")

        tk.Label(
            body,
            text=(
                "Các ô số cho phép nhập trực tiếp bằng bàn phím, không dùng nút tăng/giảm. "
                "Nếu tài khoản đang chạy, cấu hình mới áp dụng từ lượt kế tiếp."
            ),
            bg=SURFACE,
            fg=MUTED,
            justify="left",
            wraplength=525,
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(14, 0))

        def save_settings() -> None:
            selected_items = [item_id for item_id, _label in VP_OPTIONS if vp_vars[item_id].get()]
            if not selected_items:
                messagebox.showerror(
                    "KVTM - Dọn Quầy",
                    "Hãy chọn ít nhất 1 VP cần dọn.",
                    parent=w,
                )
                return
            try:
                house_count = int(house_var.get().strip())
                quantity = int(quantity_var.get().strip())
                interval = int(interval_var.get().strip())
            except ValueError:
                messagebox.showerror(
                    "KVTM - Dọn Quầy",
                    "Số lượng nhà, số lượng VP và thời gian chu kỳ phải là số nguyên.",
                    parent=w,
                )
                return
            if not 1 <= house_count <= 7:
                messagebox.showerror("KVTM - Dọn Quầy", "Số lượng nhà phải từ 1 đến 7.", parent=w)
                return
            if not 10 <= quantity <= 1000 or quantity % 10:
                messagebox.showerror(
                    "KVTM - Dọn Quầy",
                    "Số lượng VP dọn phải từ 10 đến 1000 và là bội số của 10.",
                    parent=w,
                )
                return
            if not 5 <= interval <= 1440:
                messagebox.showerror(
                    "KVTM - Dọn Quầy",
                    "Thời gian chu kỳ phải từ 5 đến 1440 phút.",
                    parent=w,
                )
                return

            self.profile_store.update_job(
                account_id,
                {
                    "allowed_item_ids": selected_items,
                    "target_friend_ordinal": house_count,
                    "buy_quantity": quantity,
                    "interval_minutes": interval,
                },
            )
            _reload_rows(self)
            w.destroy()

        def remove() -> None:
            self.runtime_controller.stop(account_id)
            self.profile_store.remove_selected(account_id)
            _reload_rows(self)
            w.destroy()

        controls = tk.Frame(body, bg=SURFACE)
        controls.pack(fill="x", pady=(22, 0))
        self._button(controls, "Xóa khỏi tool", remove, False, 12).pack(side="left")
        self._button(controls, "Lưu cấu hình", save_settings, True, 12).pack(side="right")
        self._button(controls, "Hủy", w.destroy, False, 9).pack(side="right", padx=8)

    app_class._record_for_profile = _record_for_profile
    app_class._reload_rows = _reload_rows
    app_class.set_status = set_status
    app_class.enqueue_account = enqueue_account
    app_class.start_all = start_all
    app_class.stop_all = stop_all
    app_class.add_account = add_account
    app_class.sync_profiles = sync_profiles
    app_class.quick_config = quick_config
    app_class.show_log = show_log
    app_class.details = details
    app_class._standalone_runtime_integration_installed = True


def bind_runtime(app, profile_store, runtime_controller) -> None:
    app.profile_store = profile_store
    app.runtime_controller = runtime_controller

    def on_runtime_event(profile_id: str, event: str, data: dict) -> None:
        # Progress can fire dozens of times per second while matching images.
        # It belongs in the Log window. Rebuilding every Tk row here caused the
        # entire account table to flicker continuously during a live run.
        if event == "progress":
            return

        rows = []
        changed = False
        for row in app.accounts:
            if row.account_id != profile_id:
                rows.append(row)
                continue
            note = row.note
            if event in {"running", "cycle_start", "first_cycle_wait"}:
                status = "running"
            elif event == "stopped":
                status = "stopped"
            elif event in {"cycle_error", "error"}:
                status = "running" if runtime_controller.enabled(profile_id) else "stopped"
                note = "Có lỗi - xem Log"
            elif event == "cycle_done":
                status = "running" if runtime_controller.enabled(profile_id) else "stopped"
                note = "—"
            else:
                status = row.status
            last_clean = str(data.get("last_clean") or row.last_clean)
            updated = replace(row, status=status, note=note, last_clean=last_clean)
            rows.append(updated)
            changed = changed or updated != row
        if changed:
            app.accounts = rows
            app.refresh()

    runtime_controller.callback = on_runtime_event
    if not app.accounts:
        app.default_cycle = 65
    app.root.protocol("WM_DELETE_WINDOW", lambda: (runtime_controller.close(), app.root.destroy()))
    app.refresh()
