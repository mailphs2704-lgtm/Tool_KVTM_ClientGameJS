from __future__ import annotations

from pathlib import Path
import sys
import traceback

from local_launcher_package_core_v1 import AG
import local_bridge
import local_options_bridge_v08
import local_settings_bridge
import local_function_actions_bridge_v5
from local_ui_branding import apply_process_app_id, apply_window_icon

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
ERROR_LOG = ROOT / "local_data" / "launcher_error.log"


def _report_fatal_error() -> None:
    text = traceback.format_exc()
    try:
        ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with ERROR_LOG.open("a", encoding="utf-8") as f:
            f.write("\n" + "=" * 72 + "\n")
            f.write(text)
    except Exception:
        pass
    try:
        from tkinter import messagebox
        messagebox.showerror(
            "AUTO KVTM PRO",
            "Launcher gặp lỗi. Chi tiết đã lưu tại:\n"
            f"{ERROR_LOG}",
        )
    except Exception:
        pass


if __name__ == "__main__":
    # Must be set before Tk creates its first native window so Windows gives the
    # launcher its own taskbar identity instead of grouping it as python.exe.
    apply_process_app_id()
    try:
        app = AG()
        apply_window_icon(app)
        local_bridge.start_bridge(app)
        local_options_bridge_v08.start_options_bridge(app)
        local_settings_bridge.start_settings_bridge(app)
        local_function_actions_bridge_v5.start_function_actions_bridge(app)
        app.mainloop()
    except Exception:
        _report_fatal_error()
