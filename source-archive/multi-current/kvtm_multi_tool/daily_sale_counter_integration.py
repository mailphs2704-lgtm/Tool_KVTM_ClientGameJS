from __future__ import annotations

"""Multi DEV detail-panel integration for the persistent daily VP sale count."""


_REFRESH_MS = 1000
_GAME_DAILY_SALE_LIMIT = 1000


def install_daily_sale_counter_integration(app_class, core) -> None:
    if getattr(app_class, "_kvtm_daily_sale_counter_installed", False):
        return

    # This module is imported by kvtm_multi_owned_host before the resident host
    # has inserted components/clientjs-auto into sys.path. Resolve the shared
    # counter reader only when integrations are installed, after image/runtime
    # bootstrap has already made the component package importable.
    from kvtm_automation.daily_sale_counter import read_daily_sale_count

    original_build_auto_panel = app_class._build_auto_panel
    original_show_account_details = app_class._show_account_details

    def _apply_daily_sale_count_to_details(self, profile_id: str | None) -> None:
        detail_vars = getattr(self, "detail_vars", {})
        sales_var = detail_vars.get("sales") if isinstance(detail_vars, dict) else None
        if sales_var is None:
            return

        profile_id = str(profile_id or "")
        if not profile_id:
            try:
                sales_var.set("—")
            except Exception:
                pass
            return

        try:
            count = read_daily_sale_count(core.APP_DIR, profile_id)
            text = f"{count} / {_GAME_DAILY_SALE_LIMIT}"
        except Exception as exc:
            text = "? / 1000"
            print(
                "[KVTM DEV] WARN daily sale counter read failed • "
                f"profile={profile_id} • {type(exc).__name__}: {exc}",
                flush=True,
            )
        try:
            sales_var.set(text)
        except Exception:
            pass

    def _refresh_daily_sale_counter(self, *, schedule: bool = True) -> None:
        profile_id = str(
            getattr(self, "_daily_sale_counter_detail_profile_id", "") or ""
        )
        if profile_id:
            self._apply_daily_sale_count_to_details(profile_id)

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
        self._apply_daily_sale_count_to_details(profile_id)
        return result

    def build_auto_panel_with_daily_sale_counter(self) -> None:
        original_build_auto_panel(self)
        if not getattr(self, "_daily_sale_counter_refresh_started", False):
            self._daily_sale_counter_refresh_started = True
            self.after_idle(
                lambda: self._refresh_daily_sale_counter(schedule=True)
            )

    app_class._build_auto_panel = build_auto_panel_with_daily_sale_counter
    app_class._show_account_details = show_account_details
    app_class._apply_daily_sale_count_to_details = _apply_daily_sale_count_to_details
    app_class._refresh_daily_sale_counter = _refresh_daily_sale_counter
    app_class._kvtm_daily_sale_counter_installed = True

    print(
        "[KVTM DEV] Daily sale counter READY • semantics=one posted VP x10 slot = one turn • "
        "per-profile persistent • ClientJS/tool restart preserved • "
        "local-midnight reset • UI=LƯỢT BÁN AUTO detail field",
        flush=True,
    )
