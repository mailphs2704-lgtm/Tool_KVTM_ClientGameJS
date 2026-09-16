from __future__ import annotations

from dataclasses import replace
import tkinter as tk
from tkinter import messagebox, ttk

try:
    from .app import AccountRecord, MUTED, SURFACE, TEXT
except ImportError:
    from app import AccountRecord, MUTED, SURFACE, TEXT


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
            relief="flat", bd=0, highlightthickness=1, highlightbackground="#DCE4EF",
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

    def details(self, account_id: str) -> None:
        row = _record_for_profile(self, account_id)
        if row is None:
            return
        job = self.profile_store.ensure_job(account_id)
        w = self._modal("Chi tiết tài khoản", 500, 330)
        body = tk.Frame(w, bg=SURFACE)
        body.pack(fill="both", expand=True, padx=22, pady=18)
        tk.Label(body, text=row.account_name, bg=SURFACE, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        text = (
            f"Trạng thái: {row.status_text}\n"
            f"Chu kỳ: {job['interval_minutes']} phút\n"
            f"Nhà bạn: {job['target_friend_ordinal']} · Kho VP: {job['target_stall_id']}\n"
            f"Số lượng: {job['buy_quantity']} VP · Tốc độ kéo quầy: {job['clear_stall_drag_speed']:.2f}s\n"
            f"Lần dọn cuối: {row.last_clean}"
        )
        tk.Label(body, text=text, bg=SURFACE, fg=TEXT, justify="left").pack(anchor="w", pady=12)

        def remove() -> None:
            self.runtime_controller.stop(account_id)
            self.profile_store.remove_selected(account_id)
            _reload_rows(self)
            w.destroy()

        self._button(body, "Xóa khỏi tool", remove, False, 12).pack(side="left", pady=12)
        self._button(body, "Đóng", w.destroy, True, 9).pack(side="right", pady=12)

    app_class._record_for_profile = _record_for_profile
    app_class._reload_rows = _reload_rows
    app_class.set_status = set_status
    app_class.start_all = start_all
    app_class.stop_all = stop_all
    app_class.add_account = add_account
    app_class.sync_profiles = sync_profiles
    app_class.quick_config = quick_config
    app_class.details = details
    app_class._standalone_runtime_integration_installed = True


def bind_runtime(app, profile_store, runtime_controller) -> None:
    app.profile_store = profile_store
    app.runtime_controller = runtime_controller

    def on_runtime_event(profile_id: str, event: str, data: dict) -> None:
        rows = []
        for row in app.accounts:
            if row.account_id != profile_id:
                rows.append(row)
                continue
            note = str(data.get("message") or row.note or "—")
            if event in {"running", "cycle_start", "progress"}:
                status = "running"
            elif event == "stopped":
                status = "stopped"
            elif event == "cycle_error":
                status = "running" if runtime_controller.enabled(profile_id) else "stopped"
                note = "Lỗi: " + note
            elif event == "cycle_done":
                status = "running" if runtime_controller.enabled(profile_id) else "stopped"
            else:
                status = row.status
            last_clean = str(data.get("last_clean") or row.last_clean)
            rows.append(replace(row, status=status, note=note, last_clean=last_clean))
        app.accounts = rows
        app.refresh()

    runtime_controller.callback = on_runtime_event
    if not app.accounts:
        app.default_cycle = 65
    app.root.protocol("WM_DELETE_WINDOW", lambda: (runtime_controller.close(), app.root.destroy()))
    app.refresh()
