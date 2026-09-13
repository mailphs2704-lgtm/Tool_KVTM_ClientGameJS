from __future__ import annotations


__all__ = ["install_optional_features_integration"]

FILE_FUNCTIONS = (
    "Giữ nguyên ô chọn Function của AUTO MULTI DEV và thêm hàng Tùy chọn riêng bên dưới",
    "Tùy chọn Mở rương hải tặc áp dụng cho toàn bộ tài khoản đang chọn và mặc định OFF",
    "Lưu trạng thái Mở rương riêng cho từng profile/tài khoản",
    "Đóng băng trạng thái tùy chọn theo từng run trước khi worker khởi động",
    "Ghi pirate_chest_enabled vào auto-main-config.json qua pending config hiện có",
    "Giữ flag qua scheduled ClientJS restart bằng active config hiện có",
    "Không thay đổi Bridge/capture, Function engine, sale cadence hay recovery ownership",
)

_OPTIONAL_FEATURES_KEY = "auto_multi_dev_optional_features"
_DEFAULT_OPTIONAL_FEATURES = {
    "pirate_chest_enabled": False,
}


def _normalize_optional_features(raw) -> dict[str, bool]:
    current = raw if isinstance(raw, dict) else {}
    return {
        "pirate_chest_enabled": bool(
            current.get("pirate_chest_enabled", False)
        ),
    }


def install_optional_features_integration(app_class, core) -> None:
    """Install DEV-only optional features without replacing Function selection.

    The verified Function selector remains the execution choice for AUTO Main.
    Optional features live in their own row immediately below the scheduler
    controls. A toggle applies to every profile currently selected in Multi,
    while the saved value remains per-profile and is frozen into each run.
    """
    if getattr(app_class, "_kvtm_optional_features_installed", False):
        return

    original_build_auto_panel = app_class._build_auto_panel
    original_refresh_profile_settings = (
        app_class._refresh_auto_multi_dev_profile_settings
    )
    original_start_configured_auto_main = app_class._start_configured_auto_main
    original_run_clean_main_thread = app_class._run_clean_main_thread

    def _optional_target_profile_ids(self) -> list[str]:
        known = {
            str(item.get("id") or "")
            for item in self.profiles
            if str(item.get("id") or "")
        }
        result: list[str] = []
        for profile_id in map(str, self.selected_ids()):
            if profile_id in known and profile_id not in result:
                result.append(profile_id)
        return result

    def _optional_profile_settings(self, profile_id: str) -> dict[str, bool]:
        profile_id = str(profile_id or "")
        store = self.settings.setdefault(_OPTIONAL_FEATURES_KEY, {})
        if not isinstance(store, dict):
            store = {}
            self.settings[_OPTIONAL_FEATURES_KEY] = store
        saved = _normalize_optional_features(store.get(profile_id, {}))
        store[profile_id] = dict(saved)
        return saved

    def _save_optional_features(self) -> None:
        if getattr(self, "_optional_features_refreshing", False):
            return
        profile_ids = self._optional_target_profile_ids()
        if not profile_ids:
            return
        enabled = bool(self.auto_multi_dev_pirate_chest_enabled.get())
        saved = {"pirate_chest_enabled": enabled}
        for profile_id in profile_ids:
            self.settings.setdefault(_OPTIONAL_FEATURES_KEY, {})[profile_id] = saved
        core.save_settings(self.settings)
        self.note.set(
            "AUTO MULTI DEV • Tùy chọn Mở rương hải tặc="
            + ("BẬT" if enabled else "TẮT")
            + f" • áp dụng {len(profile_ids)} tài khoản"
            + (" • check đầu sau sale đầu • chu kỳ 20 phút" if enabled else "")
        )

    def _refresh_optional_features(self) -> None:
        if not hasattr(self, "auto_multi_dev_pirate_chest_enabled"):
            return
        self._optional_features_refreshing = True
        try:
            profile_ids = self._optional_target_profile_ids()
            enabled = False
            if profile_ids:
                enabled = all(
                    bool(
                        self._optional_profile_settings(profile_id)[
                            "pirate_chest_enabled"
                        ]
                    )
                    for profile_id in profile_ids
                )
            self.auto_multi_dev_pirate_chest_enabled.set(enabled)
            button = getattr(self, "auto_multi_dev_pirate_chest_button", None)
            if button is not None:
                button.configure(
                    state="normal" if profile_ids else "disabled",
                    cursor="hand2" if profile_ids else "arrow",
                )
        finally:
            self._optional_features_refreshing = False

    def _add_optional_features_row(self) -> None:
        function_button = getattr(self, "auto_multi_dev_function_button", None)
        if function_button is None:
            return

        # Keep the verified Function selector untouched. Its parent is the
        # Function box; the grandparent is the five-column scheduler controls.
        function_box = function_button.master
        controls = function_box.master

        old_row = getattr(self, "auto_multi_dev_optional_features_row", None)
        if old_row is not None:
            try:
                old_row.destroy()
            except Exception:
                pass

        option_row = core.ttk.Frame(controls, style="Detail.TFrame")
        option_row.grid(
            row=1,
            column=0,
            columnspan=5,
            sticky="ew",
            pady=(8, 0),
        )
        self.auto_multi_dev_optional_features_row = option_row

        core.ttk.Label(
            option_row,
            text="TÙY CHỌN",
            style="AutoKey.TLabel",
        ).pack(side="left", padx=(0, 12))

        self.auto_multi_dev_pirate_chest_enabled = core.tk.BooleanVar(
            value=False
        )
        self.auto_multi_dev_pirate_chest_button = self._make_toggle_button(
            option_row,
            "Mở rương hải tặc",
            self.auto_multi_dev_pirate_chest_enabled,
            self._save_optional_features,
        )
        self.auto_multi_dev_pirate_chest_button.configure(
            anchor="center", padx=9, pady=6
        )
        self.auto_multi_dev_pirate_chest_button.pack(side="left", padx=(0, 12))

        core.ttk.Label(
            option_row,
            text="Sau sale đầu • check lại mỗi 20 phút • không cắt ngang Function",
            style="AutoValue.TLabel",
            anchor="w",
            justify="left",
        ).pack(side="left", fill="x", expand=True)

    def build_auto_panel(self) -> None:
        original_build_auto_panel(self)
        self._optional_features_refreshing = False
        self._optional_features_run_snapshot: dict[str, dict[str, bool]] = {}
        self._add_optional_features_row()
        self.after_idle(self._refresh_optional_features)

    def refresh_profile_settings(self) -> None:
        original_refresh_profile_settings(self)
        self._refresh_optional_features()

    def start_configured_auto_main(self) -> None:
        selected = list(map(str, self.selected_ids()))
        # Snapshot before the existing scheduler starts any worker thread. This
        # prevents a later UI toggle from mutating an already-started run.
        snapshots = getattr(self, "_optional_features_run_snapshot", None)
        if not isinstance(snapshots, dict):
            snapshots = {}
            self._optional_features_run_snapshot = snapshots
        for profile_id in selected:
            snapshots[profile_id] = dict(
                self._optional_profile_settings(profile_id)
            )
        return original_start_configured_auto_main(self)

    def run_clean_main_thread(self, *args, **kwargs) -> None:
        profile_id = str(args[0] if args else kwargs.get("profile_id") or "")
        snapshots = getattr(self, "_optional_features_run_snapshot", {})
        snapshot = snapshots.pop(profile_id, None) if isinstance(snapshots, dict) else None
        if isinstance(snapshot, dict):
            enabled = bool(snapshot.get("pirate_chest_enabled", False))
            pending = getattr(self, "_auto_main_pending_config", None)
            if isinstance(pending, dict):
                config = pending.get(profile_id)
                if isinstance(config, dict):
                    config["pirate_chest_enabled"] = enabled
            active = getattr(self, "_auto_main_active_config", None)
            if isinstance(active, dict):
                config = active.get(profile_id)
                if isinstance(config, dict):
                    config["pirate_chest_enabled"] = enabled
        return original_run_clean_main_thread(self, *args, **kwargs)

    app_class._build_auto_panel = build_auto_panel
    app_class._refresh_auto_multi_dev_profile_settings = refresh_profile_settings
    app_class._start_configured_auto_main = start_configured_auto_main
    app_class._run_clean_main_thread = run_clean_main_thread
    app_class._optional_target_profile_ids = _optional_target_profile_ids
    app_class._optional_profile_settings = _optional_profile_settings
    app_class._save_optional_features = _save_optional_features
    app_class._refresh_optional_features = _refresh_optional_features
    app_class._add_optional_features_row = _add_optional_features_row
    app_class._kvtm_optional_features_installed = True
    print(
        "[KVTM DEV] Optional Features READY • Function selector=PRESERVED • "
        "#1 Mở rương hải tặc • multi-select=READY • per-profile • "
        "default=OFF • safe-boundary=20m",
        flush=True,
    )
