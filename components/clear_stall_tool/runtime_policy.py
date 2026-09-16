from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback

try:
    from .runtime_controller import ClearStallController
except ImportError:
    from runtime_controller import ClearStallController


class OrderedSafeClearStallController(ClearStallController):
    """Standalone orchestration policy for deterministic account startup.

    Business behavior remains in ``clear_stall_probe_runtime``.  This class only
    owns standalone lifecycle policy:

    * first runs are admitted in the exact order ``start()`` is requested;
    * a hard failure before ``probe_ok`` keeps ClientJS open for inspection;
    * a hard failure pauses that account instead of silently waiting a full
      cycle and trying again;
    * successful runs and explicit Stop still close the ClientJS process.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._start_condition = threading.Condition()
        self._issued_start_ticket = 0
        self._next_start_ticket = 1
        self._finished_start_tickets: set[int] = set()

    def _issue_start_ticket(self) -> int:
        with self._start_condition:
            self._issued_start_ticket += 1
            return self._issued_start_ticket

    def _wait_start_turn(
        self,
        ticket: int,
        profile_id: str,
        stop_event: threading.Event,
    ) -> bool:
        with self._start_condition:
            while ticket != self._next_start_ticket:
                if ticket < self._next_start_ticket:
                    return False
                if stop_event.is_set() or self._closed or profile_id not in self._enabled:
                    return False
                self._start_condition.wait(timeout=0.10)
            return not (
                stop_event.is_set()
                or self._closed
                or profile_id not in self._enabled
            )

    def _finish_start_ticket(self, ticket: int) -> None:
        with self._start_condition:
            if ticket < self._next_start_ticket:
                return
            self._finished_start_tickets.add(ticket)
            while self._next_start_ticket in self._finished_start_tickets:
                self._finished_start_tickets.remove(self._next_start_ticket)
                self._next_start_ticket += 1
            self._start_condition.notify_all()

    def _wake_start_queue(self) -> None:
        with self._start_condition:
            self._start_condition.notify_all()

    def _live_client(self, profile_id: str) -> subprocess.Popen | None:
        pid = str(profile_id)
        client = self._clients.get(pid)
        if client is None:
            return None
        if client.poll() is None:
            return client
        self._clients.pop(pid, None)
        return None

    def _close_client(self, profile_id: str, reason: str) -> None:
        pid = str(profile_id)
        client = self._clients.pop(pid, None)
        if client is None:
            return
        if client.poll() is not None:
            return
        try:
            client.terminate()
            client.wait(timeout=5)
            self._log(
                pid,
                "client_closed",
                "ClientJS đã đóng",
                client_pid=client.pid,
                reason=str(reason),
            )
        except Exception as exc:
            self._log(
                pid,
                "client_close_force",
                str(exc),
                client_pid=client.pid,
                reason=str(reason),
            )
            try:
                client.kill()
            except OSError:
                pass

    def start(self, profile_id: str) -> None:
        pid = str(profile_id or "")
        if not pid or self._closed or pid in self._enabled:
            return
        if self.store.profile(pid) is None:
            self._emit(
                pid,
                "error",
                message="Profile không còn trong profiles.json của Dọn quầy",
            )
            return

        ticket = self._issue_start_ticket()
        self._enabled.add(pid)
        stop_event = threading.Event()
        self._stop_events[pid] = stop_event
        self._log(
            pid,
            "start_order_queued",
            f"Đã xếp hàng khởi động thứ tự {ticket}",
            start_ticket=ticket,
        )
        self._emit(pid, "running", message="Đã bật lịch Dọn quầy")
        thread = threading.Thread(
            target=self._schedule_loop,
            args=(pid, stop_event, ticket),
            name=f"kvtm-clear-stall-{pid[:8]}",
            daemon=True,
        )
        self._threads[pid] = thread
        thread.start()

    def stop(self, profile_id: str) -> None:
        pid = str(profile_id or "")
        self._enabled.discard(pid)
        event = self._stop_events.get(pid)
        if event:
            event.set()

        worker = self._workers.get(pid)
        worker_alive = worker is not None and worker.poll() is None
        if worker_alive and worker.stdin:
            try:
                worker.stdin.write(json.dumps({"command": "stop"}) + "\n")
                worker.stdin.flush()
                self._log(
                    pid,
                    "worker_stop_requested",
                    "Đã gửi lệnh stop tới worker",
                    worker_pid=worker.pid,
                )
            except OSError as exc:
                self._log(pid, "worker_stop_error", str(exc))
        else:
            # A failed pre-clean cycle deliberately leaves ClientJS open.  An
            # explicit Stop is the operator's instruction to close it.
            self._close_client(pid, "explicit_stop")

        self._wake_start_queue()
        self._emit(pid, "stopped", message="Đã dừng Dọn quầy")

    def stop_all(self) -> None:
        for pid in list(self._enabled | set(self._workers) | set(self._clients)):
            self.stop(pid)

    def close(self) -> None:
        self._closed = True
        self._wake_start_queue()
        self.stop_all()

    def _schedule_loop(
        self,
        profile_id: str,
        stop_event: threading.Event,
        start_ticket: int,
    ) -> None:
        first = True
        pending_ticket: int | None = int(start_ticket)
        try:
            while (
                not stop_event.is_set()
                and profile_id in self._enabled
                and not self._closed
            ):
                if not first:
                    interval = int(
                        self.store.ensure_job(profile_id).get("interval_minutes", 65)
                    )
                    self._log(
                        profile_id,
                        "cycle_wait",
                        f"Chờ {interval} phút tới lượt tiếp theo",
                    )
                    if stop_event.wait(max(5, interval) * 60):
                        break
                first = False

                if pending_ticket is not None:
                    if not self._wait_start_turn(
                        pending_ticket, profile_id, stop_event
                    ):
                        break
                    self._log(
                        profile_id,
                        "start_order_enter",
                        f"Bắt đầu theo hàng đợi thứ tự {pending_ticket}",
                        start_ticket=pending_ticket,
                    )

                if (
                    stop_event.is_set()
                    or profile_id not in self._enabled
                    or self._closed
                ):
                    break

                hard_error = False
                try:
                    with self._semaphore:
                        if (
                            stop_event.is_set()
                            or profile_id not in self._enabled
                            or self._closed
                        ):
                            break
                        self._run_once(profile_id, stop_event)
                except Exception as exc:
                    hard_error = True
                    self._log(
                        profile_id,
                        "cycle_exception",
                        str(exc),
                        traceback=traceback.format_exc(),
                    )
                    # Fail closed for automation, but do not destroy the game
                    # window.  The operator can inspect it and the Log, then
                    # press Play to retry or Stop to close it.
                    self._enabled.discard(profile_id)
                    self._log(
                        profile_id,
                        "cycle_paused_after_error",
                        "Đã tạm dừng tài khoản sau lỗi; giữ ClientJS mở để kiểm tra",
                    )
                    self._emit(profile_id, "cycle_error", message=str(exc))
                finally:
                    if pending_ticket is not None:
                        self._finish_start_ticket(pending_ticket)
                        pending_ticket = None

                if hard_error:
                    break
        finally:
            if pending_ticket is not None:
                self._finish_start_ticket(pending_ticket)
            self._threads.pop(profile_id, None)
            self._emit(profile_id, "stopped", message="Dọn quầy đã dừng")

    def _run_once(self, profile_id: str, stop_event: threading.Event) -> None:
        profile = self.store.profile(profile_id)
        if profile is None:
            raise RuntimeError("Profile đã bị xóa khỏi snapshot Dọn quầy")

        job = self.store.ensure_job(profile_id)
        quantity = int(job.get("buy_quantity", 10))
        if quantity % 10 or not 10 <= quantity <= 1000:
            raise RuntimeError("Số lượng Dọn quầy phải là bội số 10 trong 10..1000")

        terminal_ok = False
        proc: subprocess.Popen | None = None
        worker: subprocess.Popen | None = None
        self._emit(profile_id, "cycle_start", message="Chuẩn bị ClientJS cho Dọn quầy")

        try:
            proc = self._live_client(profile_id)
            if proc is None:
                proc = self._launch_client(profile)
                self._clients[profile_id] = proc
            else:
                self._log(
                    profile_id,
                    "client_reused_after_error",
                    "Dùng lại ClientJS đang mở từ lượt lỗi trước",
                    client_pid=proc.pid,
                )

            self._resize_client(proc.pid, stop_event)
            self._log(
                profile_id,
                "client_ready",
                "ClientJS đã sẵn sàng 1000x1000",
                client_pid=proc.pid,
            )
            if stop_event.wait(2.5):
                return

            run_id = time.strftime("%Y%m%d-%H%M%S")
            work_dir = self.store.app_dir / "runs" / profile_id / run_id
            work_dir.mkdir(parents=True, exist_ok=True)
            worker_file = Path(__file__).resolve().parent / "standalone_clear_stall_worker.py"
            allowed = list(job.get("allowed_item_ids") or [])
            args = [
                sys.executable,
                str(worker_file),
                "--runtime-root", str(self.paths.runtime_root),
                "--profile-file", str(self.store.profile_file),
                "--pid", str(proc.pid),
                "--profile-id", profile_id,
                "--profile-name", str(profile.get("name") or profile_id),
                "--friend-ordinal", str(int(job.get("target_friend_ordinal", 1))),
                "--stall-id", str(int(job.get("target_stall_id", 2))),
                "--quantity", str(quantity),
                "--max-stall-passes", str(int(job.get("max_scan_pages", 10))),
                "--allowed-items-json", json.dumps(allowed, ensure_ascii=True),
                "--drag-speed", str(float(job.get("clear_stall_drag_speed", 0.35))),
                "--work-dir", str(work_dir),
            ]
            env = os.environ.copy()
            env["KVTM_MULTI_PROFILE_FILE"] = str(self.store.profile_file)
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            worker = subprocess.Popen(
                args,
                cwd=str(self.paths.auto_root),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=flags,
                env=env,
            )
            self._workers[profile_id] = worker
            self._log(
                profile_id,
                "worker_started",
                "Worker Dọn quầy đã khởi động",
                worker_pid=worker.pid,
                client_pid=proc.pid,
                run_id=run_id,
            )

            if worker.stdout:
                for raw_line in worker.stdout:
                    line = raw_line.rstrip("\r\n")
                    if line:
                        self._log(profile_id, "worker_stdout", line)
                    if stop_event.is_set() and worker.poll() is None and worker.stdin:
                        try:
                            worker.stdin.write(json.dumps({"command": "stop"}) + "\n")
                            worker.stdin.flush()
                        except OSError:
                            pass
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        payload = {"event": "probe_progress", "message": line}
                    event = str(payload.get("event") or "")
                    message = str(
                        payload.get("message") or payload.get("error") or ""
                    )
                    if event in {"probe_progress", "probe_boot"} and message:
                        self._emit(profile_id, "progress", message=message)
                    elif event == "probe_ok":
                        terminal_ok = True
                        self._emit(
                            profile_id,
                            "progress",
                            message="Dọn quầy hoàn tất",
                        )
                    elif event == "probe_error":
                        self._emit(
                            profile_id,
                            "progress",
                            message=message or "Dọn quầy lỗi",
                        )

            rc = worker.wait()
            self._log(
                profile_id,
                "worker_exit",
                f"Worker kết thúc mã {rc}",
                worker_pid=worker.pid,
                return_code=rc,
                terminal_ok=terminal_ok,
            )
            if stop_event.is_set():
                return
            if rc != 0:
                raise RuntimeError(f"Worker Dọn quầy kết thúc mã {rc}")
            if not terminal_ok:
                raise RuntimeError(
                    "Worker Dọn quầy đã thoát nhưng chưa phát bằng chứng probe_ok; "
                    "không ghi nhận hoàn tất."
                )

            stamp = time.strftime("%H:%M %d/%m/%Y")
            self.store.mark_clean(profile_id, stamp)
            self._emit(
                profile_id,
                "cycle_done",
                message="Dọn quầy hoàn tất",
                last_clean=stamp,
            )
        finally:
            self._workers.pop(profile_id, None)
            # Never close a newly launched game merely because the worker failed
            # before Dọn quầy completed.  Preserve it for live diagnosis/retry.
            if terminal_ok:
                self._close_client(profile_id, "cycle_completed")
            elif stop_event.is_set() or self._closed:
                self._close_client(profile_id, "operator_stop")
            else:
                client = self._live_client(profile_id)
                if client is not None:
                    self._log(
                        profile_id,
                        "client_preserved_after_error",
                        "Worker chưa hoàn tất; giữ ClientJS mở để kiểm tra/retry",
                        client_pid=client.pid,
                    )
