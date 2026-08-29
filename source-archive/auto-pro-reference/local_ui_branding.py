from __future__ import annotations

import ctypes
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def apply_process_app_id() -> None:
    """Give the Tk launcher its own Windows taskbar identity."""
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Cry.AUTO_KVTM_PRO.LocalLauncher"
        )
    except Exception:
        pass


def _brand_ico() -> Path | None:
    """Use an explicit icon only; never guess from arbitrary asset PNGs."""
    for path in (
        ROOT / "local_data" / "launcher_icon.ico",
        ROOT / "assets" / "icon" / "app.ico",
        ROOT / "_internal" / "assets" / "icon" / "app.ico",
    ):
        if path.is_file():
            return path
    return None


def _brand_png() -> Path | None:
    """PNG fallback for Tk builds where iconbitmap cannot load the ICO."""
    for path in (
        ROOT / "local_data" / "launcher_icon.png",
        ROOT / "assets" / "icon" / "icon.png",
        ROOT / "_internal" / "assets" / "icon" / "icon.png",
    ):
        if path.is_file():
            return path
    return None


def apply_window_icon(app) -> Path | None:
    """Apply the original recovered AUTO/KVTM icon, never an auto-selected asset."""
    ico = _brand_ico()
    if ico is not None:
        try:
            app.iconbitmap(default=str(ico))
            return ico
        except Exception:
            pass

    png = _brand_png()
    if png is None:
        return None
    try:
        import tkinter as tk

        photo = tk.PhotoImage(file=str(png))
        app.iconphoto(True, photo)
        app._kvtm_brand_icon = photo
        return png
    except Exception:
        return None
