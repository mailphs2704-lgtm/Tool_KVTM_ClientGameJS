from __future__ import annotations


__all__ = ["install_optional_features_integration"]

FILE_FUNCTIONS = (
    "Thay vị trí Function selector cũ bằng khu vực Tùy chọn của AUTO MULTI DEV",
    "Tùy chọn đầu tiên là Mở rương hải tặc và mặc định OFF",
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
    """Install DEV-only optional features without touching the legacy core UI.

    The production Function scheduler remains the execution backbone for now,
    but its old selector occupies no visible UI space in AUTO MULTI DEV. That
    location becomes the optional-feature area. Each option is persisted per
    profile and is frozen into the run marker before the isolated worker reads
    it, so multiple accounts can use different settings safely.
    """
    if getattr(app_class, "_kvtm_optional_features_installed", False):
        return

    original_build_auto_panel = app_class._build_auto_panel
    original_refresh_profile_settings = (
        app_class._refresh_auto_multi_dev_profile_settings
    )
    original_start_configured_auto_main = app_class._start_configured_auto_main
    original_run_clean_main_thread = app_class._run_clean_main_thread

    def _optional_profile_id(self) -> str | None:
        resolver = getattr(self, "_auto_multi_dev_profile_id", None)
        if callable(resolver):
            profile_id = resolver()
            if profile_id:
                return str(profile_id)
        selected = list(map(str, self.selected_ids()))
        return selected[0] if len(selected) == 1 else None

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
        profile_id = self._optional_profile_id()
        if not profile_id:
            return
        enabled = bool(self.auto_multi_dev_pirate_chest_enabled.get())
        saved = {"pirate_chest_enabled": enabled}
        self.settings.setdefault(_OPTIONAL_FEATURES_KEY, {})[profile_id] = saved
        core.save_settings(self.settings)
        self.note.set(
            "AUTO MULTI DEV • Tùy chọn Mở rương hải tặc="
            + ("BẬT • check đầu sau sale đầu • chu kỳ 20 phút" if enabled else "TẮT")
        )

    def _refresh_optional_features(self) -> None:
        if not hasattr(self, "auto_multi_dev_pirate_chest_enabled"):
            return
        self._optional_features_refreshing = True
        try:
            profile_id = self._optional_profile_id()
            profile = next(
                (
                    item for item in self.profiles
                    if str(item.get("id") or "") == str(profile_id or "")
                ),
                None,
            )
            enabled = False
            if profile_id and profile is not None:
                enabled = bool(
                    self._optional_profile_settings(profile_id)[
                        "pirate_chest_enabled"
                    ]
                )
            self.auto_multi_dev_pirate_chest_enabled.set(enabled)
            button = getattr(self, "auto_multi_dev_pirate_chest_button", None)
            if button is not None:
                button.configure(state="normal" if profile is not None else "disabled")
        finally:
            self._optional_features_refreshing = False

    def _replace_function_slot_with_optional_features(self) -> None:
        function_button = getattr(self, "auto_multi_dev_function_button", None)
        if function_button is None:
            return
        option_box = function_button.master
        for child in tuple(option_box.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass

        core.ttk.Label(
            option_box,
            text="TÙY CHỌN",
            style="AutoKey.TLabel",
        ).pack(anchor="w")
        self.auto_multi_dev_pirate_chest_enabled = core.tk.BooleanVar(
            value=False
        )
        self.auto_multi_dev_pirate_chest_button = self._make_toggle_button(
            option_box,
            "Mở rương hải tặc",
            self.auto_multi_dev_pirate_chest_enabled,
            self._save_optional_features,
        )
        self.auto_multi_dev_pirate_chest_button.configure(
            anchor="center", padx=9, pady=6
        )
        self.auto_multi_dev_pirate_chest_button.pack(fill="x", pady=(4, 0))
        core.ttk.Label(
            option_box,
            text="Sau sale đầu • check lại mỗi 20 phút • không cắt ngang Function",
            style="AutoValue.TLabel",
            anchor="w",
            justify="left",
            wraplength=250,
        ).pack(fill="x", pady=(4, 0))

    def build_auto_panel(self) -> None:
        original_build_auto_panel(self)
        self._optional_features_refreshing = False
        self._optional_features_run_snapshot: dict[str, dict[str, bool]] = {}
        self._replace_function_slot_with_optional_features()
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
    app_class._optional_profile_id = _optional_profile_id
    app_class._optional_profile_settings = _optional_profile_settings
    app_class._save_optional_features = _save_optional_features
    app_class._refresh_optional_features = _refresh_optional_features
    app_class._replace_function_slot_with_optional_features = (
        _replace_function_slot_with_optional_features
    )
    app_class._kvtm_optional_features_installed = True
    print(
        "[KVTM DEV] Optional Features READY • slot cũ=REPLACED • "
        "#1 Mở rương hải tặc • per-profile • default=OFF • safe-boundary=20m",
        flush=True,
    )
