from __future__ import annotations

from pathlib import Path
import tkinter as tk

try:
    from .app import BORDER, GREEN, MUTED, SURFACE, TEXT
except ImportError:
    from app import BORDER, GREEN, MUTED, SURFACE, TEXT


LOGO_PATH = Path(__file__).resolve().parent / "assets" / "kvtm_clear_stall_logo.png"


def install_branding(app_class) -> None:
    """Install the approved Model-8 market-stall logo into the standalone GUI."""
    if getattr(app_class, "_kvtm_branding_installed", False):
        return

    original_setup = app_class._setup

    def _setup(self) -> None:
        original_setup(self)
        self.brand_logo_image = None
        try:
            self.brand_logo_image = tk.PhotoImage(file=str(LOGO_PATH))
            self.root.iconphoto(True, self.brand_logo_image)
        except (tk.TclError, OSError):
            self.brand_logo_image = None

    def _header(self) -> None:
        frame = tk.Frame(
            self.outer,
            bg=SURFACE,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 9))
        frame.grid_columnconfigure(1, weight=1)

        if self.brand_logo_image is not None:
            logo = tk.Label(
                frame,
                image=self.brand_logo_image,
                bg=SURFACE,
                bd=0,
                highlightthickness=0,
            )
            logo.grid(row=0, column=0, rowspan=2, padx=(14, 12), pady=8)
        else:
            tk.Label(
                frame,
                text="▦",
                bg=SURFACE,
                fg=TEXT,
                font=("Segoe UI Symbol", 17, "bold"),
                width=3,
                height=2,
            ).grid(row=0, column=0, rowspan=2, padx=(12, 10), pady=8)

        tk.Label(
            frame,
            text="KVTM - Dọn Quầy",
            bg=SURFACE,
            fg=TEXT,
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=1, sticky="sw", pady=(10, 0))
        tk.Label(
            frame,
            text="Quản lý nhiều tài khoản · Tối ưu · Hiệu quả",
            bg=SURFACE,
            fg=MUTED,
            font=("Segoe UI", 8),
        ).grid(row=1, column=1, sticky="nw", pady=(1, 10))

        box = tk.Frame(frame, bg=SURFACE)
        box.grid(row=0, column=2, rowspan=2, padx=16)
        self.header_dot = tk.Label(box, text="●", bg=SURFACE, fg=GREEN)
        self.header_dot.pack(side="left", padx=(0, 5))
        self.header_status = tk.Label(
            box,
            textvariable=self.status_var,
            bg=SURFACE,
            fg=GREEN,
            font=("Segoe UI", 9, "bold"),
        )
        self.header_status.pack(side="left")

    app_class._setup = _setup
    app_class._header = _header
    app_class._kvtm_branding_installed = True
