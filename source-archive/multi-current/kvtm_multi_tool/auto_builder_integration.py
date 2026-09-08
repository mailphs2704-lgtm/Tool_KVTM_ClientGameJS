from __future__ import annotations

import json
from pathlib import Path

from auto_builder_ui import install_auto_builder_tab


__all__ = ["install_auto_builder_integration"]
FILE_FUNCTIONS = (
    "Gắn Builder UI sau khi panel Multi DEV gốc được tạo",
    "Đưa plan Builder vào đúng worker run bằng marker riêng trong work-dir",
    "Khởi chạy Builder qua lifecycle/ownership hiện có của AUTO MULTI DEV",
    "Thêm nút DEV test riêng Sửa máy bắt đầu ngay tại panel sản xuất VP đang mở",
    "Hiển thị kết quả Builder mà không thay đổi handler AUTO chính",
)


def install_auto_builder_integration(app_class, core) -> None:
    """Add Builder to MultiDevApp through narrow wrappers around DEV-only hooks.

    This deliberately avoids editing ``kvtm_multi.py`` and avoids duplicating
    ClientJS lifecycle/CAPTURE3 ownership. The normal DEV launcher still creates
    the worker, logs, stop relay and busy gates. Builder only drops an explicit
    plan marker into that unique run's work directory before the worker starts.
    """
    if getattr(app_class, "_kvtm_auto_builder_installed", False):
        return

    original_build = app_class._build_auto_panel
    original_run_thread = app_class._run_clean_main_thread
    original_finish = app_class._finish_clean_main

    def build_auto_panel(self) -> None:
        original_build(self)
        self._auto_builder_pending_plans: dict[str, dict] = {}
        install_auto_builder_tab(self, core)

        # DEV-only one-click test. The operator must already have the production
        # VP panel open in ClientJS. No GameSession/production/Function prefix is
        # injected; the generated Builder plan contains only machine_repair_test.
        clean_actions = self.auto_multi_dev_stop_button.master
        self.auto_multi_dev_machine_repair_test_button = core.ttk.Button(
            clean_actions,
            text="🛠 TEST Sửa máy",
            width=17,
            style="AutoStart.TButton",
            command=self._start_machine_repair_test,
        )
        self.auto_multi_dev_machine_repair_test_button.pack(
            side="left", padx=(0, 8), before=self.auto_multi_dev_stop_button
        )

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

    def start_machine_repair_test(self) -> None:
        """Run only repair UI actions; current ClientJS panel is the precondition."""
        plan = {
            "version": 1,
            "kind": "plan",
            "name": "TEST Sửa máy từ panel VP đang mở",
            "saved_functions": {},
            "steps": [
                {
                    "id": "machine-repair-test",
                    "type": "machine_repair_test",
                },
                {
                    "id": "machine-repair-pass",
                    "type": "finish_pass",
                },
            ],
        }
        self.note.set(
            "TEST Sửa máy: giữ ClientJS tại panel sản xuất VP đang mở rồi chạy nút test"
        )
        self._start_auto_builder_plan(plan)

    app_class._build_auto_panel = build_auto_panel
    app_class._run_clean_main_thread = run_clean_main_thread
    app_class._finish_clean_main = finish_clean_main
    app_class._start_auto_builder_plan = start_auto_builder_plan
    app_class._start_machine_repair_test = start_machine_repair_test
    app_class._kvtm_auto_builder_installed = True
