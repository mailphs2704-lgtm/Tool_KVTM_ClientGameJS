from __future__ import annotations

__all__ = ["install_optional_features_integration"]

FILE_FUNCTIONS = (
    "Giữ nguyên ô chọn Function của AUTO MULTI DEV và đặt Tùy chọn vào ô điều khiển bên phải hiện có",
    "Không tạo thêm hàng dọc nên Log hành động/Log chi tiết luôn còn trong vùng hiển thị",
    "Tùy chọn Mở rương hải tặc áp dụng cho toàn bộ tài khoản đang chọn và mặc định OFF",
    "Lưu trạng thái Mở rương riêng cho từng profile/tài khoản",
    "Đóng băng trạng thái tùy chọn theo từng run trước khi worker khởi động",
    "Ghi pirate_chest_enabled vào auto-main-config.json qua pending config hiện có",
    "Ghi feed_mill_enabled vào config; AUTO chỉ xay sau Function + sale tại safe boundary",
    "Giữ flag qua scheduled ClientJS restart bằng active config hiện có",
    "Không thay đổi Bridge/capture, Function engine, sale cadence hay recovery ownership",
)

_OPTIONAL_FEATURES_KEY = "auto_multi_dev_optional_features"
_DEFAULT_OPTIONAL_FEATURES = {
    "pirate_chest_enabled": False,
    "feed_mill_enabled": False,
    "warehouse_upgrade_enabled": False,
    "warehouse_upgrade_mode": "warehouse_1",
    "warehouse_upgrade_interval_hours": 2,
    "warehouse_upgrade_allow_diamond_slot_delete": False,
}


def _normalize_optional_features(raw) -> dict[str, object]:
    current = raw if isinstance(raw, dict) else {}
    mode = str(current.get("warehouse_upgrade_mode", "warehouse_1"))
    if mode not in {"warehouse_1", "warehouse_2", "both", "max"}:
        mode = "warehouse_1"
    try:
        interval = int(current.get("warehouse_upgrade_interval_hours", 2) or 2)
    except (TypeError, ValueError):
        interval = 2
    return {
        "pirate_chest_enabled": bool(
            current.get("pirate_chest_enabled", False)
        ),
        "feed_mill_enabled": bool(current.get("feed_mill_enabled", False)),
        "warehouse_upgrade_enabled": bool(
            current.get("warehouse_upgrade_enabled", False)
        ),
        "warehouse_upgrade_mode": mode,
        "warehouse_upgrade_interval_hours": max(1, min(168, interval)),
        "warehouse_upgrade_allow_diamond_slot_delete": bool(
            current.get("warehouse_upgrade_allow_diamond_slot_delete", False)
        ),
    }


def install_optional_features_integration(app_class, core) -> None:
    """Install DEV-only optional features without replacing Function selection.

    The verified Function selector remains the execution choice for AUTO Main.
    Optional features reuse the existing right-side description slot instead of
    creating another vertical row. This keeps the action/log rows visible in the
    fixed-height AUTO panel. A toggle applies to every selected profile, while
    the saved value remains per-profile and is frozen into each worker run.
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

    def _optional_profile_settings(self, profile_id: str) -> dict[str, object]:
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
        chest_enabled = bool(self.auto_multi_dev_pirate_chest_enabled.get())
        feed_enabled = bool(self.auto_multi_dev_feed_mill_enabled.get())
        for profile_id in profile_ids:
            # Only update the inline toggles. Preserve every account's own
            # warehouse mode and interval.
            saved = dict(self._optional_profile_settings(profile_id))
            saved["pirate_chest_enabled"] = chest_enabled
            saved["feed_mill_enabled"] = feed_enabled
            self.settings.setdefault(_OPTIONAL_FEATURES_KEY, {})[profile_id] = saved
        core.save_settings(self.settings)
        self.note.set(
            "AUTO MULTI DEV • Tùy chọn Mở rương hải tặc="
            + ("BẬT" if chest_enabled else "TẮT")
            + " • Sx cám="
            + ("BẬT" if feed_enabled else "TẮT")
            + f" • áp dụng {len(profile_ids)} tài khoản"
            + (" • cám sau Function+sale • chu kỳ 35 phút" if feed_enabled else "")
        )

    def _refresh_optional_features(self) -> None:
        if not hasattr(self, "auto_multi_dev_pirate_chest_enabled"):
            return
        self._optional_features_refreshing = True
        try:
            profile_ids = self._optional_target_profile_ids()
            chest_enabled = False
            feed_enabled = False
            if profile_ids:
                chest_enabled = all(
                    bool(
                        self._optional_profile_settings(profile_id)[
                            "pirate_chest_enabled"
                        ]
                    )
                    for profile_id in profile_ids
                )
                feed_enabled = all(
                    bool(
                        self._optional_profile_settings(profile_id)[
                            "feed_mill_enabled"
                        ]
                    )
                    for profile_id in profile_ids
                )
            warehouse_enabled = bool(profile_ids) and all(
                bool(
                    self._optional_profile_settings(profile_id)[
                        "warehouse_upgrade_enabled"
                    ]
                )
                for profile_id in profile_ids
            )
            self.auto_multi_dev_pirate_chest_enabled.set(chest_enabled)
            self.auto_multi_dev_feed_mill_enabled.set(feed_enabled)
            warehouse_button = getattr(
                self, "auto_multi_dev_quick_warehouse_button", None
            )
            if warehouse_button is not None:
                warehouse_button.configure(
                    text="✓ Nâng kho" if warehouse_enabled else "Nâng kho"
                )
            for name in (
                "auto_multi_dev_pirate_chest_button",
                "auto_multi_dev_feed_mill_button",
                "auto_multi_dev_quick_warehouse_button",
            ):
                button = getattr(self, name, None)
                if button is not None:
                    button.configure(
                        state="normal" if profile_ids else "disabled",
                        cursor="hand2" if profile_ids else "arrow",
                    )
        finally:
            self._optional_features_refreshing = False

    def _open_warehouse_upgrade_panel(self) -> None:
        profile_ids = self._optional_target_profile_ids()
        if not profile_ids:
            core.messagebox.showinfo(core.APP_NAME, "Hãy chọn ít nhất một tài khoản.")
            return

        saved = self._optional_profile_settings(profile_ids[0])
        window = core.tk.Toplevel(self)
        window.title("Cấu hình Nâng kho")
        window.transient(self)
        try:
            window.grab_set()
        except Exception:
            pass

        # Keep this optional-feature dialog visually identical to the main
        # AUTO MULTI DEV configuration window: same header/body split, theme
        # styles, LabelFrame sections, spacing and action-button ordering.
        header = core.ttk.Frame(
            window, padding=(16, 13, 16, 8), style="Detail.TFrame"
        )
        header.pack(fill="x")
        core.ttk.Label(
            header,
            text="CẤU HÌNH NÂNG KHO",
            style="Section.TLabel",
        ).pack(anchor="w")
        core.ttk.Label(
            header,
            text=(
                f"Áp dụng cho {len(profile_ids)} tài khoản đã chọn • "
                "chạy sau lượt bán VP"
            ),
            style="AutoValue.TLabel",
            anchor="w",
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        body = core.ttk.Frame(
            window, padding=(16, 4, 16, 12), style="Detail.TFrame"
        )
        body.pack(fill="both", expand=True)

        enabled = core.tk.BooleanVar(
            value=bool(saved.get("warehouse_upgrade_enabled", False))
        )
        mode = core.tk.StringVar(
            value=str(saved.get("warehouse_upgrade_mode", "warehouse_1"))
        )
        interval = core.tk.IntVar(
            value=int(saved.get("warehouse_upgrade_interval_hours", 2))
        )
        allow_diamond_slot_delete = core.tk.BooleanVar(
            value=bool(
                saved.get("warehouse_upgrade_allow_diamond_slot_delete", False)
            )
        )

        behavior_box = core.ttk.LabelFrame(
            body,
            text="HOẠT ĐỘNG",
            padding=(12, 10),
            style="Auto.TLabelframe",
        )
        behavior_box.pack(fill="x")

        core.ttk.Checkbutton(
            behavior_box,
            text="Bật tự động nâng và cân bằng kho",
            variable=enabled,
        ).pack(anchor="w")

        mode_box = core.ttk.LabelFrame(
            body,
            text="CHẾ ĐỘ XỬ LÝ",
            padding=(12, 10),
            style="Auto.TLabelframe",
        )
        mode_box.pack(fill="x", pady=(12, 0))
        mode_box.columnconfigure(0, weight=1)
        mode_box.columnconfigure(1, weight=1)
        choices = (
            ("Nâng kho 1", "warehouse_1"),
            ("Nâng kho 2", "warehouse_2"),
            ("Nâng cả 2", "both"),
            ("Max kho", "max"),
        )
        for index, (label, value) in enumerate(choices):
            core.ttk.Radiobutton(
                mode_box, text=label, value=value, variable=mode,
            ).grid(
                row=index // 2,
                column=index % 2,
                sticky="w",
                padx=(0 if index % 2 == 0 else 24, 8),
                pady=6,
            )

        schedule_box = core.ttk.LabelFrame(
            body,
            text="LỊCH CHẠY",
            padding=(12, 10),
            style="Auto.TLabelframe",
        )
        schedule_box.pack(fill="x", pady=(12, 0))
        schedule_box.columnconfigure(1, weight=1)
        core.ttk.Label(
            schedule_box, text="Chu kỳ kiểm tra", style="AutoValue.TLabel",
        ).grid(row=0, column=0, sticky="w", padx=(0, 8), pady=6)
        core.ttk.Spinbox(
            schedule_box, from_=1, to=168, width=14, textvariable=interval,
        ).grid(row=0, column=1, sticky="w", pady=6)
        core.ttk.Label(
            schedule_box, text="giờ", style="AutoValue.TLabel",
        ).grid(row=0, column=2, sticky="w", padx=(6, 0), pady=6)

        core.ttk.Label(
            schedule_box,
            text=(
                "Kho 1: giữ/cân bằng Gỗ, Gạch, Sơn đỏ.  "
                "Kho 2: giữ/cân bằng Đinh, Sơn vàng, Đá.\n"
                "Nâng cả 2: giữ toàn bộ.  Max kho: bán toàn bộ nguyên liệu nâng kho."
            ),
            style="AutoValue.TLabel",
            justify="left",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))

        diamond_box = core.ttk.LabelFrame(
            body,
            text="Ô TRỐNG QUẦY BÁN",
            padding=(12, 10),
            style="Auto.TLabelframe",
        )
        diamond_box.pack(fill="x", pady=(12, 0))

        core.ttk.Checkbutton(
            diamond_box,
            text="Cho phép dùng 1 KC xóa VP khi quầy không có ô trống",
            variable=allow_diamond_slot_delete,
        ).pack(anchor="w")
        core.ttk.Label(
            diamond_box,
            text=(
                "Không bật: chỉ dùng ô trống có sẵn; nếu quầy đầy, AUTO thoát "
                "Nâng kho và bắt đầu lại Function."
            ),
            style="AutoValue.TLabel",
            justify="left",
            wraplength=520,
        ).pack(anchor="w", pady=(4, 0))

        def close_panel() -> None:
            try:
                window.grab_release()
            except core.tk.TclError:
                pass
            window.destroy()

        def save_and_close() -> None:
            try:
                hours = int(interval.get())
            except (TypeError, ValueError, core.tk.TclError):
                hours = 0
            selected_mode = str(mode.get())
            if selected_mode not in {"warehouse_1", "warehouse_2", "both", "max"}:
                core.messagebox.showerror(core.APP_NAME, "Chế độ Nâng kho không hợp lệ.")
                return
            if not 1 <= hours <= 168:
                core.messagebox.showerror(
                    core.APP_NAME, "Thời gian kiểm tra phải trong khoảng 1..168 giờ."
                )
                return
            value = {
                "warehouse_upgrade_enabled": bool(enabled.get()),
                "warehouse_upgrade_mode": selected_mode,
                "warehouse_upgrade_interval_hours": hours,
                "warehouse_upgrade_allow_diamond_slot_delete": bool(
                    allow_diamond_slot_delete.get()
                ),
            }
            for profile_id in profile_ids:
                current = self._optional_profile_settings(profile_id)
                current.update(value)
                self.settings.setdefault(_OPTIONAL_FEATURES_KEY, {})[profile_id] = current
            core.save_settings(self.settings)
            self._refresh_optional_features()
            self.note.set(
                f"AUTO MULTI DEV • Nâng kho={'BẬT' if enabled.get() else 'TẮT'} • "
                f"mode={selected_mode} • {hours} giờ • áp dụng {len(profile_ids)} tài khoản"
            )
            close_panel()

        def reset_defaults() -> None:
            enabled.set(False)
            mode.set("warehouse_1")
            interval.set(2)
            allow_diamond_slot_delete.set(False)

        actions = core.ttk.Frame(body, style="Detail.TFrame")
        actions.pack(fill="x", pady=(14, 0))
        core.ttk.Button(
            actions,
            text="Lưu cấu hình",
            style="AutoStart.TButton",
            command=save_and_close,
        ).pack(side="left", padx=(0, 8))
        core.ttk.Button(
            actions,
            text="Mặc định",
            style="Action.TButton",
            command=reset_defaults,
        ).pack(side="left", padx=(0, 8))
        core.ttk.Button(
            actions,
            text="Đóng",
            style="Action.TButton",
            command=close_panel,
        ).pack(side="left")

        window.protocol("WM_DELETE_WINDOW", close_panel)
        window.focus_set()
        placer = getattr(self, "_place_auto_child_window", None)
        if callable(placer):
            placer(
                window,
                preferred_width=700,
                preferred_height=600,
                min_width=590,
                min_height=500,
            )
        else:
            window.geometry("700x600")
            window.minsize(590, 500)

    def _install_optional_features_in_control_slot(self) -> None:
        function_button = getattr(self, "auto_multi_dev_function_button", None)
        if function_button is None:
            return

        # The Function button lives inside column 0 of the five-column controls.
        # Reuse column 4 (the old long description box) so controls stay one row
        # tall and the action/log rows below are never pushed out of view.
        function_box = function_button.master
        controls = function_box.master
        option_box = None
        for child in tuple(controls.winfo_children()):
            try:
                info = child.grid_info()
            except Exception:
                continue
            if int(info.get("row", -1)) == 0 and int(info.get("column", -1)) == 4:
                option_box = child
                break

        if option_box is None:
            # Fail closed on layout discovery: never destroy Function controls.
            self.note.set(
                "AUTO MULTI DEV • chưa tìm thấy ô Tùy chọn an toàn; giữ nguyên UI hiện tại"
            )
            return

        for child in tuple(option_box.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass

        self.auto_multi_dev_optional_features_slot = option_box
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

        self.auto_multi_dev_feed_mill_enabled = core.tk.BooleanVar(value=False)
        self.auto_multi_dev_feed_mill_button = self._make_toggle_button(
            option_box,
            "Sx cám",
            self.auto_multi_dev_feed_mill_enabled,
            self._save_optional_features,
        )
        self.auto_multi_dev_feed_mill_button.configure(
            anchor="center", padx=9, pady=6
        )
        self.auto_multi_dev_feed_mill_button.pack(fill="x", pady=(4, 0))

        core.ttk.Label(
            option_box,
            text="Rương: sau sale đầu/20 phút • Cám: sau Function+sale/35 phút",
            style="AutoValue.TLabel",
            anchor="w",
            justify="left",
            wraplength=300,
        ).pack(fill="x", pady=(4, 0))

    def build_auto_panel(self) -> None:
        original_build_auto_panel(self)
        self._optional_features_refreshing = False
        self._optional_features_run_snapshot: dict[str, dict[str, bool]] = {}
        self._install_optional_features_in_control_slot()
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
            chest_enabled = bool(snapshot.get("pirate_chest_enabled", False))
            feed_enabled = bool(snapshot.get("feed_mill_enabled", False))
            warehouse_enabled = bool(snapshot.get("warehouse_upgrade_enabled", False))
            warehouse_mode = str(snapshot.get("warehouse_upgrade_mode", "warehouse_1"))
            warehouse_hours = int(snapshot.get("warehouse_upgrade_interval_hours", 2))
            warehouse_allow_diamond = bool(
                snapshot.get("warehouse_upgrade_allow_diamond_slot_delete", False)
            )
            pending = getattr(self, "_auto_main_pending_config", None)
            if isinstance(pending, dict):
                config = pending.get(profile_id)
                if isinstance(config, dict):
                    config["pirate_chest_enabled"] = chest_enabled
                    config["feed_mill_enabled"] = feed_enabled
                    config["warehouse_upgrade_enabled"] = warehouse_enabled
                    config["warehouse_upgrade_mode"] = warehouse_mode
                    config["warehouse_upgrade_interval_hours"] = warehouse_hours
                    config["warehouse_upgrade_allow_diamond_slot_delete"] = (
                        warehouse_allow_diamond
                    )
            active = getattr(self, "_auto_main_active_config", None)
            if isinstance(active, dict):
                config = active.get(profile_id)
                if isinstance(config, dict):
                    config["pirate_chest_enabled"] = chest_enabled
                    config["feed_mill_enabled"] = feed_enabled
                    config["warehouse_upgrade_enabled"] = warehouse_enabled
                    config["warehouse_upgrade_mode"] = warehouse_mode
                    config["warehouse_upgrade_interval_hours"] = warehouse_hours
                    config["warehouse_upgrade_allow_diamond_slot_delete"] = (
                        warehouse_allow_diamond
                    )
        return original_run_clean_main_thread(self, *args, **kwargs)

    app_class._build_auto_panel = build_auto_panel
    app_class._refresh_auto_multi_dev_profile_settings = refresh_profile_settings
    app_class._start_configured_auto_main = start_configured_auto_main
    app_class._run_clean_main_thread = run_clean_main_thread
    app_class._optional_target_profile_ids = _optional_target_profile_ids
    app_class._optional_profile_settings = _optional_profile_settings
    app_class._save_optional_features = _save_optional_features
    app_class._refresh_optional_features = _refresh_optional_features
    app_class._install_optional_features_in_control_slot = (
        _install_optional_features_in_control_slot
    )
    app_class._open_warehouse_upgrade_panel = _open_warehouse_upgrade_panel
    app_class._kvtm_optional_features_installed = True
    print(
        "[KVTM DEV] Optional Features READY • Function selector=PRESERVED • "
        "layout=single-row • logs=PRESERVED • #1 Mở rương hải tặc • "
        "#2 Sx cám • multi-select=READY • per-profile • default=OFF • "
        "safe-boundary=rương20m+cám35m",
        flush=True,
    )
