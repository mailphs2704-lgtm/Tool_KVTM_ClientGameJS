from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def install_original_auto_pro_integration(app_cls, core) -> None:
    """Expose the original recovered AUTO PRO as a separate Stable Cry window."""
    if getattr(app_cls, "_original_auto_pro_integration_installed", False):
        return

    original_build_ui = app_cls._build_ui

    def launch_original_auto_pro(self) -> None:
        child = getattr(self, "_original_auto_pro_process", None)
        if child is not None and child.poll() is None:
            self.note.set("AUTO PRO gốc đang mở ở cửa sổ riêng")
            return

        package_root = Path(__file__).resolve().parent.parent
        auto_root = package_root / "AUTO_PRO_ORIGINAL"
        launcher = auto_root / "cry_original_launcher.py"
        if not launcher.is_file():
            self.note.set(f"Thiếu launcher AUTO PRO gốc: {launcher}")
            return

        env = os.environ.copy()
        env["KVTM_MULTI_APP_DIR"] = str(core.APP_DIR)
        env["KVTM_MULTI_PROFILE_FILE"] = str(core.PROFILE_FILE)
        env["KVTM_AUTO_PRO_TRANSPORT"] = "bridge-v3"
        env["KVTM_AUTO_PRO_ADB_DISABLED"] = "1"
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            child = subprocess.Popen(
                [sys.executable, str(launcher)],
                cwd=str(auto_root),
                env=env,
                creationflags=flags,
            )
        except Exception as exc:
            self.note.set(
                "Không mở được AUTO PRO gốc: "
                f"{type(exc).__name__}: {exc}"
            )
            return
        self._original_auto_pro_process = child
        self.note.set(
            "Đã mở AUTO PRO gốc riêng • chỉ ClientJS thuộc Cry • Bridge V3 • ADB tắt"
        )

    def build_ui_with_original_auto_pro(self) -> None:
        original_build_ui(self)
        try:
            menu_name = str(self.cget("menu") or "")
            menubar = self.nametowidget(menu_name) if menu_name else None
        except Exception:
            menubar = None
        if menubar is None:
            menubar = core.tk.Menu(self, tearoff=False)
            self.configure(menu=menubar)
        menubar.add_command(
            label="AUTO PRO gốc",
            command=lambda: launch_original_auto_pro(self),
        )

    app_cls._build_ui = build_ui_with_original_auto_pro
    app_cls.open_original_auto_pro = launch_original_auto_pro
    app_cls._original_auto_pro_integration_installed = True
    print(
        "[KVTM CRY] Original AUTO PRO launcher READY • separate GUI • "
        "offline auth • Cry ownership • Bridge V3 • ADB disabled",
        flush=True,
    )
