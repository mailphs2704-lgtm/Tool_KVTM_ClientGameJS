from __future__ import annotations

import ctypes
import json
import os
import time

import kvtm_multi as core


class MultiApp(core.MultiApp):
    """Production entrypoint with a strict per-profile Dọn quầy lifecycle."""

    def _rearm_clear_stall_after_failure(
        self,
        profile_id: str,
        checkpoint: str,
        result: dict | None = None,
    ) -> None:
        """Close a failed clone and re-arm only its own schedule."""
        job = self._clear_stall_job(profile_id)
        interval = max(5, int(job.get("interval_minutes", 65) or 65))
        now = time.time()
        job["close_client_after_run"] = True
        job["last_checkpoint"] = str(checkpoint)
        job["last_result"] = result or {
            "ok": False,
            "error": str(checkpoint),
            "finished_at": now,
        }
        job["next_run_at"] = (
            now + interval * 60 if job.get("enabled", False) else 0
        )
        self.settings.setdefault("clear_stall_jobs", {})[profile_id] = job
        core.save_settings(self.settings)
        self._clear_stall_starting.discard(profile_id)

        # A failed scheduled run must never leave its clone running unattended.
        proc = self.processes.get(profile_id)
        if proc and proc.poll() is None:
            proc.terminate()

        if profile_id == self._active_profile_id:
            self._refresh_clear_stall_panel()
        self.after(500, self.refresh)

    def _save_clear_stall_config(self) -> None:
        """Dọn quầy owns the clone lifecycle, so closing after every run is mandatory."""
        if hasattr(self, "auto_clear_stall_close"):
            self.auto_clear_stall_close.set(True)
        super()._save_clear_stall_config()
        profile_id, profile = self._clear_stall_profile()
        if not profile_id or not profile:
            return
        job = self._clear_stall_job(profile_id)
        if job and not bool(job.get("close_client_after_run", False)):
            job["close_client_after_run"] = True
            self.settings.setdefault("clear_stall_jobs", {})[profile_id] = job
            core.save_settings(self.settings)

    def _start_clear_stall(
        self, profile_id: str | None = None, scheduled: bool = False
    ) -> None:
        target_id = profile_id
        if target_id is None:
            target_id, _profile = self._clear_stall_profile()

        super()._start_clear_stall(profile_id, scheduled)
        if not target_id:
            return

        # The core reports an immediate launch error through its checkpoint.
        # Re-arm here so a single launch failure cannot permanently zero a timer.
        job = self._clear_stall_job(target_id)
        checkpoint = str(job.get("last_checkpoint") or "")
        if checkpoint.startswith("Lỗi mở clone:"):
            try:
                next_run = float(job.get("next_run_at", 0) or 0)
            except (TypeError, ValueError):
                next_run = 0
            if next_run <= 0 and target_id not in self._clear_stall_starting:
                self._rearm_clear_stall_after_failure(
                    target_id,
                    "Lỗi mở clone • sẽ thử lại theo chu kỳ",
                    {
                        "ok": False,
                        "error": checkpoint,
                        "finished_at": time.time(),
                    },
                )

    def _launch_clear_stall_worker(self, profile_id: str) -> None:
        super()._launch_clear_stall_worker(profile_id)
        worker = self._clear_stall_workers.get(profile_id)
        if worker and worker.poll() is None:
            return

        job = self._clear_stall_job(profile_id)
        checkpoint = str(job.get("last_checkpoint") or "")
        failure_prefixes = (
            "Lỗi: clone đã đóng",
            "Thiếu worker:",
            "Lỗi mở Dọn quầy worker Python:",
        )
        if not checkpoint.startswith(failure_prefixes):
            return
        try:
            next_run = float(job.get("next_run_at", 0) or 0)
        except (TypeError, ValueError):
            next_run = 0
        if next_run <= 0:
            self._rearm_clear_stall_after_failure(
                profile_id,
                "Dọn quầy chưa khởi động • sẽ thử lại theo chu kỳ",
                {
                    "ok": False,
                    "error": checkpoint,
                    "finished_at": time.time(),
                },
            )

    def _handle_clear_stall_worker_event(self, payload: dict) -> None:
        profile_id = str(payload.get("profile_id") or "")
        event = str(payload.get("event") or "")

        if event == "worker_stopped":
            self._rearm_clear_stall_after_failure(
                profile_id,
                "Đã dừng an toàn • chờ chu kỳ tiếp theo",
                {
                    "ok": False,
                    "stopped": True,
                    "finished_at": time.time(),
                },
            )
            return

        if event == "worker_error":
            super()._handle_clear_stall_worker_event(payload)
            job = self._clear_stall_job(profile_id)
            result = job.get("last_result")
            self._rearm_clear_stall_after_failure(
                profile_id,
                "Dọn quầy lỗi • sẽ thử lại theo chu kỳ",
                result if isinstance(result, dict) else None,
            )
            return

        if event == "worker_finished":
            # Let the core persist the next-run timestamp first, then enforce
            # the Dọn quầy ownership rule regardless of any legacy saved toggle.
            super()._handle_clear_stall_worker_event(payload)
            job = self._clear_stall_job(profile_id)
            bought = int(payload.get("bought") or 0)
            sold = int(payload.get("sold") or 0)
            retained = int(payload.get("retained") or 0)
            finished_at = time.time()
            job["close_client_after_run"] = True
            job["last_checkpoint"] = (
                f"Hoàn thành • mua {bought} • bán {sold} • giữ lại {retained}"
            )
            job["last_result"] = {
                "ok": True,
                "finished_at": finished_at,
                "bought": bought,
                "sold": sold,
                "retained": retained,
            }
            self.settings.setdefault("clear_stall_jobs", {})[profile_id] = job
            core.save_settings(self.settings)

            proc = self.processes.get(profile_id)
            if proc and proc.poll() is None:
                proc.terminate()

            if profile_id == self._active_profile_id:
                self._refresh_clear_stall_panel()
            self.after(500, self.refresh)
            return

        if event == "worker_exit":
            returncode = int(payload.get("returncode") or 0)
            super()._handle_clear_stall_worker_event(payload)
            if returncode == 0:
                return
            job = self._clear_stall_job(profile_id)
            result = job.get("last_result")
            if isinstance(result, dict) and result.get("ok") is False:
                return
            self._rearm_clear_stall_after_failure(
                profile_id,
                f"Worker Dọn quầy dừng bất ngờ (mã {returncode})",
                {
                    "ok": False,
                    "error": f"worker exit {returncode}",
                    "finished_at": time.time(),
                },
            )
            return

        super()._handle_clear_stall_worker_event(payload)

    def _refresh_clear_stall_panel(self) -> None:
        super()._refresh_clear_stall_panel()
        if not hasattr(self, "auto_clear_stall_status"):
            return

        # This is a workflow invariant, not a user preference. Keep the legacy
        # control visible for layout compatibility but lock it to ON.
        if hasattr(self, "auto_clear_stall_close"):
            self.auto_clear_stall_close.set(True)
        if hasattr(self, "auto_clear_stall_close_button"):
            self.auto_clear_stall_close_button.configure(state="disabled")

        profile_id, profile = self._clear_stall_profile()
        if not profile_id or not profile:
            return
        job = self._clear_stall_job(profile_id)
        if job and not bool(job.get("close_client_after_run", False)):
            job["close_client_after_run"] = True
            self.settings.setdefault("clear_stall_jobs", {})[profile_id] = job
            core.save_settings(self.settings)

        worker = self._clear_stall_workers.get(profile_id)
        if worker and worker.poll() is None:
            return
        if profile_id in self._clear_stall_starting:
            return
        if not bool(job.get("enabled", False)):
            return
        try:
            next_run = float(job.get("next_run_at", 0) or 0)
        except (TypeError, ValueError):
            next_run = 0
        if next_run > time.time():
            next_text = time.strftime("%d/%m %H:%M:%S", time.localtime(next_run))
            self.auto_clear_stall_status.set(
                f"Đang chờ lịch • Lần tiếp theo {next_text}"
            )

    def _on_close(self) -> None:
        """Stop Dọn quầy workers and only the clones owned by those runs."""
        active_profiles = set(self._clear_stall_workers)
        active_profiles.update(self._clear_stall_starting)
        for worker in list(self._clear_stall_workers.values()):
            try:
                if worker.poll() is not None:
                    continue
                if worker.stdin:
                    worker.stdin.write(
                        json.dumps({"command": "stop"}, separators=(",", ":"))
                        + "\n"
                    )
                    worker.stdin.flush()
                worker.terminate()
            except (OSError, ValueError):
                pass
        self._clear_stall_workers.clear()
        self._clear_stall_starting.clear()
        for profile_id in active_profiles:
            proc = self.processes.get(profile_id)
            try:
                if proc and proc.poll() is None:
                    proc.terminate()
            except OSError:
                pass
        super()._on_close()


def main() -> int:
    if os.name != "nt":
        print("KVTM Multi chỉ chạy trên Windows.")
        return 1
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
    MultiApp().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
