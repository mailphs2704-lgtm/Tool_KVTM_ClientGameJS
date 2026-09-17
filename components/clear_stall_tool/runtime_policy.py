from __future__ import annotations

import ctypes
from ctypes import wintypes
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
    """Standalone orchestration policy for deterministic account startup."""

    # Dọn quầy must never keep two game sessions active at once.  The ordered
    # start-ticket queue handles first admission; this semaphore also serializes
    # all later scheduled cycles.
    MAX_CONCURRENCY = 1

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

    @staticmethod
    def _hwnd_value(hwnd) -> int:
        if isinstance(hwnd, int):
            return int(hwnd)
        return int(ctypes.cast(hwnd, ctypes.c_void_p).value or 0)

    @classmethod
    def _find_window_win64_safe(cls, pid: int) -> int:
        """Find the largest visible top-level window for pid with pointer-safe HWNDs."""
        if os.name != "nt":
            return 0
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        callback_type = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HWND,
            wintypes.LPARAM,
        )
        user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
        user32.EnumWindows.restype = wintypes.BOOL
        user32.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        ]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsWindowVisible.restype = wintypes.BOOL
        user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.GetClientRect.restype = wintypes.BOOL

        candidates: list[tuple[int, int]] = []

        @callback_type
        def callback(hwnd, _lparam):
            window_pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
            if int(window_pid.value) != int(pid) or not user32.IsWindowVisible(hwnd):
                return True
            rect = wintypes.RECT()
            if user32.GetClientRect(hwnd, ctypes.byref(rect)):
                width = max(0, int(rect.right - rect.left))
                height = max(0, int(rect.bottom - rect.top))
                if width > 0 and height > 0:
                    candidates.append((width * height, cls._hwnd_value(hwnd)))
            return True

        if not user32.EnumWindows(callback, 0):
            error = ctypes.get_last_error()
            if error:
                raise ctypes.WinError(error)
        if not candidates:
            return 0
        return max(candidates, key=lambda item: item[0])[1]

    def _resize_client(self, pid: int, stop_event: threading.Event) -> None:
        """Resize ClientJS and prove the client area is exactly 1000x1000.

        This deliberately bypasses packaged pc_driver.find_window.  Its untyped
        EnumWindows callback can truncate a 64-bit HWND and spam OverflowError,
        which also made resize randomly miss the actual game window.
        """
        if os.name != "nt":
            raise RuntimeError("Chuẩn hóa ClientJS 1000x1000 chỉ hỗ trợ Windows")

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = ctypes.c_long
        user32.AdjustWindowRectEx.argtypes = [
            ctypes.POINTER(wintypes.RECT),
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        user32.AdjustWindowRectEx.restype = wintypes.BOOL
        user32.SetWindowPos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        user32.SetWindowPos.restype = wintypes.BOOL
        user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.GetClientRect.restype = wintypes.BOOL

        deadline = time.monotonic() + 25.0
        hwnd_value = 0
        while time.monotonic() < deadline and not stop_event.is_set():
            hwnd_value = self._find_window_win64_safe(int(pid))
            if hwnd_value:
                break
            time.sleep(0.10)
        if not hwnd_value:
            raise RuntimeError(
                "ClientJS đã mở nhưng chưa tìm thấy cửa sổ Win64-safe để chuẩn hóa 1000x1000"
            )

        hwnd = wintypes.HWND(hwnd_value)
        style = ctypes.c_uint32(user32.GetWindowLongW(hwnd, -16)).value
        ex_style = ctypes.c_uint32(user32.GetWindowLongW(hwnd, -20)).value
        target = wintypes.RECT(0, 0, 1000, 1000)
        if not user32.AdjustWindowRectEx(
            ctypes.byref(target), style, False, ex_style
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        outer_width = int(target.right - target.left)
        outer_height = int(target.bottom - target.top)

        last_client = (0, 0)
        resize_deadline = time.monotonic() + 8.0
        while time.monotonic() < resize_deadline and not stop_event.is_set():
            if not user32.SetWindowPos(
                hwnd,
                None,
                0,
                0,
                max(100, int(outer_width)),
                max(100, int(outer_height)),
                0x0002 | 0x0004 | 0x0040,
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            time.sleep(0.15)
            client_rect = wintypes.RECT()
            if not user32.GetClientRect(hwnd, ctypes.byref(client_rect)):
                raise ctypes.WinError(ctypes.get_last_error())
            client_width = int(client_rect.right - client_rect.left)
            client_height = int(client_rect.bottom - client_rect.top)
            last_client = (client_width, client_height)
            if last_client == (1000, 1000):
                return
            # DPI/non-client metrics can differ across machines. Correct the
            # outer dimensions by the measured client-area error and verify again.
            outer_width += 1000 - client_width
            outer_height += 1000 - client_height

        if stop_event.is_set():
            return
        raise RuntimeError(
            "Không chuẩn hóa được ClientJS về client-area 1000x1000 • "
            f"đo lần cuối={last_client[0]}x{last_client[1]}"
        )

    def start(self, profile_id: str, *, first_delay_seconds: float = 0.0) -> None:
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

        first_delay = max(0.0, float(first_delay_seconds or 0.0))
        ticket = self._issue_start_ticket() if first_delay <= 0 else None
        self._enabled.add(pid)
        stop_event = threading.Event()
        self._stop_events[pid] = stop_event
        self._log(
            pid,
            "start_order_queued",
            (
                f"Đã xếp hàng khởi động thứ tự {ticket}"
                if ticket is not None
                else f"Phiên đầu sẽ bắt đầu sau {int(round(first_delay / 60))} phút"
            ),
            start_ticket=ticket,
            first_delay_seconds=first_delay,
        )
        self._emit(pid, "running", message="Đã bật lịch Dọn quầy")
        thread = threading.Thread(
            target=self._schedule_loop,
            args=(pid, stop_event, ticket, first_delay),
            name=f"kvtm-clear-stall-{pid[:8]}",
            daemon=True,
        )
        self._threads[pid] = thread
        thread.start()

    def enqueue(self, profile_id: str, *, first_delay_seconds: float = 0.0) -> None:
        """Schedule one account; only its first cycle uses the requested delay."""
        pid = str(profile_id or "")
        if not pid:
            return
        if pid in self._enabled:
            self._log(pid, "manual_add_ignored", "Tài khoản đã có trong tiến trình Dọn quầy")
            return
        self._log(pid, "manual_add_requested", "Đã thêm tài khoản vào tiến trình Dọn quầy")
        self.start(pid, first_delay_seconds=first_delay_seconds)

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
        start_ticket: int | None,
        first_delay_seconds: float = 0.0,
    ) -> None:
        first = True
        pending_ticket = int(start_ticket) if start_ticket is not None else None
        try:
            first_delay = max(0.0, float(first_delay_seconds or 0.0))
            if first_delay > 0:
                self._emit(
                    profile_id,
                    "first_cycle_wait",
                    message=(
                        "Đang chờ phiên đầu • còn "
                        f"{max(1, int(round(first_delay / 60)))} phút"
                    ),
                    wait_seconds=first_delay,
                )
                if stop_event.wait(first_delay):
                    return
                pending_ticket = self._issue_start_ticket()
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
                    self._enabled.discard(profile_id)
                    self._log(
                        profile_id,
                        "cycle_paused_after_error",
                        "Đã tạm dừng tài khoản sau lỗi; ClientJS đã được đóng để giải phóng phiên online",
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
                    "client_reused",
                    "Dùng lại ClientJS đang được controller theo dõi",
                    client_pid=proc.pid,
                )

            self._resize_client(proc.pid, stop_event)
            self._log(
                profile_id,
                "client_ready",
                "ClientJS đã xác minh client-area 1000x1000",
                client_pid=proc.pid,
                verified_client_width=1000,
                verified_client_height=1000,
                window_lookup="WIN64_POINTER_SAFE_ENUMWINDOWS",
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
                "--drag-speed", "0.20",
                "--work-dir", str(work_dir),
            ]
            env = os.environ.copy()
            env["KVTM_MULTI_PROFILE_FILE"] = str(self.store.profile_file)
            env["KVTM_CLEAR_STALL_SINGLE_SWIPE"] = "1"
            env["KVTM_CLEAR_STALL_SEVEN_VIEW_SCAN_BUY"] = "1"
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
            if terminal_ok:
                close_reason = "cycle_completed"
            elif stop_event.is_set() or self._closed:
                close_reason = "operator_stop"
            else:
                close_reason = "cycle_failed"
            self._close_client(profile_id, close_reason)
