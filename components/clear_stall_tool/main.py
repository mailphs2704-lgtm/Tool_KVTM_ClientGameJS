from __future__ import annotations

import argparse
import ctypes
import sys
import tkinter as tk
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from app import ClearStallToolApp, demo_accounts
    from branding import install_branding
    from profile_store import ProfileStore
    from runtime_controller import ClearStallController, RuntimeLayoutError
    from runtime_integration import bind_runtime, install_runtime_integration
else:
    from .app import ClearStallToolApp, demo_accounts
    from .branding import install_branding
    from .profile_store import ProfileStore
    from .runtime_controller import ClearStallController, RuntimeLayoutError
    from .runtime_integration import bind_runtime, install_runtime_integration


def _enable_windows_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="KVTM Dọn Quầy standalone")
    parser.add_argument("--demo", action="store_true", help="Mở dữ liệu demo, không nối runtime thật")
    args = parser.parse_args()

    _enable_windows_dpi_awareness()
    install_branding(ClearStallToolApp)

    if args.demo:
        root = tk.Tk()
        ClearStallToolApp(root, demo_accounts())
        root.mainloop()
        return 0

    install_runtime_integration(ClearStallToolApp)
    store = ProfileStore()
    root = tk.Tk()
    app = ClearStallToolApp(root, store.account_rows())
    try:
        controller = ClearStallController(root, store, lambda *_args: None)
    except RuntimeLayoutError as exc:
        from tkinter import messagebox
        root.withdraw()
        messagebox.showerror("KVTM - Dọn Quầy", str(exc), parent=root)
        root.destroy()
        return 2

    bind_runtime(app, store, controller)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
