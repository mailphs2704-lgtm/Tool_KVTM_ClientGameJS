from __future__ import annotations

"""Multi DEV UI for the persistent per-profile daily VP sale counter."""


_REFRESH_MS = 1000


def install_daily_sale_counter_integration(app_class, core) -> None:
    if getattr(app_class, "_kvtm_daily_sale_counter_installed", False):
        return

    # This module is imported by kvtm_multi_owned_host before the resident host
    # has inserted components/clientjs-auto into sys.path. Resolve the shared
    # counter reader only when integrations are installed, after image/runtime
    # bootstrap has already made the component package importable.
    from kvtm_automation.daily_sale_counter import read_daily_sale_count

    original_build_auto_panel = app_class._build_auto_panel

    def _daily_sale_counter_profile_id(self) -> str | None:
        resolver = getattr(self, "_auto_multi_dev_profile_id", None)
        if callable(resolver):
            try:
                profile_id = resolver()
            except Exception:
                profile_id = None
            if profile_id:
                return str(profile_id)
        try:
            selected = list(map(str, self.selected_ids()))
        except Exception:
            selected = []
        return selected[0] if len(selected) == 1 else None

    def _refresh_daily_sale_counter(self, *, schedule: bool = True) -> None:
        variable = getattr(self, "auto_multi_dev_daily_sale_count", None)
        if variable is not None:
            profile_id = self._daily_sale_counter_profile_id()
            if profile_id:
                try:
                    count = read_daily_sale_count(core.APP_DIR, profile_id)
                    text = f"Lần bán hôm nay: {count}"
                except Exception as exc:
                    text = "Lần bán hôm nay: ?"
                    print(
                        "[KVTM DEV] WARN daily sale counter read failed • "
                        f"profile={profile_id} • {type(exc).__name__}: {exc}",
                        flush=True,
                    )
            else:
                text = "Lần bán hôm nay: —"
            try:
                variable.set(text)
            except Exception:
                pass

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

    def build_auto_panel_with_daily_sale_counter(self) -> None:
        original_build_auto_panel(self)

        sale_spin = getattr(self, "auto_multi_dev_sale_every_spin", None)
        if sale_spin is None:
            print(
                "[KVTM DEV] WARN daily sale counter UI skipped • sale spinbox missing",
                flush=True,
            )
            return

        sale_box = sale_spin.master
        self.auto_multi_dev_daily_sale_count = core.tk.StringVar(
            master=self,
            value="Lần bán hôm nay: 0",
        )
        self.auto_multi_dev_daily_sale_count_label = core.ttk.Label(
            sale_box,
            textvariable=self.auto_multi_dev_daily_sale_count,
            style="AutoValue.TLabel",
            anchor="w",
        )
        self.auto_multi_dev_daily_sale_count_label.pack(
            anchor="w",
            pady=(6, 0),
        )
        self.after_idle(
            lambda: self._refresh_daily_sale_counter(schedule=True)
        )

    app_class._build_auto_panel = build_auto_panel_with_daily_sale_counter
    app_class._daily_sale_counter_profile_id = _daily_sale_counter_profile_id
    app_class._refresh_daily_sale_counter = _refresh_daily_sale_counter
    app_class._kvtm_daily_sale_counter_installed = True

    print(
        "[KVTM DEV] Daily sale counter READY • per-profile persistent • "
        "ClientJS/tool restart preserved • local-midnight reset • UI=Auto Main sale box",
        flush=True,
    )
