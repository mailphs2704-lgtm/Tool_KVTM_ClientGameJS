from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback

import kvtm_multi as core
import kvtm_multi_entry as production


_RESIDENT_RUNTIME_TIMEOUT = 15.0
_CLEAR_STALL_MAX_CONCURRENCY = 2


def _runtime_roots() -> tuple[Path, Path, Path]:
    package_root = core.TOOL_DIR.parent
    component_root = package_root / "components" / "clientjs-auto"
    worker_root = component_root / "worker"
    auto_root = package_root / "AUTO_PRO"
    return component_root, worker_root, auto_root


def _install_runtime_paths() -> tuple[Path, Path, Path]:
    component_root, worker_root, auto_root = _runtime_roots()
    for path in (component_root, worker_root):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)
    return component_root, worker_root, auto_root


def _prewarm_resident_image_runtime() -> None:
    """Load native image libraries once in the process that will own Multi DEV."""

    _component_root, _worker_root, auto_root = _install_runtime_paths()
    from kvtm_automation.runtime.bootstrap import install_binary_dependencies

    print("[KVTM DEV] Loading resident Dọn quầy image runtime in Multi process...", flush=True)
    started = time.monotonic()
    done = threading.Event()
    failure: list[BaseException] = []

    def log(message: str) -> None:
        print(f"[CLEAN RUNTIME] {message}", flush=True)

    def load() -> None:
        try:
            install_binary_dependencies(auto_root, logger=log)
        except BaseException as exc:
            failure.append(exc)
        finally:
            done.set()

    thread = threading.Thread(
        target=load,
        name="kvtm-dev-resident-image-runtime",
        daemon=True,
    )
    thread.start()

    next_heartbeat = 2.0
    while not done.wait(0.10):
        elapsed = time.monotonic() - started
        if elapsed >= _RESIDENT_RUNTIME_TIMEOUT:
            raise RuntimeError(
                "Resident Dọn quầy image runtime không sẵn sàng sau "
                f"{_RESIDENT_RUNTIME_TIMEOUT:.0f}s"
            )
        if elapsed >= next_heartbeat:
            print(f"[CLEAN RUNTIME] resident import still running... {elapsed:.0f}s", flush=True)
            next_heartbeat += 2.0

    if failure:
        raise failure[0]

    import cv2
    import numpy
    from PIL import Image  # noqa: F401

    elapsed = time.monotonic() - started
    print(
        "[CLEAN RUNTIME] RESIDENT READY "
        f"after {elapsed:.2f}s | cv2={cv2.__version__} | numpy={numpy.__version__}",
        flush=True,
    )


class MultiDevApp(production.MultiApp):
    """DEV shell with one resident image runtime and an in-process safe probe."""

    def _build_auto_panel(self) -> None:
        # Base panel refreshes during construction, so resident probe state must
        # exist before super() creates/enables the Gate button.
        self._clear_stall_probe_log_consoles: dict[str, subprocess.Popen] = {}
        self._clear_stall_probe_log_paths: dict[str, tuple[Path, Path]] = {}
        self._dev_probe_threads: dict[str, threading.Thread] = {}
        self._dev_probe_stop_events: dict[str, threading.Event] = {}
        self._clean_main_threads: dict[str, threading.Thread] = {}
        self._clean_main_workers: dict[str, subprocess.Popen] = {}
        self._clean_main_stop_events: dict[str, threading.Event] = {}
        self._clean_main_log_paths: dict[str, tuple[Path, Path]] = {}
        self._clean_vp_probe_requested: set[str] = set()
        self._clean_vp_sale_requested: set[str] = set()
        self._clean_rose_plant_requested: set[str] = set()
        self._clean_function_3_step_1_requested: set[str] = set()
        self._clear_stall_probe_starting: set[str] = set()
        self._clear_stall_probe_terminal: dict[str, str] = {}
        self._clear_stall_gate2_profiles: set[str] = set()
        self._clear_stall_gate3_profiles: set[str] = set()
        self._clear_stall_gate4_profiles: set[str] = set()
        self._clear_stall_gate5_profiles: set[str] = set()
        self._clear_stall_scheduled_profiles: set[str] = set()
        super()._build_auto_panel()
        # Production entry adds its historical check button after resolving the
        # compatibility anchor. DEV exposes only the single full-action button.
        legacy_probe = getattr(self, "auto_clear_stall_probe_button", None)
        full_action = self.auto_clear_stall_full_resale_probe_button
        if legacy_probe is not None and legacy_probe is not full_action:
            legacy_probe.destroy()
        self.auto_clear_stall_probe_button = full_action
        self.auto_clear_stall_start_button = full_action
        clean_actions = self.auto_multi_dev_stop_button.master
        clean_tab = clean_actions.master

        # Put DEV-only Step tests and logs on a dedicated lower row. The old
        # floor-6 demo is removed; this button owns only Function 3 Step 1.
        self.auto_multi_dev_action_log_button.destroy()
        self.auto_multi_dev_detail_log_button.destroy()
        test_actions = core.ttk.Frame(clean_tab, style="Detail.TFrame")
        test_actions.pack(fill="x", padx=8, pady=(6, 0))

        self.auto_multi_dev_function_3_step_1_button = core.ttk.Button(
            test_actions,
            text="▶ Test Function 3 - Step 1",
            width=28,
            style="Action.TButton",
            command=self._start_clean_function_3_step_1,
        )
        self.auto_multi_dev_function_3_step_1_button.pack(
            side="left", padx=(0, 8)
        )
        self.auto_multi_dev_action_log_button = core.ttk.Button(
            test_actions, text="≡ Log hành động", width=18,
            style="Action.TButton",
            command=lambda: self._open_clean_main_log("action"),
        )
        self.auto_multi_dev_action_log_button.pack(side="left", padx=(0, 8))
        self.auto_multi_dev_detail_log_button = core.ttk.Button(
            test_actions, text="⌕ Log chi tiết", width=18,
            style="Action.TButton",
            command=lambda: self._open_clean_main_log("detail"),
        )
        self.auto_multi_dev_detail_log_button.pack(side="left")
        self._refresh_clear_stall_panel()

    def _clean_main_alive(self, profile_id: str | None) -> bool:
        if not profile_id:
            return False
        thread = self._clean_main_threads.get(str(profile_id))
        return bool(thread and thread.is_alive())

    def _start_clean_vp_recognition_probe(self) -> None:
        selected = list(map(str, self.selected_ids()))
        if not selected:
            core.messagebox.showinfo(
                core.APP_NAME, "Hãy chọn ít nhất một tài khoản để kiểm tra VP."
            )
            return
        self._clean_vp_probe_requested.update(selected)
        self._start_clean_auto_session()

    def _start_clean_vp_sale(self) -> None:
        selected = list(map(str, self.selected_ids()))
        if not selected:
            core.messagebox.showinfo(
                core.APP_NAME, "Hãy chọn ít nhất một tài khoản để bán VP."
            )
            return
        self._clean_vp_sale_requested.update(selected)
        self._start_clean_auto_session()

    def _start_clean_rose_plant(self) -> None:
        selected = list(map(str, self.selected_ids()))
        if not selected:
            core.messagebox.showinfo(
                core.APP_NAME, "Hãy chọn ít nhất một tài khoản để trồng Hoa hồng."
            )
            return
        self._clean_rose_plant_requested.update(selected)
        self._start_clean_auto_session()

    def _start_clean_function_3_step_1(self) -> None:
        """Run only operator-defined Function 3 Step 1 through the isolated worker."""
        selected = list(map(str, self.selected_ids()))
        if not selected:
            core.messagebox.showinfo(
                core.APP_NAME, "Hãy chọn ít nhất một tài khoản để test Function 3 Step 1."
            )
            return
        self._clean_function_3_step_1_requested.update(selected)
        self._start_clean_auto_session()

    def _start_clean_auto_session(self) -> None:
        """Run clean Main on the resident image runtime already owned by DEV."""
        selected = self.selected_ids()
        if not selected:
            core.messagebox.showinfo(
                core.APP_NAME, "Hãy tích chọn ít nhất một tài khoản."
            )
            return

        try:
            self._adopt_running_clients(core.running_clients())
        except Exception as exc:
            self.note.set(f"AUTO MULTI DEV: chưa thể quét ClientJS: {exc}")

        launched = 0
        busy: list[str] = []
        failed: list[str] = []
        for profile_id in selected:
            profile_id = str(profile_id)
            profile = next(
                (item for item in self.profiles if str(item.get("id") or "") == profile_id),
                None,
            )
            name = str((profile or {}).get("name") or profile_id)
            if profile is None:
                failed.append(f"{name} (không còn profile)")
                continue
            if (
                self._clean_main_alive(profile_id)
                or self._probe_thread_alive(profile_id)
                or self._worker_alive(self._auto_workers.get(profile_id))
                or self._worker_alive(self._clear_stall_workers.get(profile_id))
            ):
                busy.append(name)
                continue

            process = self.processes.get(profile_id)
            if process is None or process.poll() is not None:
                try:
                    self._launch(profile)
                    process = self.processes.get(profile_id)
                except Exception as exc:
                    failed.append(f"{name} ({exc})")
                    continue
            if process is None or process.poll() is not None:
                failed.append(f"{name} (ClientJS không khởi động)")
                continue

            # A CAPTURE3 mapping has exactly one automation owner. Close any
            # explicit preview consumer before the isolated worker starts.
            preview = self.previews.pop(profile_id, None)
            if preview is not None:
                try:
                    preview.close()
                except Exception:
                    pass
            self._live_enabled.discard(profile_id)

            stop_event = threading.Event()
            run_id = time.strftime("%Y%m%d-%H%M%S")
            work_dir = core.APP_DIR / "auto-multi-dev" / profile_id / run_id
            _component_root, _worker_root, _auto_root = _install_runtime_paths()
            from kvtm_automation.runtime.main_log import MainLogWriter
            log_writer = MainLogWriter(work_dir)
            self._clean_main_log_paths[profile_id] = (
                log_writer.action_path, log_writer.detail_path,
            )
            log_writer.action(
                f"AUTO MULTI DEV start | profile={name} | pid={int(process.pid)}"
            )
            log_writer.detail(
                f"Runtime=isolated-worker | bridge=V3 | "
                f"profile_id={profile_id} | pid={int(process.pid)}"
            )
            thread = threading.Thread(
                target=self._run_clean_main_thread,
                args=(
                    profile_id, profile, int(process.pid), work_dir, stop_event,
                    log_writer, profile_id in self._clean_vp_probe_requested,
                    profile_id in self._clean_vp_sale_requested,
                    profile_id in self._clean_rose_plant_requested,
                    profile_id in self._clean_function_3_step_1_requested,
                    self._collect_auto_tuning(),
                ),
                name=f"kvtm-dev-clean-main-{profile_id[:8]}",
                daemon=True,
            )
            self._clean_main_stop_events[profile_id] = stop_event
            self._clean_main_threads[profile_id] = thread
            thread.start()
            self._clean_vp_probe_requested.discard(profile_id)
            self._clean_vp_sale_requested.discard(profile_id)
            self._clean_rose_plant_requested.discard(profile_id)
            self._clean_function_3_step_1_requested.discard(profile_id)
            launched += 1

        self._clean_vp_probe_requested.difference_update(selected)
        self._clean_vp_sale_requested.difference_update(selected)
        self._clean_rose_plant_requested.difference_update(selected)
        self._clean_function_3_step_1_requested.difference_update(selected)
        if launched:
            self.auto_multi_dev_status.set(
                f"AUTO MULTI DEV • đang chạy chuỗi bán → trồng • {launched} tài khoản"
            )
        if busy:
            self.note.set("AUTO MULTI DEV bỏ qua tài khoản đang bận: " + ", ".join(busy))
        if failed:
            detail = "; ".join(failed)
            self.note.set("AUTO MULTI DEV không mở được ClientJS: " + detail)
            core.messagebox.showerror(
                core.APP_NAME, "Không mở được ClientJS cho AUTO MULTI DEV:\n" + detail
            )

    def _run_clean_main_thread(
        self,
        profile_id: str,
        profile: dict,
        pid: int,
        work_dir: Path,
        stop_event: threading.Event,
        log_writer,
        run_vp_probe: bool,
        run_vp_sale: bool,
        run_rose_plant: bool,
        run_function_3_step_1: bool,
        speed_values: dict,
    ) -> None:
        """Supervise one isolated AUTO MULTI DEV worker process."""

        _component_root, worker_root, auto_root = _install_runtime_paths()
        worker_file = worker_root / "auto_multi_dev_worker.py"
        if not worker_file.is_file():
            payload = {"error": f"Thiếu worker AUTO MULTI DEV: {worker_file}"}
            self.after(
                0, lambda data=payload: self._finish_clean_main(
                    profile_id, "error", data
                )
            )
            return

        args = [
            core.sys.executable, str(worker_file),
            "--auto-root", str(auto_root),
            "--pid", str(int(pid)),
            "--profile-id", str(profile_id),
            "--profile-name", str(profile.get("name") or profile_id),
            "--profile-file", str(core.PROFILE_FILE),
            "--work-dir", str(work_dir),
            "--mode", "function-3-step-1" if run_function_3_step_1 else "main",
            "--speed-json", json.dumps(
                speed_values, ensure_ascii=True, separators=(",", ":")
            ),
            "--timeout", "180",
        ]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        terminal = False
        worker = None
        try:
            worker = subprocess.Popen(
                args,
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
            self._clean_main_workers[profile_id] = worker
            log_writer.action(
                f"AUTO MULTI DEV worker READY | worker_pid={worker.pid} | "
                "runtime=isolated | bridge=V3 | capture_owner=single-worker"
            )
            runtime_ready_event = threading.Event()
            startup_timed_out = threading.Event()

            def guard_worker_startup() -> None:
                if runtime_ready_event.wait(90.0):
                    return
                if worker.poll() is None:
                    startup_timed_out.set()
                    log_writer.action(
                        "ERROR | Worker chưa READY sau 90s • GUI cha kết thúc worker"
                    )
                    try:
                        worker.terminate()
                    except OSError:
                        pass

            threading.Thread(
                target=guard_worker_startup,
                name=f"auto-multi-dev-startup-{profile_id[:8]}",
                daemon=True,
            ).start()

            def relay_stop() -> None:
                while worker.poll() is None:
                    if not stop_event.wait(0.10):
                        continue
                    if worker.stdin:
                        try:
                            worker.stdin.write(
                                json.dumps({"command": "stop"}) + "\n"
                            )
                            worker.stdin.flush()
                        except (OSError, ValueError):
                            pass
                    return

            threading.Thread(
                target=relay_stop,
                name=f"auto-multi-dev-stop-{profile_id[:8]}",
                daemon=True,
            ).start()

            if worker.stdout:
                for raw_line in worker.stdout:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        event = {"event": "detail", "message": line}
                    kind = str(event.get("event") or "")
                    message = str(event.get("message") or "")
                    if kind == "runtime_ready":
                        runtime_ready_event.set()
                        log_writer.action(
                            "AUTO MULTI DEV runtime READY • Bridge V3 + image stack"
                        )
                        continue
                    if kind == "detail":
                        if message:
                            log_writer.detail(message)
                        continue
                    if kind in {"progress", "stage", "worker_started", "worker_stopping"}:
                        if message:
                            log_writer.action(message)
                            self.after(
                                0, lambda text=message: (
                                    self.auto_multi_dev_status.set(text),
                                    self.note.set(text),
                                )
                            )
                        elif kind == "worker_started":
                            log_writer.action(
                                "Worker V3 độc lập đã khởi động • một chủ CAPTURE3"
                            )
                        continue
                    if kind == "client_restart_requested":
                        reason = str(event.get("reason") or "")
                        log_writer.action(
                            "AUTO MULTI DEV restart SAFE đã đến hạn"
                        )
                        if reason:
                            log_writer.detail(reason)
                        self.after(
                            0, lambda: self.auto_multi_dev_status.set(
                                "AUTO MULTI DEV • đang restart đúng ClientJS"
                            )
                        )
                        continue
                    if kind == "client_pid_changed":
                        old_pid = int(event.get("old_pid") or 0)
                        new_pid = int(event.get("new_pid") or 0)
                        if new_pid <= 0:
                            raise RuntimeError(
                                "Worker báo client_pid_changed nhưng thiếu PID mới"
                            )
                        log_writer.action(
                            f"ClientJS PID changed {old_pid} -> {new_pid}"
                        )
                        self.after(
                            0,
                            lambda old=old_pid, new=new_pid:
                            self._adopt_restarted_auto_client(
                                profile_id, old, new
                            ),
                        )
                        continue
                    if kind == "client_restart_completed":
                        restart_message = message or (
                            "ClientJS restart PASS • AUTO tiếp tục"
                        )
                        log_writer.action(restart_message)
                        self.after(
                            0, lambda text=restart_message: (
                                self.auto_multi_dev_status.set(text),
                                self.note.set(text),
                            )
                        )
                        continue
                    if kind == "worker_finished":
                        terminal = True
                        outcome = str(event.pop("outcome", "auto_main_ready"))
                        self.after(
                            0, lambda data=dict(event), result_kind=outcome:
                            self._finish_clean_main(profile_id, result_kind, data)
                        )
                        break
                    if kind == "worker_stopped":
                        terminal = True
                        self.after(
                            0, lambda data=dict(event):
                            self._finish_clean_main(profile_id, "stopped", data)
                        )
                        break
                    if kind == "worker_error":
                        terminal = True
                        error = str(event.get("error") or "Lỗi worker AUTO MULTI DEV")
                        log_writer.action(f"ERROR | {error}")
                        if event.get("traceback"):
                            log_writer.detail(str(event["traceback"]))
                        self.after(
                            0, lambda data=dict(event):
                            self._finish_clean_main(profile_id, "error", data)
                        )
                        break

            returncode = worker.wait()
            if not terminal:
                payload = {
                    "error": (
                        "Runtime ảnh worker bị treo quá 90 giây; GUI cha đã dừng"
                        if startup_timed_out.is_set()
                        else (
                            "Worker AUTO MULTI DEV kết thúc không có kết quả "
                            f"(exit={returncode})"
                        )
                    )
                }
                self.after(
                    0, lambda data=payload: self._finish_clean_main(
                        profile_id, "error", data
                    )
                )
        except Exception as exc:
            payload = {"error": repr(exc), "traceback": traceback.format_exc()}
            log_writer.action(f"ERROR | {repr(exc)}")
            log_writer.detail(payload["traceback"])
            self.after(
                0, lambda data=payload: self._finish_clean_main(
                    profile_id, "error", data
                )
            )
        finally:
            self._clean_main_workers.pop(profile_id, None)
            if worker is not None and worker.poll() is None:
                try:
                    worker.terminate()
                except OSError:
                    pass

    def _adopt_restarted_auto_client(
        self, profile_id: str, old_pid: int, new_pid: int
    ) -> None:
        """Bind GUI state to the exact replacement PID reported by its worker."""
        if int(new_pid) <= 0:
            return
        current = self.processes.get(profile_id)
        current_pid = int(getattr(current, "pid", 0) or 0)
        if current_pid not in {0, int(old_pid), int(new_pid)}:
            self.note.set(
                "Bỏ qua PID restart không còn khớp profile • "
                f"đang giữ PID {current_pid}"
            )
            return
        self.processes[profile_id] = core.RunningProcessRef(int(new_pid))
        with self._bridge_lock:
            # EngineDriver emits the PID only after its V3 bridge is READY.
            self._bridged_pids.discard(int(old_pid))
            self._bridge_inflight_pids.discard(int(old_pid))
            self._bridge_ready_after.pop(int(old_pid), None)
            self._bridged_pids.add(int(new_pid))
            self._bridge_inflight_pids.discard(int(new_pid))
            self._bridge_ready_after.pop(int(new_pid), None)
        self.auto_multi_dev_status.set(
            f"AUTO MULTI DEV • ClientJS {old_pid} → {new_pid} • đang tiếp tục"
        )
        self.note.set(
            f"ClientJS đã restart: PID {old_pid} → {new_pid}; AUTO tiếp tục"
        )
        self.refresh()

    def _finish_clean_main(
        self, profile_id: str, outcome: str, payload: dict
    ) -> None:
        self._clean_main_threads.pop(profile_id, None)
        self._clean_main_workers.pop(profile_id, None)
        self._clean_main_stop_events.pop(profile_id, None)
        if outcome == "stopped":
            self.auto_multi_dev_status.set("ĐÃ DỪNG • worker AUTO MULTI DEV đã thoát an toàn")
            return
        if outcome == "function_3_step_1_finished":
            apples_1_5 = int(payload.get("apples_floor_1_to_5", 0) or 0)
            apples_6 = int(payload.get("apples_floor_6", 0) or 0)
            dried_teas = int(payload.get("dried_teas", 0) or 0)
            end_floor = int(payload.get("end_floor", 0) or 0)
            self.auto_multi_dev_status.set(
                "STEP 1 PASS • Function 3 • "
                f"Táo={apples_1_5}+{apples_6}/36 • "
                f"Trà sấy={dried_teas}/9 • đứng tại tầng {end_floor}"
            )
            return
        if outcome == "auto_main_ready":
            sold = int(payload.get("sold_listings", 0) or 0)
            gold = int(payload.get("collected_gold_slots", 0) or 0)
            planted = int(payload.get("planted_count", 0) or 0)
            produced = int(payload.get("produced_count", 0) or 0)
            juice = int(payload.get("apple_juice_count", 0) or 0)
            self.auto_multi_dev_status.set(
                "TẠM PASS 2/3 CHỨC NĂNG 1 • "
                f"bán {sold} ô • thu vàng {gold} ô • "
                f"trồng Táo {planted}/27 • Táo sấy {produced}/9 • "
                f"Nước táo {juice}/9 • còn 9 Vải vàng"
            )
            return
        if outcome == "finished":
            self.auto_multi_dev_status.set(
                "PASS • Đã vào game, đóng popup và xác nhận màn hình chính"
            )
            return
        if outcome == "sale_finished":
            sold = int(payload.get("sold_listings", 0) or 0)
            gold = int(payload.get("collected_gold_slots", 0) or 0)
            self.auto_multi_dev_status.set(
                f"PASS • Đã treo {sold} ô VP • thu vàng {gold} ô"
            )
            return
        if outcome == "rose_plant_finished":
            planted = int(payload.get("planted_count", 0) or 0)
            self.auto_multi_dev_status.set(
                f"ĐÃ GỬI LỆNH • Trồng Hoa hồng {planted}/27 • cần kiểm tra trực tiếp"
            )
            return
        if outcome == "vp_finished":
            count = int(payload.get("recognized_count", 0) or 0)
            self.auto_multi_dev_status.set(
                f"READ-ONLY PASS • Nhận diện {count}/3 VP mẫu"
            )
            return
        error = str(payload.get("error") or "Lỗi AUTO MULTI DEV")
        self.auto_multi_dev_status.set(f"LỖI • {error}")
        core.messagebox.showerror(core.APP_NAME, f"AUTO MULTI DEV lỗi:\n{error}")

    def _stop_clean_auto_session(self) -> None:
        selected = set(map(str, self.selected_ids()))
        targets = [
            (profile_id, event)
            for profile_id, event in self._clean_main_stop_events.items()
            if not selected or profile_id in selected
        ]
        for _profile_id, event in targets:
            event.set()
        self.auto_multi_dev_status.set(
            f"Đã gửi dừng an toàn • {len(targets)} worker độc lập"
            if targets else "AUTO MULTI DEV hiện không chạy"
        )

    def _poll_clear_stall_schedule(self) -> None:
        """Start due Dọn quầy cycles up to the two-client machine limit."""
        if self._bridge_stop.is_set():
            return
        now = time.time()
        jobs = self.settings.get("clear_stall_jobs", {})
        if isinstance(jobs, dict):
            due_jobs = []
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
                if self._dev_probe_blocked(profile_id):
                    job = self._clear_stall_job(profile_id)
                    waiting = "Đang xếp hàng • chờ tài khoản trước hoàn thành"
                    if job.get("last_checkpoint") != waiting:
                        self._set_clear_stall_checkpoint(profile_id, waiting)
                    continue
                self._start_scheduled_full_clear_stall(profile_id)
        self.after(1000, self._poll_clear_stall_schedule)

    def _clear_stall_profile(self) -> tuple[str | None, dict | None]:
        profile_id, profile = super()._clear_stall_profile()
        if profile_id and profile:
            return profile_id, profile

        running: list[tuple[str, dict]] = []
        for candidate in self.profiles:
            candidate_id = str(candidate.get("id") or "")
            if not candidate_id:
                continue
            proc = self.processes.get(candidate_id)
            try:
                alive = bool(proc and proc.poll() is None)
            except Exception:
                alive = False
            if alive:
                running.append((candidate_id, candidate))
        return running[0] if len(running) == 1 else (None, None)

    @staticmethod
    def _worker_alive(worker) -> bool:
        try:
            return bool(worker and worker.poll() is None)
        except Exception:
            return False

    def _probe_thread_alive(self, profile_id: str | None) -> bool:
        if not profile_id:
            return False
        thread = self._dev_probe_threads.get(profile_id)
        return bool(thread and thread.is_alive())

    def _dev_probe_blocked(self, profile_id: str | None) -> bool:
        """Allow two independent profiles while keeping each profile exclusive."""
        if not profile_id:
            return True
        profile_id = str(profile_id)
        if self._probe_thread_alive(profile_id):
            return True
        if self._clean_main_alive(profile_id):
            return True
        auto_worker = self._auto_workers.get(profile_id)
        if self._worker_alive(auto_worker):
            return True
        if profile_id in self._clear_stall_starting:
            return True
        if profile_id in getattr(self, "_clear_stall_probe_starting", ()):
            return True
        worker = self._clear_stall_workers.get(profile_id)
        if self._worker_alive(worker):
            return True

        active_profiles = {
            str(other_id)
            for other_id, thread in self._dev_probe_threads.items()
            if thread.is_alive() and str(other_id) != profile_id
        }
        active_profiles.update(
            str(other_id)
            for other_id in self._clear_stall_starting
            if str(other_id) != profile_id
        )
        active_profiles.update(
            str(other_id)
            for other_id in getattr(self, "_clear_stall_probe_starting", ())
            if str(other_id) != profile_id
        )
        active_profiles.update(
            str(other_id)
            for other_id, other_worker in self._clear_stall_workers.items()
            if str(other_id) != profile_id and self._worker_alive(other_worker)
        )
        return len(active_profiles) >= _CLEAR_STALL_MAX_CONCURRENCY

    def _start_scheduled_full_clear_stall(self, profile_id: str) -> None:
        """Open one due clone and run the same live-verified full transaction."""
        profile = next(
            (item for item in self.profiles if str(item.get("id") or "") == profile_id),
            None,
        )
        job = self._clear_stall_job(profile_id)
        if not profile or not job.get("enabled", False):
            return
        self._prepare_probe_console(profile_id, profile)
        self._clear_stall_gate3_profiles.add(profile_id)
        self._clear_stall_gate5_profiles.add(profile_id)
        self._clear_stall_scheduled_profiles.add(profile_id)
        job["next_run_at"] = 0
        job["last_checkpoint"] = "Đến lịch • đang tự mở clone"
        self.settings.setdefault("clear_stall_jobs", {})[profile_id] = job
        core.save_settings(self.settings)
        self._clear_stall_probe_starting.add(profile_id)
        try:
            proc = self.processes.get(profile_id)
            if not proc or proc.poll() is not None:
                self._launch(profile)
                proc = self.processes.get(profile_id)
            if not proc or proc.poll() is not None:
                raise RuntimeError("Không mở được ClientJS của clone đến lịch")
        except Exception as exc:
            self._clear_stall_probe_starting.discard(profile_id)
            self._clear_stall_gate3_profiles.discard(profile_id)
            self._clear_stall_gate5_profiles.discard(profile_id)
            self._clear_stall_scheduled_profiles.discard(profile_id)
            interval = max(5, int(job.get("interval_minutes", 65) or 65))
            job["next_run_at"] = time.time() + min(5, interval) * 60
            job["last_checkpoint"] = f"Lỗi tự mở clone • thử lại sau 5 phút: {exc}"
            self.settings.setdefault("clear_stall_jobs", {})[profile_id] = job
            core.save_settings(self.settings)
            self._mark_probe_console_done(profile_id, f"ERROR mở clone đến lịch: {exc}")
            return
        self._append_probe_log(profile_id, f"scheduled_clone_pid={proc.pid}")
        self.auto_clear_stall_status.set("Đến lịch • đang chờ ClientJS sẵn sàng")
        self.after(
            2500,
            lambda pid=profile_id: self._launch_clear_stall_probe_worker(pid),
        )

    def _refresh_clear_stall_panel(self) -> None:
        super()._refresh_clear_stall_panel()
        if not hasattr(self, "auto_clear_stall_full_resale_probe_button"):
            return
        profile_id, profile = self._clear_stall_profile()
        gate_state = (
            "normal"
            if profile and not self._dev_probe_blocked(profile_id)
            else "disabled"
        )
        self.auto_clear_stall_full_resale_probe_button.configure(state=gate_state)

    def _new_live_log_paths(self, profile_id: str) -> tuple[Path, Path]:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        root = core.APP_DIR / "clear-stall-probe" / profile_id / f"dev-live-{stamp}"
        root.mkdir(parents=True, exist_ok=True)
        return root / "activity.log", root / ".probe-console-done"

    def _append_probe_log(self, profile_id: str, message: str) -> None:
        paths = self._clear_stall_probe_log_paths.get(profile_id)
        if not paths:
            return
        try:
            with paths[0].open("a", encoding="utf-8", errors="replace") as stream:
                stream.write(f"[{time.strftime('%H:%M:%S')}] UI     {message}\n")
                stream.flush()
        except OSError:
            pass

    @staticmethod
    def _activity_text(payload: dict, raw_line: str) -> str:
        stamp = time.strftime("%H:%M:%S")
        event = str(payload.get("event") or "output")
        stage = str(payload.get("stage") or "")
        message = str(payload.get("message") or "")
        if event == "probe_boot" and stage:
            summary = f"STAGE  {stage}"
        elif event == "probe_progress" and message:
            summary = f"INFO   {message}"
        elif event == "probe_purchase_ok":
            transaction_gate = str(payload.get("transaction_gate") or "")
            purchase_gate = (
                "GATE 5"
                if transaction_gate == "COLLECT_GOLD_RESELL_TARGET_EXACT"
                else (
                    "GATE 4"
                    if transaction_gate == "COLLECT_GOLD_RESELL_ONE_EXACT"
                    else (
                        "GATE 3B"
                        if transaction_gate == "PURCHASE_TARGET_MULTI_HOUSE"
                        else "GATE 2"
                    )
                )
            )
            summary = (
                f"PASS   {purchase_gate} mua đúng "
                f"{int(payload.get('purchased_quantity') or 0)} VP"
            )
        elif event == "probe_resale_ok":
            sold = int(payload.get("quantity") or 0)
            fingerprint = str(payload.get("fingerprint_sha256") or "")
            gate = (
                "GATE 5"
                if str(payload.get("transaction_gate") or "")
                == "COLLECT_GOLD_RESELL_TARGET_EXACT"
                else "GATE 4"
            )
            cumulative = int(payload.get("sold_quantity") or sold)
            summary = (
                f"PASS   {gate} treo {sold} VP • tổng={cumulative} • "
                f"fingerprint={fingerprint[:12]}"
            )
        elif event == "probe_ok":
            summary = (
                "PASS   probe hoàn tất • sample_hits="
                f"{int(payload.get('sample_hits_not_unique_inventory') or 0)}"
            )
        elif event == "probe_error":
            summary = f"ERROR  {payload.get('error') or 'không xác định'}"
        elif event == "probe_stopped":
            summary = "STOP   probe đã được yêu cầu dừng"
        elif event == "probe_exit":
            summary = f"EXIT   returncode={int(payload.get('returncode') or 0)}"
        else:
            summary = f"EVENT  {event}"
            if message:
                summary += f" • {message}"
        return f"[{stamp}] {summary}\n[{stamp}] RAW    {raw_line}\n"

    def _append_probe_event(self, profile_id: str, payload: dict) -> None:
        paths = self._clear_stall_probe_log_paths.get(profile_id)
        if not paths:
            return
        raw = json.dumps(payload, ensure_ascii=False, default=str)
        try:
            with paths[0].open("a", encoding="utf-8", errors="replace") as stream:
                stream.write(self._activity_text(payload, raw))
                stream.flush()
        except OSError:
            pass

    def _open_probe_log_console_paths(
        self, profile_id: str, paths: tuple[Path, Path]
    ) -> None:
        if os.name != "nt":
            return
        log_path, done_path = paths
        try:
            done_path.unlink(missing_ok=True)
            log_path.touch(exist_ok=True)
        except OSError:
            return

        helper = core.TOOL_DIR / "clear_stall_probe_console.py"
        if not helper.is_file():
            self._append_probe_log(profile_id, f"ERROR thiếu console helper: {helper}")
            return
        title = f"KVTM DEV - Don quay RESIDENT probe - {profile_id[:8]}"
        command = subprocess.list2cmdline(
            [
                core.sys.executable,
                str(helper),
                "--log",
                str(log_path),
                "--done",
                str(done_path),
                "--title",
                title,
            ]
        )
        try:
            console = subprocess.Popen(
                ["cmd.exe", "/d", "/s", "/k", command],
                cwd=str(core.TOOL_DIR),
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010),
            )
        except OSError as exc:
            self._append_probe_log(profile_id, f"ERROR không mở được CMD: {exc}")
            return
        self._clear_stall_probe_log_consoles[profile_id] = console

    def _prepare_probe_console(self, profile_id: str, profile: dict | None) -> None:
        paths = self._new_live_log_paths(profile_id)
        self._clear_stall_probe_log_paths[profile_id] = paths
        # The first record is mandatory evidence that the Gate button was
        # actually pressed.  Do not rely on the best-effort append helper here:
        # an empty file cannot be committed and previously hid the whole run.
        header = (
            f"[{time.strftime('%H:%M:%S')}] BUTTON Gate Dọn quầy\\n"
            f"[{time.strftime('%H:%M:%S')}] MODE   IN_PROCESS_RESIDENT\\n"
        )
        try:
            paths[0].write_text(header, encoding="utf-8")
        except OSError as exc:
            self.auto_clear_stall_status.set(f"Không ghi được log Gate: {exc}")
            raise RuntimeError(f"Không ghi được activity.log Gate: {exc}") from exc
        # Keep diagnostics silent/background. The user sends them later
        # through the single Control Center BAT; no extra CMD is opened here.
        if profile:
            self._append_probe_log(
                profile_id,
                f"profile={profile.get('name') or profile_id} id={profile_id}",
            )

    def _mark_probe_console_done(self, profile_id: str, reason: str) -> None:
        paths = self._clear_stall_probe_log_paths.get(profile_id)
        if not paths:
            return
        self._append_probe_log(profile_id, reason)
        self._clear_stall_gate2_profiles.discard(profile_id)
        self._clear_stall_gate3_profiles.discard(profile_id)
        self._clear_stall_gate4_profiles.discard(profile_id)
        self._clear_stall_gate5_profiles.discard(profile_id)
        self._clear_stall_scheduled_profiles.discard(profile_id)
        try:
            paths[1].write_text("done\n", encoding="ascii")
        except OSError:
            pass

    def _start_clear_stall_target_probe(self) -> None:
        """Buy the configured x10 target, with no resale action."""
        self._save_clear_stall_config()
        profile_id, profile = self._clear_stall_profile()
        if not profile_id or not profile:
            core.messagebox.showinfo(core.APP_NAME, "Hãy chọn một tài khoản clone.")
            return
        job = self._clear_stall_job(profile_id)
        quantity = max(10, min(1000, int(job.get("buy_quantity", 10) or 10)))
        quantity = max(10, (quantity // 10) * 10)
        if quantity <= 10:
            core.messagebox.showinfo(
                core.APP_NAME,
                "GATE 3 cần Số lượng mua ít nhất 20 VP; target 10 đã thuộc Gate 2.",
            )
            return
        if not core.messagebox.askyesno(
            core.APP_NAME,
            f"GATE 3B sẽ mua thật đúng {quantity} VP ({quantity // 10} ô x10).\n"
            "Tự tải lại quầy và duyệt nhà 1→N; mỗi ô phải đổi trước khi cộng.\n"
            "Gate này CHƯA thu vàng và CHƯA treo bán. Tiếp tục?",
        ):
            return
        self._clear_stall_gate3_profiles.add(str(profile_id))
        self._start_clear_stall_probe()

    def _start_clear_stall_full_resale_probe(self) -> None:
        """Buy target, collect gold and resell every verified x10 purchase."""
        self._save_clear_stall_config()
        profile_id, profile = self._clear_stall_profile()
        if not profile_id or not profile:
            core.messagebox.showinfo(core.APP_NAME, "Hãy chọn một tài khoản clone.")
            return
        job = self._clear_stall_job(profile_id)
        requested_quantity = int(job.get("buy_quantity", 20) or 20)
        if requested_quantity > 200:
            core.messagebox.showinfo(
                core.APP_NAME,
                "GATE 5 hỗ trợ tối đa 200 VP (20 ô x10) trong một vòng.",
            )
            return
        quantity = max(20, (requested_quantity // 10) * 10)
        storage = max(1, min(5, int(job.get("target_stall_id", 2) or 2)))
        batch_count = quantity // 10
        if not core.messagebox.askyesno(
            core.APP_NAME,
            f"GATE 5 sẽ mua đủ {quantity} VP rồi treo lại toàn bộ "
            f"{batch_count} nhóm VP đã mua.\n"
            f"Chỉ dùng fingerprint đã mua trong lượt này tại kho {storage}.\n"
            "Thu vàng trước, không đổi giá; sai/thiếu VP hoặc hết ô trống sẽ "
            "dừng ngay. Tiếp tục?",
        ):
            return
        self._clear_stall_gate5_profiles.add(str(profile_id))
        self._clear_stall_gate3_profiles.add(str(profile_id))
        self._start_clear_stall_probe()

    def _start_clear_stall_resale_probe(self) -> None:
        """Buy target, collect gold and resell one exact purchased x10 batch."""
        self._save_clear_stall_config()
        profile_id, profile = self._clear_stall_profile()
        if not profile_id or not profile:
            core.messagebox.showinfo(core.APP_NAME, "Hãy chọn một tài khoản clone.")
            return
        job = self._clear_stall_job(profile_id)
        quantity = max(
            20, min(1000, int(job.get("buy_quantity", 20) or 20))
        )
        quantity = max(20, (quantity // 10) * 10)
        storage = max(
            1, min(5, int(job.get("target_stall_id", 2) or 2))
        )
        if not core.messagebox.askyesno(
            core.APP_NAME,
            f"GATE 4 sẽ mua đủ {quantity} VP, thu vàng quầy nhà và "
            "treo thử đúng 1 lô x10.\n"
            f"Chỉ dùng fingerprint VP vừa mua trong vòng này, tìm tại kho {storage}.\n"
            "Không đổi giá; không tìm thấy đúng VP sẽ dừng trước khi treo. Tiếp tục?",
        ):
            return
        self._clear_stall_gate4_profiles.add(str(profile_id))
        self._clear_stall_gate3_profiles.add(str(profile_id))
        self._start_clear_stall_probe()

    def _start_clear_stall_purchase_probe(self) -> None:
        """Require explicit consent, then buy exactly one verified x10 listing."""
        self._save_clear_stall_config()
        profile_id, profile = self._clear_stall_profile()
        if not profile_id or not profile:
            core.messagebox.showinfo(core.APP_NAME, "Hãy chọn một tài khoản clone.")
            return
        if not core.messagebox.askyesno(
            core.APP_NAME,
            "GATE 2 sẽ mua thật đúng 1 ô x10 tại nhà bạn đầu tiên.\n"
            "Sau khi ô quầy đổi, Gate dừng mua và quay về nhà. Tiếp tục?",
        ):
            return
        self._clear_stall_gate2_profiles.add(str(profile_id))
        self._start_clear_stall_probe()

    def _start_clear_stall_probe(self) -> None:
        """Launch clone, then run the selected resident probe inside this process."""
        self._save_clear_stall_config()
        profile_id, profile = self._clear_stall_profile()
        log_profile_id = str(profile_id or "unresolved-profile")
        self._prepare_probe_console(log_profile_id, profile)
        if not profile_id or not profile:
            self._mark_probe_console_done(
                log_profile_id,
                "ERROR không xác định được đúng một clone/profile để probe",
            )
            core.messagebox.showinfo(core.APP_NAME, "Hãy chọn một tài khoản clone.")
            return
        if self._dev_probe_blocked(profile_id):
            self._mark_probe_console_done(profile_id, "Probe bị chặn bởi worker đang hoạt động")
            self.auto_clear_stall_status.set("Đang có AUTO/Dọn quầy khác sử dụng clone")
            return

        auto_worker = self._auto_workers.get(profile_id)
        if self._worker_alive(auto_worker):
            self._mark_probe_console_done(profile_id, "AUTO chính của clone vẫn đang chạy")
            core.messagebox.showinfo(
                core.APP_NAME,
                "Hãy dừng AUTO chính của clone trước khi kiểm tra Dọn quầy.",
            )
            return

        job = self._clear_stall_job(profile_id)
        job["next_run_at"] = 0
        job["last_checkpoint"] = "Đang mở clone để dọn quầy"
        self.settings.setdefault("clear_stall_jobs", {})[profile_id] = job
        core.save_settings(self.settings)
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
            self._mark_probe_console_done(profile_id, f"ERROR mở clone: {exc}")
            self.auto_clear_stall_status.set(f"Lỗi mở clone để kiểm tra: {exc}")
            return

        self._append_probe_log(profile_id, f"clone_pid={proc.pid}")
        self.auto_clear_stall_status.set(
            "Kiểm tra resident • đang chờ ClientJS sẵn sàng"
        )
        self.after(2500, lambda pid=profile_id: self._launch_clear_stall_probe_worker(pid))

    def _launch_clear_stall_probe_worker(self, profile_id: str) -> None:
        """Run probe in a background thread; never spawn a second Python runtime."""
        profile = next((p for p in self.profiles if p.get("id") == profile_id), None)
        proc = self.processes.get(profile_id)
        if not profile or not proc or proc.poll() is not None:
            self._clear_stall_probe_starting.discard(profile_id)
            self._mark_probe_console_done(profile_id, "ERROR clone đã đóng trước probe thread")
            self.auto_clear_stall_status.set("Kiểm tra lỗi: clone đã đóng")
            return

        job = self._clear_stall_job(profile_id)
        friend = max(1, min(7, int(job.get("target_friend_ordinal", 1) or 1)))
        storage = max(1, min(5, int(job.get("target_stall_id", 2) or 2)))
        quantity = max(10, min(1000, int(job.get("buy_quantity", 10) or 10)))
        quantity = max(10, (quantity // 10) * 10)
        max_stall_passes = 1
        default_items = [item_id for item_id, _label in core.CLEAR_STALL_ITEM_OPTIONS]
        raw_items = job.get("allowed_item_ids", default_items)
        allowed_item_ids = tuple(
            item_id
            for item_id in default_items
            if isinstance(raw_items, list) and item_id in raw_items
        )
        if not allowed_item_ids:
            self._clear_stall_probe_starting.discard(profile_id)
            self._mark_probe_console_done(profile_id, "ERROR chưa chọn VP Dọn quầy")
            self.auto_clear_stall_status.set("Dọn quầy lỗi: phải chọn ít nhất một VP")
            return
        try:
            clear_stall_drag_speed = float(
                self._collect_auto_tuning().get("clear_stall_drag_speed", 0.35)
            )
        except (TypeError, ValueError):
            clear_stall_drag_speed = 0.35
        clear_stall_drag_speed = max(0.05, min(3.0, clear_stall_drag_speed))

        run_id = time.strftime("%Y%m%d-%H%M%S")
        work_dir = core.APP_DIR / "clear-stall-probe" / profile_id / run_id
        stop_event = threading.Event()
        self._dev_probe_stop_events[profile_id] = stop_event
        self._clear_stall_probe_terminal.pop(profile_id, None)
        self._clear_stall_probe_starting.discard(profile_id)

        thread = threading.Thread(
            target=self._run_probe_thread,
            args=(
                profile_id, profile, int(proc.pid), friend, storage,
                quantity, max_stall_passes, work_dir, stop_event,
                (
                    quantity // 10
                    if profile_id in self._clear_stall_gate3_profiles
                    else (1 if profile_id in self._clear_stall_gate2_profiles else 0)
                ),
                allowed_item_ids,
                clear_stall_drag_speed,
            ),
            name=f"kvtm-dev-clear-stall-probe-{profile_id[:8]}",
            daemon=True,
        )
        watchdogs = getattr(self, "_clear_stall_probe_watchdogs", None)
        if watchdogs is None:
            watchdogs = {}
            self._clear_stall_probe_watchdogs = watchdogs
        watchdogs[profile_id] = {
            "last_action_at": time.monotonic(),
            "purchased_quantity": 0,
            "sold_quantity": 0,
            "collected_gold_slots": 0,
            "requested_quantity": quantity,
            "timed_out": False,
        }
        self._dev_probe_threads[profile_id] = thread
        self._append_probe_log(
            profile_id,
            f"probe_thread_start pid={proc.pid} report_dir={work_dir}",
        )
        self.auto_clear_stall_status.set(
            f"Kiểm tra resident • Nhà 1..{friend} • {quantity} VP • "
            f"{len(allowed_item_ids)} loại được chọn"
        )
        thread.start()
        self.after(
            5000,
            lambda pid=profile_id: self._watch_clear_stall_probe(pid),
        )
        self._refresh_clear_stall_panel()

    def _run_probe_thread(
        self,
        profile_id: str,
        profile: dict,
        pid: int,
        friend: int,
        storage: int,
        quantity: int,
        max_stall_passes: int,
        work_dir: Path,
        stop_event: threading.Event,
        purchase_limit: int,
        allowed_item_ids: tuple[str, ...],
        clear_stall_drag_speed: float,
    ) -> None:
        returncode = 1
        try:
            _component_root, _worker_root, auto_root = _install_runtime_paths()
            from clear_stall_probe_runtime import ProbeConfig, run_probe

            config = ProbeConfig(
                auto_root=auto_root,
                pid=int(pid),
                profile_id=profile_id,
                profile_name=str(profile.get("name") or profile_id),
                friend_ordinal=int(friend),
                resale_storage_id=int(storage),
                buy_quantity=int(quantity),
                work_dir=work_dir,
                purchase_limit=int(purchase_limit),
                max_stall_passes=int(max_stall_passes),
                allowed_item_ids=allowed_item_ids,
                clear_stall_drag_speed=float(clear_stall_drag_speed),
                resale_batch_limit=(
                    purchase_limit
                    if profile_id in self._clear_stall_gate5_profiles
                    else (1 if profile_id in self._clear_stall_gate4_profiles else 0)
                ),
            )

            def sink(payload: dict) -> None:
                data = dict(payload)
                data["profile_id"] = profile_id
                self._touch_clear_stall_watchdog(profile_id, data)
                self._append_probe_event(profile_id, data)
                self.after(
                    0,
                    lambda event_data=dict(data): self._handle_clear_stall_probe_event(event_data),
                )

            if profile_id in self._clear_stall_gate5_profiles:
                resident_mode = (
                    f"GATE 5 mua và treo lại toàn bộ {purchase_limit * 10} VP"
                )
            elif profile_id in self._clear_stall_gate4_profiles:
                resident_mode = (
                    f"GATE 4 mua {purchase_limit * 10} VP + thu vàng + "
                    "treo VP đã mua"
                )
            elif purchase_limit > 1:
                resident_mode = f"GATE 3B mua target {purchase_limit * 10} VP"
            elif purchase_limit == 1:
                resident_mode = "GATE 2 mua đúng 1 ô x10"
            else:
                resident_mode = "GATE 1 READ-ONLY"
            sink({
                "event": "probe_progress",
                "message": f"Resident runtime đã sẵn sàng • {resident_mode}",
                "stage": "resident-runtime-reused",
            })
            returncode = run_probe(
                config,
                emit_event=sink,
                stop_event=stop_event,
                image_runtime_ready=True,
            )
        except Exception as exc:
            payload = {
                "event": "probe_error",
                "profile_id": profile_id,
                "error": repr(exc),
                "traceback": traceback.format_exc(),
                "report": str(work_dir / "report.json"),
            }
            self._append_probe_event(profile_id, payload)
            self.after(
                0,
                lambda data=dict(payload): self._handle_clear_stall_probe_event(data),
            )
            returncode = 1
        finally:
            exit_payload = {
                "event": "probe_exit",
                "profile_id": profile_id,
                "returncode": int(returncode),
            }
            self._append_probe_event(profile_id, exit_payload)
            self.after(0, lambda data=exit_payload: self._finish_inprocess_probe(data))

    def _close_clear_stall_client(self, profile_id: str, reason: str) -> None:
        """Close only this profile's ClientJS and publish OFF after exit."""
        profile_id = str(profile_id or "")
        proc = self.processes.get(profile_id)
        if not proc:
            self.refresh()
            return
        try:
            expected_pid = int(proc.pid)
        except (AttributeError, TypeError, ValueError):
            expected_pid = 0
        try:
            alive = proc.poll() is None
        except Exception as exc:
            self._append_probe_log(
                profile_id, f"ClientJS OFF check failed: {exc}"
            )
            alive = False
        if alive:
            self._append_probe_log(
                profile_id,
                f"ClientJS OFF requested pid={expected_pid} reason={reason}",
            )
            try:
                proc.terminate()
            except OSError as exc:
                self._append_probe_log(
                    profile_id, f"ClientJS OFF terminate failed: {exc}"
                )
        self.after(
            250,
            lambda pid=profile_id, target=proc, target_pid=expected_pid,
            why=str(reason), deadline=time.monotonic() + 8.0:
            self._confirm_clear_stall_client_off(
                pid, target, target_pid, why, deadline
            ),
        )

    def _confirm_clear_stall_client_off(
        self,
        profile_id: str,
        target_proc,
        expected_pid: int,
        reason: str,
        deadline: float,
    ) -> None:
        """Never remove or terminate a replacement PID created after cleanup."""
        current = self.processes.get(profile_id)
        if current is not target_proc:
            self._append_probe_log(
                profile_id,
                f"ClientJS OFF skipped replacement pid; old={expected_pid}",
            )
            self.refresh()
            return
        try:
            alive = target_proc.poll() is None
        except Exception:
            alive = False
        if alive and time.monotonic() < deadline:
            self.after(
                250,
                lambda: self._confirm_clear_stall_client_off(
                    profile_id, target_proc, expected_pid, reason, deadline
                ),
            )
            return
        if alive:
            self._append_probe_log(
                profile_id,
                f"ClientJS OFF timeout pid={expected_pid} reason={reason}",
            )
            self.auto_clear_stall_status.set(
                f"Dọn quầy đã dừng nhưng ClientJS PID {expected_pid} chưa OFF"
            )
            self.refresh()
            return
        self.processes.pop(profile_id, None)
        self._append_probe_log(
            profile_id,
            f"ClientJS OFF confirmed pid={expected_pid} reason={reason}",
        )
        if profile_id == self._active_profile_id:
            self.auto_clear_stall_status.set(
                "Dọn quầy đã kết thúc • tài khoản đã về OFF"
            )
        self.refresh()
        self._refresh_clear_stall_panel()

    def _handle_clear_stall_probe_event(self, payload: dict) -> None:
        profile_id = str(payload.get("profile_id") or "")
        event = str(payload.get("event") or "")
        if (
            self._clear_stall_probe_terminal.get(profile_id) == "TEMP_PASS"
            and event in {"probe_error", "probe_stopped", "probe_exit"}
        ):
            return
        self._record_clear_stall_activity(payload)
        message = str(payload.get("message") or "")
        stage = str(payload.get("stage") or "")
        transaction_gate = str(payload.get("transaction_gate") or "")
        is_gate5 = (
            transaction_gate == "COLLECT_GOLD_RESELL_TARGET_EXACT"
            or profile_id in self._clear_stall_gate5_profiles
        )
        is_gate4 = (
            transaction_gate == "COLLECT_GOLD_RESELL_ONE_EXACT"
            or profile_id in self._clear_stall_gate4_profiles
        )
        is_gate3 = (
            transaction_gate == "PURCHASE_TARGET_MULTI_HOUSE"
            or profile_id in self._clear_stall_gate3_profiles
        )
        is_gate2 = (
            transaction_gate == "PURCHASE_ONE_LISTING"
            or profile_id in self._clear_stall_gate2_profiles
        )
        gate_name = (
            "GATE 5" if is_gate5 else "GATE 4" if is_gate4
            else "GATE 3B" if is_gate3 else "GATE 2" if is_gate2 else "GATE 1"
        )

        if event == "probe_boot":
            self._set_clear_stall_checkpoint(
                profile_id, f"{gate_name} • {stage or 'đang khởi tạo'}"
            )
        elif event == "probe_progress":
            self._set_clear_stall_checkpoint(
                profile_id, message or stage or f"{gate_name} đang chạy"
            )
        elif event == "probe_purchase_ok":
            purchased = int(payload.get("purchased_quantity") or 0)
            self._set_clear_stall_checkpoint(
                profile_id, f"{gate_name} • đã xác minh mua {purchased} VP"
            )
        elif event == "probe_resale_ok":
            sold = int(payload.get("sold_quantity") or payload.get("quantity") or 0)
            fingerprint = str(payload.get("fingerprint_sha256") or "")
            self._set_clear_stall_checkpoint(
                profile_id,
                f"{gate_name} • đã treo {sold} VP • fingerprint={fingerprint[:12]}",
            )
        elif event == "probe_ok":
            sample_hits = int(payload.get("sample_hits_not_unique_inventory") or 0)
            requested = int(payload.get("requested_quantity") or 0)
            purchased = int(payload.get("purchased_quantity") or 0)
            sold = int(payload.get("sold_quantity") or 0)
            collected_gold = int(payload.get("collected_gold_slots") or 0)
            transaction_gate = str(payload.get("transaction_gate") or "")
            is_gate5 = (
                transaction_gate == "COLLECT_GOLD_RESELL_TARGET_EXACT"
                or profile_id in self._clear_stall_gate5_profiles
            )
            is_gate4 = (
                transaction_gate == "COLLECT_GOLD_RESELL_ONE_EXACT"
                and not is_gate5
            )
            is_gate3 = transaction_gate == "PURCHASE_TARGET_MULTI_HOUSE"
            is_gate2 = transaction_gate == "PURCHASE_ONE_LISTING"

            if is_gate5:
                if requested <= 0 or purchased != requested or sold != requested:
                    self._clear_stall_probe_terminal[profile_id] = "FAIL"
                    self._set_clear_stall_checkpoint(
                        profile_id,
                        "Dọn quầy chưa đủ số lượng • giữ clone để kiểm tra",
                        {
                            "ok": False,
                            "requested_quantity": requested,
                            "purchased_quantity": purchased,
                            "sold_quantity": sold,
                        },
                    )
                    self._close_clear_stall_client(
                        profile_id, "incomplete-purchase-or-resale"
                    )
                    return
                job = self._clear_stall_job(profile_id)
                interval = max(5, int(job.get("interval_minutes", 65) or 65))
                finished_at = time.time()
                job["last_checkpoint"] = (
                    f"Hoàn thành • mua {purchased}/{requested} • treo {sold}; "
                    f"chờ {interval} phút"
                )
                job["last_result"] = {
                    "ok": True,
                    "finished_at": finished_at,
                    "requested_quantity": requested,
                    "purchased_quantity": purchased,
                    "sold_quantity": sold,
                    "collected_gold_slots": collected_gold,
                    "transaction_gate": transaction_gate,
                }
                job["next_run_at"] = (
                    finished_at + interval * 60 if job.get("enabled", False) else 0
                )
                self.settings.setdefault("clear_stall_jobs", {})[profile_id] = job
                core.save_settings(self.settings)
                if bool(job.get("close_client_after_run", True)):
                    proc = self.processes.get(profile_id)
                    if proc and proc.poll() is None:
                        proc.terminate()
                summary = (
                    f"DỌN QUẦY PASS • mua {purchased}/{requested} VP • "
                    f"thu {collected_gold} ô vàng • treo đủ {sold} VP"
                )
            elif is_gate4:
                summary = (
                    f"GATE 4 PASS • mua {purchased}/{requested} VP • "
                    f"thu {collected_gold} ô vàng • treo đúng {sold} VP vừa mua"
                )
            elif is_gate3:
                summary = (
                    f"GATE 3B PASS • đã mua đủ {purchased}/{requested} VP "
                    "qua tải lại/chuyển nhà"
                )
            elif is_gate2:
                summary = f"GATE 2 PASS • đã mua và xác minh đúng {purchased} VP"
            else:
                summary = (
                    "GATE 1 PASS • điều hướng/capture/4 view ổn định • "
                    f"{sample_hits} mẫu ảnh có VP (chỉ chẩn đoán) • "
                    f"mục tiêu {requested} VP dùng bộ đếm động"
                )

            self._clear_stall_probe_terminal[profile_id] = "PASS"
            self._set_clear_stall_checkpoint(
                profile_id,
                summary,
                {
                    "ok": True,
                    "probe_only": not (
                        is_gate2 or is_gate3 or is_gate4 or is_gate5
                    ),
                    "transaction_gate": transaction_gate or "READ_ONLY_SCAN",
                    "purchased_quantity": purchased,
                    "sold_quantity": sold,
                    "collected_gold_slots": collected_gold,
                    "sample_hits_not_unique_inventory": sample_hits,
                    "capacity_model": str(
                        payload.get("capacity_model") or "DYNAMIC_REMAINING_COUNTER"
                    ),
                    "requested_quantity": requested,
                    "report": str(payload.get("report") or ""),
                },
            )
        elif event == "probe_stopped":
            self._clear_stall_probe_terminal[profile_id] = "STOPPED"
            self._set_clear_stall_checkpoint(
                profile_id, f"{gate_name} đã dừng an toàn"
            )
            self._close_clear_stall_client(profile_id, "probe-stopped")
        elif event == "probe_error":
            error = str(payload.get("error") or "Lỗi probe không xác định")
            scheduled_run = profile_id in self._clear_stall_scheduled_profiles
            self._clear_stall_probe_terminal[profile_id] = "FAIL"
            self._set_clear_stall_checkpoint(
                profile_id,
                f"{gate_name} FAIL",
                {
                    "ok": False,
                    "probe_only": not (
                        is_gate2 or is_gate3 or is_gate4 or is_gate5
                    ),
                    "transaction_gate": transaction_gate or "UNKNOWN",
                    "error": error,
                    "report": str(payload.get("report") or ""),
                },
            )
            if scheduled_run:
                job = self._clear_stall_job(profile_id)
                interval = max(5, int(job.get("interval_minutes", 65) or 65))
                finished_at = time.time()
                job["last_checkpoint"] = (
                    f"Lỗi tự động • đã đóng clone; thử lại sau {interval} phút: {error}"
                )
                job["last_result"] = {
                    "ok": False,
                    "scheduled_failure": True,
                    "finished_at": finished_at,
                    "error": error,
                }
                job["next_run_at"] = (
                    finished_at + interval * 60 if job.get("enabled", False) else 0
                )
                self.settings.setdefault("clear_stall_jobs", {})[profile_id] = job
                core.save_settings(self.settings)
            elif profile_id == self._active_profile_id:
                core.messagebox.showerror(core.APP_NAME, f"{gate_name} lỗi:\n{error}")
            self._close_clear_stall_client(profile_id, "probe-error")
        elif event == "probe_exit":
            if profile_id not in self._clear_stall_probe_terminal:
                code = int(payload.get("returncode") or 0)
                self._clear_stall_probe_terminal[profile_id] = (
                    "PASS" if code == 0 else "FAIL"
                )
                if code != 0:
                    self._close_clear_stall_client(
                        profile_id, f"probe-exit-{code}"
                    )

    def _touch_clear_stall_watchdog(
        self, profile_id: str, payload: dict
    ) -> None:
        state = getattr(self, "_clear_stall_probe_watchdogs", {}).get(profile_id)
        if not state or state.get("timed_out"):
            return
        for key in (
            "requested_quantity", "purchased_quantity", "sold_quantity",
            "collected_gold_slots",
        ):
            value = int(payload.get(key) or 0)
            if value:
                state[key] = max(int(state.get(key) or 0), value)

        event = str(payload.get("event") or "")
        message = str(payload.get("message") or "")
        stage = str(payload.get("stage") or "")
        capture_only = (
            "CAPTURE metadata" in message
            or message.startswith("Capture:")
            or message.startswith("Đã chụp ")
            or "capture" in stage.lower()
        )
        if event in {
            "probe_purchase_ok", "probe_resale_ok", "probe_ok",
            "probe_error", "probe_stopped",
        } or (event in {"probe_boot", "probe_progress"} and not capture_only):
            state["last_action_at"] = time.monotonic()

    def _watch_clear_stall_probe(self, profile_id: str) -> None:
        state = getattr(self, "_clear_stall_probe_watchdogs", {}).get(profile_id)
        if not state or state.get("timed_out"):
            return
        if not self._probe_thread_alive(profile_id):
            self._clear_stall_probe_watchdogs.pop(profile_id, None)
            return

        # Temporary overnight safety: capture frames do not count as workflow
        # progress. Five minutes without navigation/purchase/resale progress
        # closes only this clone and releases the serialized queue safely.
        stalled_for = time.monotonic() - float(
            state.get("last_action_at") or time.monotonic()
        )
        if stalled_for < 300.0:
            self.after(
                5000,
                lambda pid=profile_id: self._watch_clear_stall_probe(pid),
            )
            return

        state["timed_out"] = True
        stop_event = self._dev_probe_stop_events.get(profile_id)
        if stop_event is not None:
            stop_event.set()
        requested = int(state.get("requested_quantity") or 0)
        purchased = int(state.get("purchased_quantity") or 0)
        sold = int(state.get("sold_quantity") or 0)
        gold = int(state.get("collected_gold_slots") or 0)
        message = (
            "TẠM PASS watchdog • không có tiến độ thao tác 5 phút • "
            f"mua {purchased}/{requested} VP • treo {sold} VP • "
            f"thu {gold} ô vàng • đã đóng ClientJS và trả về hàng chờ"
        )
        payload = {
            "event": "probe_temp_pass",
            "profile_id": profile_id,
            "message": message,
            "requested_quantity": requested,
            "purchased_quantity": purchased,
            "sold_quantity": sold,
            "collected_gold_slots": gold,
        }
        self._append_probe_event(profile_id, payload)
        self._record_clear_stall_activity(payload)
        self._clear_stall_probe_terminal[profile_id] = "TEMP_PASS"

        job = self._clear_stall_job(profile_id)
        interval = max(5, int(job.get("interval_minutes", 65) or 65))
        finished_at = time.time()
        job["last_checkpoint"] = message
        job["last_result"] = {
            "ok": True,
            "temporary_pass": True,
            "reason": "watchdog_no_action_300s",
            "finished_at": finished_at,
            "requested_quantity": requested,
            "purchased_quantity": purchased,
            "sold_quantity": sold,
            "collected_gold_slots": gold,
        }
        job["next_run_at"] = (
            finished_at + interval * 60 if job.get("enabled", False) else 0
        )
        self.settings.setdefault("clear_stall_jobs", {})[profile_id] = job
        core.save_settings(self.settings)
        if profile_id == self._active_profile_id:
            self.auto_clear_stall_status.set(message)
        self._append_probe_log(profile_id, message)

        proc = self.processes.get(profile_id)
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except OSError as exc:
                self._append_probe_log(
                    profile_id, f"WATCHDOG close ClientJS failed: {exc}"
                )
        self.after(1500, self._refresh_clear_stall_panel)

    def _finish_inprocess_probe(self, payload: dict) -> None:
        profile_id = str(payload.get("profile_id") or "")
        self._dev_probe_threads.pop(profile_id, None)
        getattr(self, "_clear_stall_probe_watchdogs", {}).pop(profile_id, None)
        self._dev_probe_stop_events.pop(profile_id, None)
        self._handle_clear_stall_probe_event(payload)
        self._mark_probe_console_done(profile_id, "In-process resident probe finished")
        self._refresh_clear_stall_panel()

    def _stop_clear_stall(self) -> None:
        profile_id, _profile = self._clear_stall_profile()
        profile_id = str(profile_id or "")
        stop_event = self._dev_probe_stop_events.get(profile_id)
        if stop_event is not None and self._probe_thread_alive(profile_id):
            stop_event.set()
            self._append_probe_log(profile_id, "STOP requested for in-process probe")
            self.auto_clear_stall_status.set("Đã gửi yêu cầu dừng probe resident")
            return
        super()._stop_clear_stall()

    def _on_close(self) -> None:
        for event in tuple(getattr(self, "_clean_main_stop_events", {}).values()):
            event.set()
        for event in tuple(getattr(self, "_dev_probe_stop_events", {}).values()):
            event.set()
        for profile_id, paths in tuple(
            getattr(self, "_clear_stall_probe_log_paths", {}).items()
        ):
            try:
                paths[1].write_text("closed\n", encoding="ascii")
            except OSError:
                pass
        super()._on_close()


def main() -> int:
    if os.name != "nt":
        print("KVTM Multi DEV chỉ chạy trên Windows.")
        return 1

    try:
        _prewarm_resident_image_runtime()
    except Exception as exc:
        print(
            f"[KVTM DEV] RESIDENT RUNTIME FAILED: {type(exc).__name__}: {exc}",
            flush=True,
        )
        traceback.print_exc()
        return 2

    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
    MultiDevApp().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
