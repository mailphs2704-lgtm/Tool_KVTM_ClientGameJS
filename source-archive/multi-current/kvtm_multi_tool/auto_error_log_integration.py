from __future__ import annotations

from datetime import datetime
from pathlib import Path

from main_log_viewer import open_log_window
from optional_features_integration import install_optional_features_integration
from auto_multi_dev_ui_integration import install_auto_multi_dev_ui_integration
from auto_multi_dev_ui_refinement import install_auto_multi_dev_ui_refinement


__all__ = ["install_auto_error_log_integration"]


def install_auto_error_log_integration(app_class, core) -> None:
    """Expose per-account error-log helpers, then install the final DEV UI layer."""
    if getattr(app_class, "_kvtm_auto_error_log_installed", False):
        return

    from kvtm_automation.error_journal import error_log_file_for_profile

    def _error_log_profile(self) -> tuple[str | None, dict | None]:
        profile_id = str(getattr(self, "_active_profile_id", "") or "")
        if not profile_id:
            try:
                selected = list(map(str, self.selected_ids()))
            except Exception:
                selected = []
            profile_id = selected[0] if len(selected) == 1 else ""
        profile = next(
            (
                item for item in self.profiles
                if str(item.get("id") or "") == profile_id
            ),
            None,
        )
        return (profile_id or None), profile

    def _persistent_error_log_path(self, profile_id: str) -> Path:
        return error_log_file_for_profile(core.APP_DIR, str(profile_id))

    def _open_auto_error_log(self) -> None:
        """Compatibility entry; the main UI now opens this inside the Log window."""
        profile_id, profile = self._error_log_profile()
        if not profile_id or profile is None:
            core.messagebox.showinfo(
                core.APP_NAME,
                "Hãy chọn một tài khoản để xem Log lỗi AUTO.",
            )
            return
        path = self._persistent_error_log_path(profile_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        name = str(profile.get("name") or profile_id)
        open_log_window(self, path, f"KVTM DEV - Log lỗi AUTO - {name}")

    def _export_auto_error_log_txt(self) -> None:
        profile_id, profile = self._error_log_profile()
        if not profile_id or profile is None:
            core.messagebox.showinfo(
                core.APP_NAME,
                "Hãy chọn một tài khoản để xuất Log lỗi AUTO.",
            )
            return
        source = self._persistent_error_log_path(profile_id)
        source.parent.mkdir(parents=True, exist_ok=True)
        source.touch(exist_ok=True)
        name = str(profile.get("name") or profile_id)
        safe_name = "".join(
            char if char.isalnum() or char in "-_" else "_" for char in name
        ).strip("_") or "account"
        initial = (
            f"KVTM_AUTO_ERRORS_{safe_name}_"
            f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
        )
        destination = core.filedialog.asksaveasfilename(
            title="Xuất Log lỗi AUTO",
            defaultextension=".txt",
            filetypes=(("Text file", "*.txt"), ("All files", "*.*")),
            initialfile=initial,
        )
        if not destination:
            return
        try:
            raw = source.read_text(encoding="utf-8", errors="replace")
            header = (
                "KVTM AUTO ERROR LOG\n"
                f"Tài khoản: {name}\n"
                f"Profile ID: {profile_id}\n"
                f"Xuất lúc: {datetime.now().astimezone().isoformat(timespec='seconds')}\n"
                + "=" * 80
                + "\n"
            )
            Path(destination).write_text(header + raw, encoding="utf-8")
        except OSError as exc:
            core.messagebox.showerror(
                core.APP_NAME,
                f"Không xuất được Log lỗi:\n{exc}",
            )
            return
        self.note.set(f"Đã xuất Log lỗi AUTO của {name}: {destination}")

    app_class._error_log_profile = _error_log_profile
    app_class._persistent_error_log_path = _persistent_error_log_path
    app_class._open_auto_error_log = _open_auto_error_log
    app_class._export_auto_error_log_txt = _export_auto_error_log_txt
    app_class._kvtm_auto_error_log_installed = True

    # Optional features were historically a separate source module. Install it
    # here so the final operator UI always has a real per-profile Mở rương toggle
    # before the compact layout reuses the same BooleanVar/callback.
    install_optional_features_integration(app_class, core)
    install_auto_multi_dev_ui_integration(app_class, core)
    install_auto_multi_dev_ui_refinement(app_class, core)

    print(
        "[KVTM DEV] AUTO error journal UI READY • persistent per-profile TXT • "
        "export lives inside combined Log lỗi tab",
        flush=True,
    )
