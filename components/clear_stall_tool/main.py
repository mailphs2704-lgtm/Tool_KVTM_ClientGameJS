from __future__ import annotations

import argparse
import ctypes
import os
import sys
import tkinter as tk
from pathlib import Path


def _bind_multi_dev_profile_source() -> None:
    """Bind standalone Dọn quầy to the authoritative AUTO MULTI DEV data root.

    START_MULTI_DEV_SILENT.ps1 makes ``%APPDATA%\\KVTM Multi DEV`` authoritative.
    The standalone process is launched separately, so it does not inherit the
    ``KVTM_MULTI_APP_DIR`` environment variable from the already-running Multi
    DEV process. Resolve the same persistent directory explicitly before
    importing profile_store. Never silently fall back to ``%APPDATA%\\KVTM Multi``
    because that belongs to the non-DEV/legacy Multi profile set.
    """
    if os.environ.get("KVTM_MULTI_APP_DIR", "").strip():
        return

    appdata = Path(os.environ.get("APPDATA", Path.home()))
    authoritative = appdata / "KVTM Multi DEV"
    if (authoritative / "profiles.json").is_file() or authoritative.is_dir():
        os.environ["KVTM_MULTI_APP_DIR"] = str(authoritative)
        return

    # Migration-only fallback for a machine where Multi DEV has not yet copied
    # package-local data-dev into %APPDATA%. Keep this deterministic and DEV-only.
    source_root = Path(__file__).resolve().parents[2]
    legacy_candidates = (
        source_root.parent
        / "Tool_KVTM_Multi_DEV"
        / "dist"
        / "KVTM-ClientJS-Suite-Multi-DEV"
        / "data-dev",
        source_root / "dist" / "KVTM-ClientJS-Suite-Multi-DEV" / "data-dev",
    )
    for directory in legacy_candidates:
        if (directory / "profiles.json").is_file():
            os.environ["KVTM_MULTI_APP_DIR"] = str(directory)
            return

    # Even when the file does not exist yet, point at the authoritative DEV
    # location so the error message names the correct source instead of reading
    # an unrelated profile set.
    os.environ["KVTM_MULTI_APP_DIR"] = str(authoritative)


_bind_multi_dev_profile_source()

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from app import ClearStallToolApp, demo_accounts
    from branding import install_branding
    from profile_store import ProfileStore
    from runtime_controller import RuntimeLayoutError
    from runtime_integration import bind_runtime, install_runtime_integration
    from runtime_policy import OrderedSafeClearStallController
else:
    from .app import ClearStallToolApp, demo_accounts
    from .branding import install_branding
    from .profile_store import ProfileStore
    from .runtime_controller import RuntimeLayoutError
    from .runtime_integration import bind_runtime, install_runtime_integration
    from .runtime_policy import OrderedSafeClearStallController


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
        # Full transactional Dọn quầy remains machine-wide serialized. The
        # ordered controller also guarantees Start All enters this single slot
        # in the same top-to-bottom order shown by the account table.
        OrderedSafeClearStallController.MAX_CONCURRENCY = 1
        controller = OrderedSafeClearStallController(
            root, store, lambda *_args: None
        )
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
