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
else:
    from .app import ClearStallToolApp, demo_accounts
    from .branding import install_branding


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
    parser = argparse.ArgumentParser(description="KVTM Dọn Quầy standalone UI preview")
    parser.add_argument("--empty", action="store_true", help="Mở giao diện không có dữ liệu demo")
    args = parser.parse_args()

    _enable_windows_dpi_awareness()
    install_branding(ClearStallToolApp)
    root = tk.Tk()
    ClearStallToolApp(root, [] if args.empty else demo_accounts())
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
