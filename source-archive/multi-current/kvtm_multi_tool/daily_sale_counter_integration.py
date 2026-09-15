from __future__ import annotations

"""Multi DEV account-detail integration for persistent daily AUTO counters."""


_REFRESH_MS = 1000
_GAME_DAILY_SALE_LIMIT = 1000


def install_daily_sale_counter_integration(app_class, core) -> None:
    if getattr(app_class, "_kvtm_daily_sale_counter_installed", False):
        return

    # Imported only after the component package has been made available by the
    # resident runtime bootstrap.
    from kvtm_automation.daily_pirate_chest_counter import (
        read_daily_pirate_chest_count,
    )
    from kvtm_automation.daily_sale_counter import read_daily_sale_count

    original_build_auto_panel = app_class._build_auto_panel
    original_show_account_details = app_class._show_account_details

    def _find_textvariable_widget(root, variable):
        target = str(variable)
        stack = list(root.winfo_children())
        while stack:
            widget = stack.pop()
            try:
                if str(widget.cget("textvariable")) == target:
                    return widget
            except Exception:
                pass
            try:
                stack.extend(widget.winfo_children())
            except Exception:
                pass
        return None

    def _ensure_pirate_chest_detail_field(self) -> None:
        detail_vars = getattr(self, "detail_vars", {})
        if not isinstance(detail_vars, dict):
            return
        if "pirate_chests" in detail_vars:
            return
        sales_var = detail_vars.get("sales")
        if sales_var is None:
            return
        sales_widget = _find_textvariable_widget(self, sales_var)
        if sales_widget is None:
            return
        parent = sales_widget.master
        second_group_rows = []
        try:
            for widget in parent.grid_slaves():
                info = widget.grid_info()
                column = int(info.get("column", 0) or 0)
                row = int(info.get("row", 0) or 0)
                if column >= 2:
                    second_group_rows.append(row)
        except Exception:
            second_group_rows = []
        row = max(second_group_rows, default=-1) + 1
        value = core.tk.StringVar(value="—")
        detail_vars["pirate_chests"] = value
        core.ttk.Label(
            parent,
            text="RƯƠNG HẢI TẶC",
            style="Key.TLabel",
        ).grid(row=row, column=2, sticky="w", padx=(18, 10), pady=5)
        core.ttk.Label(
            parent,
            textvariable=value,
            style="Value.TLabel",
        ).grid(row=row, column=3, sticky="w", pady=5)

    def _apply_daily_counts_to_details(self, profile_id: str | None) -> None:
        detail_vars = getattr(self, "detail_vars", {})
        if not isinstance(detail_vars, dict):
            return
        sales_var = detail_vars.get("sales")
        chest_var = detail_vars.get("pirate_chests")

        profile_id = str(profile_id or "")
        if not profile_id:
            for variable in (sales_var, chest_var):
                if variable is not None:
                    try:
                        variable.set("—")
                    except Exception:
                        pass
            return

        if sales_var is not None:
            try:
                count = read_daily_sale_count(core.APP_DIR, profile_id)
                sales_text = f"{count} / {_GAME_DAILY_SALE_LIMIT}"
            except Exception as exc:
                sales_text = "? / 1000"
                print(
                    "[KVTM DEV] WARN daily sale counter read failed • "
                    f"profile={profile_id} • {type(exc).__name__}: {exc}",
                    flush=True,
                )
            try:
                sales_var.set(sales_text)
            except Exception:
                pass

        if chest_var is not None:
            try:
                opened = read_daily_pirate_chest_count(core.APP_DIR, profile_id)
                chest_text = f"{opened} lần hôm nay"
            except Exception as exc:
                chest_text = "? lần hôm nay"
                print(
                    "[KVTM DEV] WARN pirate chest counter read failed • "
                    f"profile={profile_id} • {type(exc).__name__}: {exc}",
                    flush=True,
                )
            try:
                chest_var.set(chest_text)
            except Exception:
                pass

    def _refresh_daily_counters(self, *, schedule: bool = True) -> None:
        profile_id = str(
            getattr(self, "_daily_sale_counter_detail_profile_id", "") or ""
        )
        if profile_id:
            self._apply_daily_counts_to_details(profile_id)

        if not schedule:
            return
        previous = getattr(self, "_daily_sale_counter_after_id", None)
        if previous is not None:
            try:
                self.after_cancel(previous)
            except Exception:
                pass
        try:
            self._daily_sale_counter_after_id = self.after(
                _REFRESH_MS,
                lambda: self._refresh_daily_sale_counter(schedule=True),
            )
        except Exception:
            self._daily_sale_counter_after_id = None

    def show_account_details(self, profile_id: str | None) -> None:
        result = original_show_account_details(self, profile_id)
        self._daily_sale_counter_detail_profile_id = str(profile_id or "")
        self._apply_daily_counts_to_details(profile_id)
        return result

    def build_auto_panel_with_daily_counters(self) -> None:
        original_build_auto_panel(self)
        self._ensure_pirate_chest_detail_field()
        if not getattr(self, "_daily_sale_counter_refresh_started", False):
            self._daily_sale_counter_refresh_started = True
            self.after_idle(
                lambda: self._refresh_daily_sale_counter(schedule=True)
            )

    app_class._build_auto_panel = build_auto_panel_with_daily_counters
    app_class._show_account_details = show_account_details
    app_class._ensure_pirate_chest_detail_field = _ensure_pirate_chest_detail_field
    app_class._apply_daily_sale_count_to_details = _apply_daily_counts_to_details
    app_class._apply_daily_counts_to_details = _apply_daily_counts_to_details
    app_class._refresh_daily_sale_counter = _refresh_daily_counters
    app_class._kvtm_daily_sale_counter_installed = True

    print(
        "[KVTM DEV] Daily counters READY • sale=one posted VP x10 slot = one turn • "
        "pirate_chest=OPENED only • per-profile persistent • "
        "ClientJS/tool restart preserved • local-midnight reset • "
        "UI=LƯỢT BÁN AUTO+RƯƠNG HẢI TẶC",
        flush=True,
    )
