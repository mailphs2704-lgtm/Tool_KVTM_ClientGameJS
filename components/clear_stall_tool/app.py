from __future__ import annotations

from dataclasses import dataclass, replace
import tkinter as tk
from tkinter import ttk
from typing import Iterable

BG = "#F4F7FB"; SURFACE = "#FFFFFF"; ALT = "#F8FAFD"; BORDER = "#DCE4EF"
TEXT = "#17253A"; MUTED = "#6D7A90"; BLUE = "#1677F2"; GREEN = "#22A35A"; RED = "#E84A5F"


@dataclass(frozen=True)
class AccountRecord:
    account_id: str
    account_name: str
    profile_name: str
    status: str = "ready"
    last_clean: str = "—"
    cycle_minutes: int = 30
    note: str = "—"

    @property
    def status_text(self) -> str:
        return {"running": "Đang chạy", "ready": "Sẵn sàng", "stopped": "Đã dừng"}.get(self.status, self.status)

    @property
    def status_color(self) -> str:
        return {"running": GREEN, "ready": "#2D7FF9", "stopped": RED}.get(self.status, MUTED)


class ClearStallToolApp:
    PAGE_SIZE = 8
    COLS = ((38, 0), (38, 0), (170, 2), (125, 1), (135, 1), (138, 1), (95, 0), (92, 0), (118, 0))

    def __init__(self, root: tk.Tk, accounts: Iterable[AccountRecord] = ()) -> None:
        self.root = root; self.accounts = list(accounts); self.page = 0; self.default_cycle = 30
        self.selected = {a.account_id: tk.BooleanVar(value=False) for a in self.accounts}
        self.header_select = tk.BooleanVar(value=False); self.status_var = tk.StringVar(value="Sẵn sàng")
        self._row_signature = None; self._row_value_labels = {}
        self._setup(); self._build(); self.refresh()

    def _setup(self) -> None:
        self.root.title("KVTM - Dọn Quầy"); self.root.geometry("1240x720"); self.root.minsize(1080, 650); self.root.configure(bg=BG)
        try: self.root.option_add("*Font", "{Segoe UI} 9")
        except tk.TclError: pass
        style = ttk.Style(self.root)
        try: style.theme_use("clam")
        except tk.TclError: pass
        style.configure("Modern.TEntry", fieldbackground=SURFACE, foreground=TEXT, bordercolor=BORDER, padding=6)

    @staticmethod
    def _button(master, text, command, primary=False, width=14):
        bg = BLUE if primary else SURFACE; fg = "#FFFFFF" if primary else TEXT
        return tk.Button(master, text=text, command=command, bg=bg, fg=fg, activebackground="#0D68D7" if primary else ALT,
                         activeforeground=fg, relief="flat", bd=0, padx=10, pady=7, width=width, cursor="hand2",
                         font=("Segoe UI", 9, "bold"), highlightthickness=1, highlightbackground=BLUE if primary else BORDER)

    @staticmethod
    def _columns(frame):
        for i, (size, weight) in enumerate(ClearStallToolApp.COLS): frame.grid_columnconfigure(i, minsize=size, weight=weight)

    def _build(self) -> None:
        self.outer = tk.Frame(self.root, bg=BG); self.outer.pack(fill="both", expand=True, padx=14, pady=12)
        self.outer.grid_columnconfigure(0, weight=1); self.outer.grid_rowconfigure(3, weight=1)
        self._header(); self._toolbar(); self._stats(); self._table()

    def _header(self) -> None:
        f = tk.Frame(self.outer, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER); f.grid(row=0, column=0, sticky="ew", pady=(0, 9)); f.grid_columnconfigure(1, weight=1)
        tk.Label(f, text="▦", bg=BLUE, fg="white", font=("Segoe UI Symbol", 17, "bold"), width=3, height=2).grid(row=0, column=0, rowspan=2, padx=(12, 10), pady=8)
        tk.Label(f, text="KVTM - Dọn Quầy", bg=SURFACE, fg=TEXT, font=("Segoe UI", 14, "bold")).grid(row=0, column=1, sticky="sw", pady=(10, 0))
        tk.Label(f, text="Quản lý nhiều tài khoản · Tối ưu · Hiệu quả", bg=SURFACE, fg=MUTED, font=("Segoe UI", 8)).grid(row=1, column=1, sticky="nw", pady=(1, 10))
        box = tk.Frame(f, bg=SURFACE); box.grid(row=0, column=2, rowspan=2, padx=16)
        self.header_dot = tk.Label(box, text="●", bg=SURFACE, fg=GREEN); self.header_dot.pack(side="left", padx=(0, 5))
        self.header_status = tk.Label(box, textvariable=self.status_var, bg=SURFACE, fg=GREEN, font=("Segoe UI", 9, "bold")); self.header_status.pack(side="left")

    def _toolbar(self) -> None:
        f = tk.Frame(self.outer, bg=BG); f.grid(row=1, column=0, sticky="ew", pady=(0, 9)); f.grid_columnconfigure(5, weight=1)
        specs = (("▶  Bắt đầu tất cả", self.start_all, True, 15), ("Ⅱ  Dừng tất cả", self.stop_all, False, 13),
                 ("＋  Thêm tài khoản", self.add_account, False, 14), ("↻  Đồng bộ profile", self.sync_profiles, False, 14))
        for i, spec in enumerate(specs): self._button(f, *spec).grid(row=0, column=i, padx=(0 if i == 0 else 7, 7))
        self._button(f, "⚙  Cấu hình nhanh", self.quick_config, False, 14).grid(row=0, column=6, sticky="e")

    def _stats(self) -> None:
        self.stats_host = tk.Frame(self.outer, bg=BG); self.stats_host.grid(row=2, column=0, sticky="ew", pady=(0, 9))
        for i in range(5): self.stats_host.grid_columnconfigure(i, weight=1, uniform="s")
        self.stat_values = []
        for i, (icon, label, color) in enumerate((("♙", "Tổng tài khoản", TEXT), ("▶", "Đang chạy", GREEN), ("●", "Sẵn sàng", "#2D7FF9"), ("■", "Đã dừng", RED), ("◷", "Chu kỳ mặc định", BLUE))):
            card = tk.Frame(self.stats_host, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER); card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 5, 0 if i == 4 else 5)); card.grid_columnconfigure(1, weight=1)
            tk.Label(card, text=icon, bg=ALT, fg=color, font=("Segoe UI Symbol", 16, "bold"), width=3, height=2).grid(row=0, column=0, rowspan=2, padx=(12, 8), pady=12)
            tk.Label(card, text=label, bg=SURFACE, fg=MUTED, font=("Segoe UI", 8)).grid(row=0, column=1, sticky="sw", pady=(12, 1))
            value = tk.Label(card, text="0", bg=SURFACE, fg=color, font=("Segoe UI", 14, "bold")); value.grid(row=1, column=1, sticky="nw", pady=(0, 12)); self.stat_values.append(value)

    def _table(self) -> None:
        card = tk.Frame(self.outer, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER); card.grid(row=3, column=0, sticky="nsew"); card.grid_columnconfigure(0, weight=1); card.grid_rowconfigure(2, weight=1)
        title = tk.Frame(card, bg=SURFACE); title.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 9)); title.grid_columnconfigure(0, weight=1)
        tk.Label(title, text="Danh sách tài khoản", bg=SURFACE, fg=TEXT, font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        self.table_meta = tk.Label(title, bg=SURFACE, fg=MUTED, font=("Segoe UI", 8)); self.table_meta.grid(row=0, column=1, sticky="e")
        head = tk.Frame(card, bg=ALT, highlightthickness=1, highlightbackground=BORDER); head.grid(row=1, column=0, sticky="ew", padx=14); self._columns(head)
        tk.Checkbutton(head, variable=self.header_select, command=self.select_page, bg=ALT, activebackground=ALT, selectcolor="white", bd=0, highlightthickness=0).grid(row=0, column=0, padx=7, pady=8)
        for c, text in enumerate(("#", "TÊN TÀI KHOẢN", "PROFILE", "TRẠNG THÁI", "LẦN DỌN CUỐI", "CHU KỲ", "LOG", "THAO TÁC"), 1):
            tk.Label(head, text=text, bg=ALT, fg=MUTED, font=("Segoe UI", 8, "bold"), anchor="center" if c in (1, 7, 8) else "w").grid(row=0, column=c, padx=8, pady=9, sticky="ew")
        self.rows = tk.Frame(card, bg=SURFACE); self.rows.grid(row=2, column=0, sticky="nsew", padx=14); self.rows.grid_columnconfigure(0, weight=1)
        foot = tk.Frame(card, bg=SURFACE); foot.grid(row=3, column=0, sticky="ew", padx=14, pady=(10, 12)); foot.grid_columnconfigure(1, weight=1)
        self.selected_label = tk.Label(foot, bg=SURFACE, fg=MUTED, font=("Segoe UI", 8)); self.selected_label.grid(row=0, column=0)
        self.pager = tk.Frame(foot, bg=SURFACE); self.pager.grid(row=0, column=2)

    def refresh(self) -> None:
        total = len(self.accounts); running = sum(a.status == "running" for a in self.accounts); ready = sum(a.status == "ready" for a in self.accounts); stopped = sum(a.status == "stopped" for a in self.accounts)
        for w, v in zip(self.stat_values, (total, running, ready, stopped, f"{self.default_cycle} phút")): w.config(text=str(v))
        self.table_meta.config(text=f"{total} tài khoản · {running} đang chạy")
        color = GREEN if running or ready or not total else RED; self.status_var.set(f"Đang hoạt động · {running}" if running else ("Sẵn sàng" if ready or not total else "Đã dừng")); self.header_dot.config(fg=color); self.header_status.config(fg=color)
        self._rows(); self._footer()

    def _rows(self) -> None:
        start = self.page * self.PAGE_SIZE; page = self.accounts[start:start + self.PAGE_SIZE]
        signature = tuple(a.account_id for a in page)
        if signature == self._row_signature:
            for offset, account in enumerate(page):
                labels = self._row_value_labels.get(account.account_id)
                if not labels:
                    self._row_signature = None
                    break
                values = (
                    str(start + offset + 1), account.account_name,
                    account.profile_name, account.status_text,
                    account.last_clean, f"{account.cycle_minutes} phút",
                )
                for column, (label, value) in enumerate(zip(labels, values), 1):
                    label.configure(
                        text=f"●  {value}" if column == 4 else value,
                        fg=(
                            account.status_color if column == 4
                            else (MUTED if value == "—" or column == 1 else TEXT)
                        ),
                    )
            if signature == self._row_signature:
                return

        for w in self.rows.winfo_children(): w.destroy()
        self._row_signature = signature
        self._row_value_labels = {}
        if not page:
            f = tk.Frame(self.rows, bg=SURFACE); f.grid(row=0, column=0, pady=70)
            tk.Label(f, text="Chưa có tài khoản", bg=SURFACE, fg=TEXT, font=("Segoe UI", 11, "bold")).pack()
            tk.Label(f, text="Nhấn “Thêm tài khoản” hoặc “Đồng bộ profile” để bắt đầu.", bg=SURFACE, fg=MUTED).pack(pady=5); return
        for r, a in enumerate(page):
            row = tk.Frame(self.rows, bg=SURFACE); row.grid(row=r, column=0, sticky="ew"); self._columns(row)
            tk.Checkbutton(row, variable=self.selected.setdefault(a.account_id, tk.BooleanVar()), command=self._footer, bg=SURFACE, activebackground=SURFACE, selectcolor="white", bd=0, highlightthickness=0).grid(row=0, column=0, padx=7, pady=7)
            vals = (str(start+r+1), a.account_name, a.profile_name, a.status_text, a.last_clean, f"{a.cycle_minutes} phút")
            value_labels = []
            for c, val in enumerate(vals, 1):
                fg = a.status_color if c == 4 else (MUTED if val == "—" or c == 1 else TEXT); font = ("Segoe UI", 9, "bold") if c in (2, 4) else ("Segoe UI", 9)
                text = f"●  {val}" if c == 4 else val
                label = tk.Label(row, text=text, bg=SURFACE, fg=fg, font=font, anchor="center" if c == 1 else "w")
                label.grid(row=0, column=c, padx=8, pady=9, sticky="ew")
                value_labels.append(label)
            self._row_value_labels[a.account_id] = value_labels
            log_cell = tk.Frame(row, bg=SURFACE); log_cell.grid(row=0, column=7, padx=6)
            self._mini(log_cell, "Log", BLUE, lambda i=a.account_id: self.show_log(i), 6).pack()
            acts = tk.Frame(row, bg=SURFACE); acts.grid(row=0, column=8, padx=6)
            self._mini(acts, "▶", BLUE, lambda i=a.account_id: self.set_status(i, "running")).pack(side="left", padx=2)
            self._mini(acts, "＋", GREEN, lambda i=a.account_id: self.enqueue_account(i)).pack(side="left", padx=2)
            self._mini(acts, "■", RED, lambda i=a.account_id: self.set_status(i, "stopped")).pack(side="left", padx=2)
            self._mini(acts, "•••", MUTED, lambda i=a.account_id: self.details(i), 4).pack(side="left", padx=2)
            tk.Frame(row, bg=BORDER, height=1).grid(row=1, column=0, columnspan=9, sticky="ew")

    @staticmethod
    def _mini(master, text, fg, command, width=3):
        return tk.Button(master, text=text, command=command, bg=ALT, fg=fg, activebackground="#EEF3FA", relief="flat", bd=0, width=width, pady=3, cursor="hand2", highlightthickness=1, highlightbackground=BORDER, font=("Segoe UI", 8, "bold"))

    def _footer(self) -> None:
        self.selected_label.config(text=f"Đã chọn {sum(v.get() for v in self.selected.values())} tài khoản")
        for w in self.pager.winfo_children(): w.destroy()
        pages = max(1, (len(self.accounts)+self.PAGE_SIZE-1)//self.PAGE_SIZE); self.page = min(self.page, pages-1)
        self._button(self.pager, "‹", lambda: self.goto(self.page-1), False, 2).pack(side="left", padx=2)
        for i in range(pages): self._button(self.pager, str(i+1), lambda p=i: self.goto(p), i == self.page, 2).pack(side="left", padx=2)
        self._button(self.pager, "›", lambda: self.goto(self.page+1), False, 2).pack(side="left", padx=2)
        visible = self.accounts[self.page*self.PAGE_SIZE:(self.page+1)*self.PAGE_SIZE]
        self.header_select.set(bool(visible) and all(self.selected[a.account_id].get() for a in visible))

    def goto(self, page: int) -> None:
        pages = max(1, (len(self.accounts)+self.PAGE_SIZE-1)//self.PAGE_SIZE); self.page = max(0, min(page, pages-1)); self.refresh()

    def select_page(self) -> None:
        value = self.header_select.get()
        for a in self.accounts[self.page*self.PAGE_SIZE:(self.page+1)*self.PAGE_SIZE]: self.selected[a.account_id].set(value)
        self._footer()

    def set_status(self, account_id: str, status: str) -> None:
        self.accounts = [replace(a, status=status) if a.account_id == account_id else a for a in self.accounts]; self.refresh()

    def start_all(self) -> None: self.accounts = [replace(a, status="running") for a in self.accounts]; self.refresh()
    def stop_all(self) -> None: self.accounts = [replace(a, status="stopped") for a in self.accounts]; self.refresh()

    def _modal(self, title: str, width=450, height=260):
        w = tk.Toplevel(self.root); w.title(title); w.configure(bg=SURFACE); w.resizable(False, False); self.root.update_idletasks()
        x = self.root.winfo_rootx() + max(20, (self.root.winfo_width()-width)//2); y = self.root.winfo_rooty() + max(20, (self.root.winfo_height()-height)//2); w.geometry(f"{width}x{height}+{x}+{y}"); w.transient(self.root); w.grab_set(); return w

    def add_account(self) -> None:
        w = self._modal("Thêm tài khoản", 460, 285); body = tk.Frame(w, bg=SURFACE); body.pack(fill="both", expand=True, padx=22, pady=18)
        tk.Label(body, text="Thêm tài khoản Dọn quầy", bg=SURFACE, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        name = tk.StringVar(); profile = tk.StringVar()
        for label, var in (("Tên tài khoản", name), ("Profile", profile)):
            row = tk.Frame(body, bg=SURFACE); row.pack(fill="x", pady=7); tk.Label(row, text=label, bg=SURFACE, fg=MUTED, width=18, anchor="w").pack(side="left"); ttk.Entry(row, textvariable=var, style="Modern.TEntry").pack(side="left", fill="x", expand=True)
        def save():
            if not name.get().strip() or not profile.get().strip(): return
            key = f"local-{len(self.accounts)+1}"; self.accounts.append(AccountRecord(key, name.get().strip(), profile.get().strip(), cycle_minutes=self.default_cycle)); self.selected[key] = tk.BooleanVar(); self.refresh(); w.destroy()
        self._button(body, "Thêm", save, True, 9).pack(side="right", pady=18); self._button(body, "Hủy", w.destroy, False, 9).pack(side="right", padx=8, pady=18)

    def sync_profiles(self) -> None:
        w = self._modal("Đồng bộ profile", 460, 225); body = tk.Frame(w, bg=SURFACE); body.pack(fill="both", expand=True, padx=24, pady=22)
        tk.Label(body, text="↻", bg=SURFACE, fg=BLUE, font=("Segoe UI Symbol", 24, "bold")).pack(); tk.Label(body, text="Giao diện đồng bộ đã sẵn sàng", bg=SURFACE, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(pady=4)
        tk.Label(body, text="Bước tiếp theo sẽ nối AUTO MULTI DEV\nvới profiles.json riêng của tool Dọn quầy.", bg=SURFACE, fg=MUTED, justify="center").pack(); self._button(body, "Đóng", w.destroy, True, 9).pack(pady=14)

    def quick_config(self) -> None:
        w = self._modal("Cấu hình nhanh", 470, 270); body = tk.Frame(w, bg=SURFACE); body.pack(fill="both", expand=True, padx=22, pady=18)
        tk.Label(body, text="Cấu hình nhanh", bg=SURFACE, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(anchor="w"); var = tk.StringVar(value=str(self.default_cycle))
        row = tk.Frame(body, bg=SURFACE); row.pack(fill="x", pady=18); tk.Label(row, text="Chu kỳ mặc định (phút)", bg=SURFACE, fg=MUTED, width=24, anchor="w").pack(side="left"); ttk.Entry(row, textvariable=var, style="Modern.TEntry").pack(side="left", fill="x", expand=True)
        def save():
            try: self.default_cycle = max(1, min(1440, int(var.get())))
            except ValueError: return
            self.accounts = [replace(a, cycle_minutes=self.default_cycle) for a in self.accounts]; self.refresh(); w.destroy()
        self._button(body, "Lưu", save, True, 9).pack(side="right", pady=14); self._button(body, "Hủy", w.destroy, False, 9).pack(side="right", padx=8, pady=14)

    def show_log(self, account_id: str) -> None:
        a = next((x for x in self.accounts if x.account_id == account_id), None)
        if not a: return
        w = self._modal(f"Log - {a.account_name}", 560, 250); body = tk.Frame(w, bg=SURFACE); body.pack(fill="both", expand=True, padx=22, pady=18)
        tk.Label(body, text="Log runtime", bg=SURFACE, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        tk.Label(body, text="Chế độ demo không ghi log runtime. Bản chạy thật sẽ hiển thị log trực tiếp tại đây.", bg=SURFACE, fg=MUTED, justify="left", wraplength=500).pack(anchor="w", pady=12)
        self._button(body, "Đóng", w.destroy, True, 9).pack(anchor="e", pady=10)

    def details(self, account_id: str) -> None:
        a = next((x for x in self.accounts if x.account_id == account_id), None)
        if not a: return
        w = self._modal("Chi tiết tài khoản", 420, 235); body = tk.Frame(w, bg=SURFACE); body.pack(fill="both", expand=True, padx=22, pady=18)
        tk.Label(body, text=a.account_name, bg=SURFACE, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(anchor="w"); tk.Label(body, text=f"{a.profile_name} · {a.status_text} · {a.cycle_minutes} phút", bg=SURFACE, fg=MUTED).pack(anchor="w", pady=5); tk.Label(body, text=f"Lần dọn cuối: {a.last_clean}\nGhi chú: {a.note}", bg=SURFACE, fg=TEXT, justify="left").pack(anchor="w", pady=12); self._button(body, "Đóng", w.destroy, True, 9).pack(anchor="e")


def demo_accounts() -> list[AccountRecord]:
    rows = (("demo_shop_01", "running", "14:28", "Quầy chính"), ("demo_farm_02", "ready", "13:45", "—"), ("demo_store_03", "stopped", "12:10", "Cần kiểm tra"), ("demo_house_04", "ready", "11:33", "—"), ("demo_item_05", "running", "14:12", "SKU mới"), ("demo_market_06", "ready", "10:55", "—"), ("demo_online_07", "ready", "09:20", "—"), ("demo_daily_08", "running", "14:05", "—"), ("demo_farm_09", "ready", "08:42", "—"), ("demo_shop_10", "stopped", "08:15", "Tạm dừng"))
    return [AccountRecord(f"demo-{i:02d}", name, f"Profile {i}", status, f"{last} 16/09", 30, note) for i, (name, status, last, note) in enumerate(rows, 1)]
