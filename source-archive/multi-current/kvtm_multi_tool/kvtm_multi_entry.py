from __future__ import annotations

import ctypes
import json
import os
import subprocess
import threading
import time

import kvtm_multi as core


CLEAR_STALL_REQUIRED_VIEWS = 4
CLEAR_STALL_VERIFIED_FRIEND_MAX = 7
CLEAR_STALL_RESALE_STORAGE_MAX = 5


class MultiApp(core.MultiApp):
    """Production entrypoint with a strict per-profile Dọn quầy lifecycle."""

    def _build_auto_panel(self) -> None:
        super()._build_auto_panel()
        self._clear_stall_probe_workers = {}
        self._clear_stall_probe_starting = set()
        self._clear_stall_probe_terminal = {}
        self._normalize_clear_stall_controls()

        action_row = self.auto_clear_stall_start_button.master
        self.auto_clear_stall_probe_button = core.ttk.Button(
            action_row,
            text="✓ Kiểm tra Dọn quầy",
            style="Action.TButton",
            command=self._start_clear_stall_probe,
        )
        self.auto_clear_stall_probe_button.pack(side="left", padx=(8, 0))

    def _normalize_clear_stall_controls(self) -> None:
        """Translate historical UI names/ranges to the clean workflow contract."""
        if hasattr(self, "auto_clear_stall_friend_spin"):
            self.auto_clear_stall_friend_spin.configure(
                from_=1, to=CLEAR_STALL_VERIFIED_FRIEND_MAX
            )
        if hasattr(self, "auto_clear_stall_stall_spin"):
            self.auto_clear_stall_stall_spin.configure(
                from_=1, to=CLEAR_STALL_RESALE_STORAGE_MAX
            )
        if hasattr(self, "auto_clear_stall_pages_spin"):
            self.auto_clear_stall_pages_spin.configure(
                from_=CLEAR_STALL_REQUIRED_VIEWS,
                to=CLEAR_STALL_REQUIRED_VIEWS,
            )

        # Core keeps backward-compatible widget names. Only visible labels are
        # translated here; settings/CLI migration remains lossless.
        try:
            body = self.auto_clear_stall_start_button.master.master
            replacements = {
                "Quầy:": "Kho VP:",
                "Quét tối đa:": "Quét quầy:",
                "trang": "4 view / 20 ô",
            }
            for widget in body.winfo_children():
                try:
                    text = str(widget.cget("text"))
                except Exception:
                    continue
                if text in replacements:
                    widget.configure(text=replacements[text])
        except Exception:
            pass

    def _clear_stall_busy(self) -> bool:
        """Only one Dọn quầy/probe clone may own ClientJS automation at a time."""
        if tuple(self._clear_stall_starting):
            return True
        if tuple(getattr(self, "_clear_stall_probe_starting", ())):
            return True
        for worker in tuple(self._clear_stall_workers.values()):
            try:
                if worker.poll() is None:
                    return True
            except Exception:
                continue
        for worker in tuple(
            getattr(self, "_clear_stall_probe_workers", {}).values()
        ):
            try:
                if worker.poll() is None:
                    return True
            except Exception:
                continue
        return False

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

        proc = self.processes.get(profile_id)
        if proc and proc.poll() is None:
            proc.terminate()

        if profile_id == self._active_profile_id:
            self._refresh_clear_stall_panel()
        self.after(500, self.refresh)

    def _save_clear_stall_config(self) -> None:
        """Persist the clean Dọn quầy contract through the legacy settings schema."""
        if getattr(self, "_clear_stall_refreshing", False):
            return
        try:
            friend = max(
                1,
                min(
                    CLEAR_STALL_VERIFIED_FRIEND_MAX,
                    int(self.auto_clear_stall_friend.get()),
                ),
            )
        except Exception:
            friend = 1
        try:
            storage = max(
                1,
                min(
                    CLEAR_STALL_RESALE_STORAGE_MAX,
                    int(self.auto_clear_stall_stall.get()),
                ),
            )
        except Exception:
            storage = 2

        self.auto_clear_stall_friend.set(friend)
        self.auto_clear_stall_stall.set(storage)
        self.auto_clear_stall_pages.set(CLEAR_STALL_REQUIRED_VIEWS)
        self.auto_clear_stall_close.set(True)

        # Core persists the historical keys; immediately overwrite the fields
        # whose old validation had different semantics/ranges.
        super()._save_clear_stall_config()
        profile_id, profile = self._clear_stall_profile()
        if not profile_id or not profile:
            return
        job = self._clear_stall_job(profile_id)
        job["target_friend_ordinal"] = friend
        job["target_stall_id"] = storage
        job["max_scan_pages"] = CLEAR_STALL_REQUIRED_VIEWS
        job["close_client_after_run"] = True
        self.settings.setdefault("clear_stall_jobs", {})[profile_id] = job
        core.save_settings(self.settings)

    def _start_clear_stall(
        self, profile_id: str | None = None, scheduled: bool = False
    ) -> None:
        target_id = profile_id
        if target_id is None:
            target_id, _profile = self._clear_stall_profile()

        if target_id and self._clear_stall_busy():
            if not scheduled and hasattr(self, "auto_clear_stall_status"):
                self.auto_clear_stall_status.set(
                    "Đang có clone khác Dọn quầy/kiểm tra • tài khoản này chờ lượt"
                )
            return

        super()._start_clear_stall(profile_id, scheduled)
        if not target_id:
            return

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

    def _start_clear_stall_probe(self) -> None:
        """Open the selected clone and scan four stall views without transactions."""
        self._save_clear_stall_config()
        profile_id, profile = self._clear_stall_profile()
        if not profile_id or not profile:
            core.messagebox.showinfo(core.APP_NAME, "Hãy chọn một tài khoản clone.")
            return
        if self._clear_stall_busy():
            self.auto_clear_stall_status.set(
                "Đang có phiên Dọn quầy/kiểm tra khác • chờ phiên đó kết thúc"
            )
            return
        auto_worker = self._auto_workers.get(profile_id)
        if auto_worker and auto_worker.poll() is None:
            core.messagebox.showinfo(
                core.APP_NAME,
                "Hãy dừng AUTO chính của clone trước khi kiểm tra Dọn quầy.",
            )
            return

        self._clear_stall_probe_starting.add(profile_id)
        try:
            proc = self.processes.get(profile_id)
            if not proc or proc.poll() is not None:
                self._launch(profile)
                proc = self.processes.get(profile_id)
            if not proc or proc.poll() is not None:
                raise RuntimeError("Không mở được ClientJS của clone")
        except Exception as exc:
            self._clear_stall_probe_starting.discard(profile_id)
            self.auto_clear_stall_status.set(f"Lỗi mở clone để kiểm tra: {exc}")
            core.messagebox.showerror(core.APP_NAME, str(exc))
            return

        self.auto_clear_stall_status.set(
            "Kiểm tra chỉ đọc • đang chờ ClientJS sẵn sàng"
        )
        self.after(
            2500,
            lambda pid=profile_id: self._launch_clear_stall_probe_worker(pid),
        )

    def _launch_clear_stall_probe_worker(self, profile_id: str) -> None:
        profile = next(
            (p for p in self.profiles if p.get("id") == profile_id), None
        )
        proc = self.processes.get(profile_id)
        if not profile or not proc or proc.poll() is not None:
            self._clear_stall_probe_starting.discard(profile_id)
            self.auto_clear_stall_status.set(
                "Kiểm tra lỗi: clone đã đóng trước khi worker khởi động"
            )
            return

        job = self._clear_stall_job(profile_id)
        package_root = core.TOOL_DIR.parent
        auto_root = package_root / "AUTO_PRO"
        worker_file = (
            package_root / "components" / "clientjs-auto" /
            "worker" / "clear_stall_live_probe.py"
        )
        if not worker_file.is_file():
            self._clear_stall_probe_starting.discard(profile_id)
            self.auto_clear_stall_status.set(f"Thiếu probe worker: {worker_file}")
            return

        friend = max(
            1,
            min(
                CLEAR_STALL_VERIFIED_FRIEND_MAX,
                int(job.get("target_friend_ordinal", 1) or 1),
            ),
        )
        storage = max(
            1,
            min(
                CLEAR_STALL_RESALE_STORAGE_MAX,
                int(job.get("target_stall_id", 2) or 2),
            ),
        )
        run_id = time.strftime("%Y%m%d-%H%M%S")
        work_dir = core.APP_DIR / "clear-stall-probe" / profile_id / run_id
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            worker = subprocess.Popen(
                [
                    core.sys.executable,
                    str(worker_file),
                    "--auto-root", str(auto_root),
                    "--pid", str(proc.pid),
                    "--profile-id", str(profile_id),
                    "--profile-name", str(profile.get("name") or profile_id),
                    "--friend-ordinal", str(friend),
                    "--stall-id", str(storage),
                    "--work-dir", str(work_dir),
                ],
                cwd=str(auto_root),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=flags,
            )
        except Exception as exc:
            self._clear_stall_probe_starting.discard(profile_id)
            self.auto_clear_stall_status.set(f"Lỗi mở probe worker: {exc}")
            return

        self._clear_stall_probe_workers[profile_id] = worker
        self._clear_stall_probe_terminal.pop(profile_id, None)
        self._clear_stall_probe_starting.discard(profile_id)
        self.auto_clear_stall_status.set(
            f"Kiểm tra chỉ đọc • Nhà bạn {friend} • Kho VP {storage}"
        )
        threading.Thread(
            target=self._read_clear_stall_probe_worker,
            args=(profile_id, worker),
            daemon=True,
        ).start()

    def _read_clear_stall_probe_worker(self, profile_id: str, worker) -> None:
        if worker.stdout:
            for line in worker.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    payload = {"event": "probe_progress", "message": line}
                payload["profile_id"] = profile_id
                self.after(
                    0,
                    lambda data=dict(payload):
                    self._handle_clear_stall_probe_event(data),
                )
        try:
            returncode = worker.wait(timeout=1.0)
        except Exception:
            returncode = -1
        self.after(
            0,
            lambda: self._handle_clear_stall_probe_event({
                "event": "probe_exit",
                "profile_id": profile_id,
                "returncode": returncode,
            }),
        )

    def _close_probe_clone(self, profile_id: str) -> None:
        proc = self.processes.get(profile_id)
        try:
            if proc and proc.poll() is None:
                proc.terminate()
        except OSError:
            pass
        self.after(500, self.refresh)

    def _handle_clear_stall_probe_event(self, payload: dict) -> None:
        profile_id = str(payload.get("profile_id") or "")
        event = str(payload.get("event") or "")
        message = str(payload.get("message") or "")

        if event == "probe_boot":
            stage = str(payload.get("stage") or "")
            labels = {
                "clean-runtime-start": "Kiểm tra: nạp runtime sạch",
                "raw-window-connecting": "Kiểm tra: kết nối cửa sổ ClientJS",
                "clientjs-engine-connecting": "Kiểm tra: kết nối engine ClientJS",
                "waiting-main-screen": "Kiểm tra: xử popup/màn hình farm",
                "navigating-friend": "Kiểm tra: đang sang nhà bạn",
                "opening-friend-stall": "Kiểm tra: đang mở quầy 20 ô",
            }
            if profile_id == self._active_profile_id:
                self.auto_clear_stall_status.set(labels.get(stage, f"Kiểm tra: {stage}"))
            return

        if event == "probe_progress":
            if profile_id == self._active_profile_id and message:
                self.auto_clear_stall_status.set(message)
            if message:
                self.note.set(message)
            return

        if event == "probe_ok":
            self._clear_stall_probe_terminal[profile_id] = "ok"
            occupied = int(payload.get("occupied_new_total") or 0)
            report = str(payload.get("report") or "")
            if profile_id == self._active_profile_id:
                self.auto_clear_stall_status.set(
                    f"Kiểm tra PASS • {occupied}/20 ô có VP • đã lưu ảnh/report"
                )
            self.note.set(f"Dọn quầy probe PASS: {report}")
            self._close_probe_clone(profile_id)
            return

        if event == "probe_stopped":
            self._clear_stall_probe_terminal[profile_id] = "stopped"
            if profile_id == self._active_profile_id:
                self.auto_clear_stall_status.set("Đã dừng kiểm tra Dọn quầy")
            self._close_probe_clone(profile_id)
            return

        if event == "probe_error":
            self._clear_stall_probe_terminal[profile_id] = "error"
            error = str(payload.get("error") or "Lỗi probe không xác định")
            report = str(payload.get("report") or "")
            if profile_id == self._active_profile_id:
                self.auto_clear_stall_status.set("Kiểm tra Dọn quầy lỗi")
                core.messagebox.showerror(
                    core.APP_NAME,
                    f"Kiểm tra Dọn quầy lỗi:\n{error}\n\nReport: {report}",
                )
            self._close_probe_clone(profile_id)
            return

        if event == "probe_exit":
            returncode = int(payload.get("returncode") or 0)
            self._clear_stall_probe_workers.pop(profile_id, None)
            terminal = self._clear_stall_probe_terminal.pop(profile_id, None)
            if returncode and terminal not in {"error", "stopped"}:
                if profile_id == self._active_profile_id:
                    self.auto_clear_stall_status.set(
                        f"Probe worker dừng bất ngờ (mã {returncode})"
                    )
                self._close_probe_clone(profile_id)
            self._refresh_clear_stall_panel()

    def _poll_clear_stall_schedule(self) -> None:
        """Run due clone jobs FIFO, never concurrently."""
        if self._bridge_stop.is_set():
            return
        if not self._clear_stall_busy():
            now = time.time()
            jobs = self.settings.get("clear_stall_jobs", {})
            due_jobs = []
            if isinstance(jobs, dict):
                for profile_id, job in tuple(jobs.items()):
                    if not isinstance(job, dict) or not job.get("enabled", False):
                        continue
                    try:
                        due = float(job.get("next_run_at", 0) or 0)
                    except (TypeError, ValueError):
                        due = 0
                    if due > 0 and due <= now:
                        due_jobs.append((due, str(profile_id)))
            for _due, profile_id in sorted(due_jobs):
                self._start_clear_stall(profile_id, scheduled=True)
                if self._clear_stall_busy():
                    break
        self.after(1000, self._poll_clear_stall_schedule)

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

        if event == "worker_boot":
            stage = str(payload.get("stage") or "")
            labels = {
                "process_started": "Worker Dọn quầy sạch đã khởi động",
                "clean_runtime_importing": "Đang nạp runtime Python sạch",
                "clientjs_engine_connecting": "Đang kết nối engine ClientJS",
                "clientjs_engine_ready": "Đã kết nối engine ClientJS",
            }
            self._set_clear_stall_checkpoint(
                profile_id, labels.get(stage, f"Khởi tạo: {stage}")
            )
            return

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
                "deferred": bool(payload.get("deferred", False)),
                "inventory_full": bool(payload.get("inventory_full", False)),
                "source_empty": bool(payload.get("source_empty", False)),
                "state": str(payload.get("state") or "COMPLETED"),
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

    def _stop_clear_stall(self) -> None:
        profile_id, _profile = self._clear_stall_profile()
        profile_id = str(profile_id or "")
        if profile_id in getattr(self, "_clear_stall_probe_starting", set()):
            self._clear_stall_probe_starting.discard(profile_id)
            self._close_probe_clone(profile_id)
            self.auto_clear_stall_status.set("Đã hủy kiểm tra trước khi worker chạy")
            return
        probe = getattr(self, "_clear_stall_probe_workers", {}).get(profile_id)
        if probe and probe.poll() is None:
            try:
                if probe.stdin:
                    probe.stdin.write(json.dumps({"command": "stop"}) + "\n")
                    probe.stdin.flush()
                self.auto_clear_stall_status.set("Đang dừng kiểm tra Dọn quầy")
            except (OSError, ValueError):
                probe.terminate()
                self._close_probe_clone(profile_id)
            return
        super()._stop_clear_stall()

    def _refresh_clear_stall_panel(self) -> None:
        super()._refresh_clear_stall_panel()
        if not hasattr(self, "auto_clear_stall_status"):
            return

        self._normalize_clear_stall_controls()
        self._clear_stall_refreshing = True
        try:
            if hasattr(self, "auto_clear_stall_close"):
                self.auto_clear_stall_close.set(True)
            if hasattr(self, "auto_clear_stall_close_button"):
                self.auto_clear_stall_close_button.configure(state="disabled")
            if hasattr(self, "auto_clear_stall_pages"):
                self.auto_clear_stall_pages.set(CLEAR_STALL_REQUIRED_VIEWS)
            if hasattr(self, "auto_clear_stall_pages_spin"):
                self.auto_clear_stall_pages_spin.configure(state="disabled")

            profile_id, profile = self._clear_stall_profile()
            if profile_id and profile:
                job = self._clear_stall_job(profile_id)
                try:
                    friend = max(
                        1,
                        min(
                            CLEAR_STALL_VERIFIED_FRIEND_MAX,
                            int(job.get("target_friend_ordinal", 1) or 1),
                        ),
                    )
                except Exception:
                    friend = 1
                try:
                    storage = max(
                        1,
                        min(
                            CLEAR_STALL_RESALE_STORAGE_MAX,
                            int(job.get("target_stall_id", 2) or 2),
                        ),
                    )
                except Exception:
                    storage = 2
                self.auto_clear_stall_friend.set(friend)
                self.auto_clear_stall_stall.set(storage)
        finally:
            self._clear_stall_refreshing = False

        profile_id, profile = self._clear_stall_profile()
        main_auto_busy = False
        if profile_id:
            auto_worker = self._auto_workers.get(profile_id)
            main_auto_busy = bool(auto_worker and auto_worker.poll() is None)
        if hasattr(self, "auto_clear_stall_probe_button"):
            self.auto_clear_stall_probe_button.configure(
                state=(
                    "normal"
                    if profile and not main_auto_busy and not self._clear_stall_busy()
                    else "disabled"
                )
            )

        if not profile_id or not profile:
            return
        job = self._clear_stall_job(profile_id)
        changed = False
        normalized_friend = max(
            1,
            min(
                CLEAR_STALL_VERIFIED_FRIEND_MAX,
                int(job.get("target_friend_ordinal", 1) or 1),
            ),
        )
        normalized_storage = max(
            1,
            min(
                CLEAR_STALL_RESALE_STORAGE_MAX,
                int(job.get("target_stall_id", 2) or 2),
            ),
        )
        if int(job.get("target_friend_ordinal", normalized_friend) or normalized_friend) != normalized_friend:
            job["target_friend_ordinal"] = normalized_friend
            changed = True
        if int(job.get("target_stall_id", normalized_storage) or normalized_storage) != normalized_storage:
            job["target_stall_id"] = normalized_storage
            changed = True
        if int(job.get("max_scan_pages", CLEAR_STALL_REQUIRED_VIEWS) or CLEAR_STALL_REQUIRED_VIEWS) != CLEAR_STALL_REQUIRED_VIEWS:
            job["max_scan_pages"] = CLEAR_STALL_REQUIRED_VIEWS
            changed = True
        if not bool(job.get("close_client_after_run", False)):
            job["close_client_after_run"] = True
            changed = True
        if changed:
            self.settings.setdefault("clear_stall_jobs", {})[profile_id] = job
            core.save_settings(self.settings)

        worker = self._clear_stall_workers.get(profile_id)
        if worker and worker.poll() is None:
            return
        probe = getattr(self, "_clear_stall_probe_workers", {}).get(profile_id)
        if probe and probe.poll() is None:
            return
        if profile_id in self._clear_stall_starting:
            return
        if profile_id in getattr(self, "_clear_stall_probe_starting", set()):
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
        """Stop Dọn quầy/probe workers and only the clones owned by those runs."""
        active_profiles = set(self._clear_stall_workers)
        active_profiles.update(self._clear_stall_starting)
        active_profiles.update(
            getattr(self, "_clear_stall_probe_workers", {}).keys()
        )
        active_profiles.update(
            getattr(self, "_clear_stall_probe_starting", set())
        )

        all_workers = list(self._clear_stall_workers.values())
        all_workers.extend(
            getattr(self, "_clear_stall_probe_workers", {}).values()
        )
        for worker in all_workers:
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
        getattr(self, "_clear_stall_probe_workers", {}).clear()
        getattr(self, "_clear_stall_probe_starting", set()).clear()
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
