from __future__ import annotations

import argparse
import ctypes
import os
import sys
import tkinter as tk
from pathlib import Path


def _bind_multi_dev_profile_source() -> None:
    """Point the standalone store at the active AUTO MULTI DEV data directory.

    The operator keeps this tool in a separate worktree, while the authoritative
    Multi DEV runtime normally lives in D:\\Tool_KVTM_Multi_DEV.  Resolve that
    runtime before importing profile_store so its profile/settings constants use
    the same authoritative source.  An explicit KVTM_MULTI_APP_DIR always wins.
    """
    if os.environ.get("KVTM_MULTI_APP_DIR", "").strip():
        return

    source_root = Path(__file__).resolve().parents[2]
    candidates = [
        source_root / "dist" / "KVTM-ClientJS-Suite-Multi-DEV" / "data-dev",
        source_root.parent / "Tool_KVTM_Multi_DEV" / "dist" / "KVTM-ClientJS-Suite-Multi-DEV" / "data-dev",
        Path(os.environ.get("APPDATA", Path.home())) / "KVTM Multi",
    ]
    valid = []
    for directory in candidates:
        profile_file = directory / "profiles.json"
        if not profile_file.is_file():
            continue
        try:
            stamp = profile_file.stat().st_mtime
        except OSError:
            stamp = 0.0
        valid.append((stamp, directory))
    if valid:
        valid.sort(key=lambda item: item[0], reverse=True)
        os.environ["KVTM_MULTI_APP_DIR"] = str(valid[0][1])


_bind_multi_dev_profile_source()

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
        # Full transactional Dọn quầy remains machine-wide serialized, matching
        # the proven Multi contract: never let two accounts buy/resell at once.
        ClearStallController.MAX_CONCURRENCY = 1
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
