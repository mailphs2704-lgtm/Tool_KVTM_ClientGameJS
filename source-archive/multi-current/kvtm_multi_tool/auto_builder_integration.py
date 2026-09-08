from __future__ import annotations

import json
from pathlib import Path

from auto_builder_ui import install_auto_builder_tab


__all__ = ["install_auto_builder_integration"]
FILE_FUNCTIONS = (
    "Gắn Builder UI sau khi panel Multi DEV gốc được tạo",
    "Đưa plan Builder vào đúng worker run bằng marker riêng trong work-dir",
    "Khởi chạy Builder qua lifecycle/ownership hiện có của AUTO MULTI DEV",
    "Ẩn tab Thiết kế cũ khỏi hàng chức năng của Multi DEV",
    "Đưa Log hành động + Log chi tiết xuống hàng riêng dưới nút AUTO MULTI DEV",
    "Hiển thị kết quả Builder mà không thay đổi handler AUTO chính",
)


def install_auto_builder_integration(app_class, core) -> None:
    """Add Builder to MultiDevApp through narrow wrappers around DEV-only hooks.

    This deliberately avoids duplicating ClientJS lifecycle/CAPTURE3 ownership.
    The normal DEV launcher still creates the worker, logs, stop relay and busy
    gates. Builder only drops an explicit plan marker into that unique run's work
    directory before the worker starts.
    """
    if getattr(app_class, "_kvtm_auto_builder_installed", False):
        return

    original_build = app_class._build_auto_panel
    original_run_thread = app_class._run_clean_main_thread
    original_finish = app_class._finish_clean_main

    def _apply_requested_dev_layout(self) -> None:
        # The real legacy Designer key in kvtm_multi.py is clear_stall_designer.
        # Keep the widget registered for compatibility with _show_auto_tab, but
        # remove it from the visible tab strip only.
        tab_buttons = getattr(self, "auto_tab_buttons", {})
        designer_button = tab_buttons.get("clear_stall_designer")
        if designer_button is not None:
            try:
                designer_button.pack_forget()
            except Exception:
                pass

        start_button = getattr(self, "auto_multi_dev_start_button", None)
        action_log = getattr(self, "auto_multi_dev_action_log_button", None)
        detail_log = getattr(self, "auto_multi_dev_detail_log_button", None)
        multi_dev_tab = getattr(self, "auto_feature_tabs", {}).get("multi_dev")
        if (
            start_button is None
            or action_log is None
            or detail_log is None
            or multi_dev_tab is None
        ):
            return

        # All five original buttons are children of one clean_actions frame.
        # Never pack_forget that frame: doing so hides Start/Speed/Stop too.
        # Hide only the two old log buttons, then recreate the same commands in a
        # dedicated row directly below clean_actions. Tk widgets cannot be safely
        # reparented after construction.
        clean_actions = start_button.master
        if action_log.master is not clean_actions or detail_log.master is not clean_actions:
            return
        try:
            action_log.pack_forget()
            detail_log.pack_forget()

            log_row = core.ttk.Frame(multi_dev_tab, style="Detail.TFrame")
            log_row.pack(fill="x", padx=8, pady=(6, 0), after=clean_actions)

            self.auto_multi_dev_action_log_button = core.ttk.Button(
                log_row,
                text="≡ Log hành động",
                width=18,
                style="Action.TButton",
                command=lambda: self._open_clean_main_log("action"),
            )
            self.auto_multi_dev_action_log_button.pack(side="left", padx=(0, 8))

            self.auto_multi_dev_detail_log_button = core.ttk.Button(
                log_row,
                text="⌕ Log chi tiết",
                width=18,
                style="Action.TButton",
                command=lambda: self._open_clean_main_log("detail"),
            )
            self.auto_multi_dev_detail_log_button.pack(side="left")

            refresh_tabs = getattr(self, "_refresh_auto_tab_scroll", None)
            if callable(refresh_tabs):
                self.after_idle(refresh_tabs)
        except Exception:
            # Fail visibly safe: restore the original log buttons if creating the
            # second row fails. Start/Speed/Stop were never removed.
            try:
                action_log.pack(side="left", padx=(0, 8))
                detail_log.pack(side="left")
                self.auto_multi_dev_action_log_button = action_log
                self.auto_multi_dev_detail_log_button = detail_log
            except Exception:
                pass

    def build_auto_panel(self) -> None:
        original_build(self)
        self._auto_builder_pending_plans: dict[str, dict] = {}
        _apply_requested_dev_layout(self)
        install_auto_builder_tab(self, core)

    def run_clean_main_thread(self, *args, **kwargs) -> None:
        profile_id = str(args[0] if args else kwargs.get("profile_id") or "")
        work_dir = Path(args[3] if len(args) > 3 else kwargs["work_dir"])
        plan = self._auto_builder_pending_plans.pop(profile_id, None)
        if plan is not None:
            work_dir.mkdir(parents=True, exist_ok=True)
            marker = work_dir / "auto-builder-plan.json"
            marker.write_text(
                json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        return original_run_thread(self, *args, **kwargs)

    def finish_clean_main(self, profile_id: str, outcome: str, payload: dict) -> None:
        if outcome != "auto_builder_ready":
            return original_finish(self, profile_id, outcome, payload)

        self._clean_main_threads.pop(profile_id, None)
        self._clean_main_workers.pop(profile_id, None)
        self._clean_main_stop_events.pop(profile_id, None)
        completed = int(payload.get("completed_steps", 0) or 0)
        total = int(payload.get("total_steps", 0) or 0)
        plan_name = str(payload.get("plan_name") or "AUTO tự tạo")
        outcome_text = str(payload.get("outcome") or "completed").upper()
        status = (
            f"AUTO Builder {outcome_text} • {plan_name} • bước {completed}/{total}"
        )
        self.auto_multi_dev_status.set(status)
        self.note.set(status)
        controller = getattr(self, "auto_builder_ui", None)
        if controller is not None and controller.status_var is not None:
            controller.status_var.set(status)

    def start_auto_builder_plan(self, plan: dict) -> None:
        selected = list(map(str, self.selected_ids()))
        if not selected:
            core.messagebox.showinfo(
                core.APP_NAME, "Hãy chọn ít nhất một tài khoản để chạy AUTO Builder."
            )
            return
        # JSON roundtrip freezes one serializable snapshot per launch. The editor
        # may continue changing afterwards without mutating a running worker plan.
        try:
            frozen = json.loads(json.dumps(plan, ensure_ascii=False))
        except (TypeError, ValueError) as exc:
            core.messagebox.showerror(
                core.APP_NAME, f"Plan AUTO Builder không thể chạy:\n{exc}"
            )
            return
        if not isinstance(frozen, dict) or not isinstance(frozen.get("steps"), list):
            core.messagebox.showerror(core.APP_NAME, "Plan AUTO Builder không hợp lệ.")
            return

        previous_threads = {
            profile_id: self._clean_main_threads.get(profile_id)
            for profile_id in selected
        }
        for profile_id in selected:
            self._auto_builder_pending_plans[profile_id] = frozen

        self._start_clean_auto_session()

        launched = 0
        for profile_id in selected:
            current = self._clean_main_threads.get(profile_id)
            if current is None or current is previous_threads[profile_id]:
                self._auto_builder_pending_plans.pop(profile_id, None)
                continue
            launched += 1
        if launched:
            name = str(frozen.get("name") or "AUTO tự tạo")
            status = f"AUTO Builder • đang chạy {name} • {launched} tài khoản"
            self.auto_multi_dev_status.set(status)
            self.note.set(status)
            controller = getattr(self, "auto_builder_ui", None)
            if controller is not None and controller.status_var is not None:
                controller.status_var.set(status)

    app_class._build_auto_panel = build_auto_panel
    app_class._run_clean_main_thread = run_clean_main_thread
    app_class._finish_clean_main = finish_clean_main
    app_class._start_auto_builder_plan = start_auto_builder_plan
    app_class._kvtm_auto_builder_installed = True
