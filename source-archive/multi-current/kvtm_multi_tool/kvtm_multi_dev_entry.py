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
        self._clear_stall_probe_starting: set[str] = set()
        self._clear_stall_probe_terminal: dict[str, str] = {}
        super()._build_auto_panel()
        self._refresh_clear_stall_panel()

    def _poll_clear_stall_schedule(self) -> None:
        """Never auto-start transaction-capable Dọn quầy jobs in Multi DEV."""
        if self._bridge_stop.is_set():
            return
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
        if not profile_id:
            return True
        if self._probe_thread_alive(profile_id):
            return True
        auto_worker = self._auto_workers.get(profile_id)
        if self._worker_alive(auto_worker):
            return True
        if tuple(self._clear_stall_starting):
            return True
        if tuple(getattr(self, "_clear_stall_probe_starting", ())):
            return True
        if any(self._worker_alive(w) for w in self._clear_stall_workers.values()):
            return True
        return False

    def _refresh_clear_stall_panel(self) -> None:
        super()._refresh_clear_stall_panel()
        if not hasattr(self, "auto_clear_stall_probe_button"):
            return
        profile_id, profile = self._clear_stall_profile()
        self.auto_clear_stall_probe_button.configure(
            state=(
                "normal"
                if profile and not self._dev_probe_blocked(profile_id)
                else "disabled"
            )
        )

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
        elif event == "probe_ok":
            summary = f"PASS   probe hoàn tất • occupied={int(payload.get('occupied_new_total') or 0)}/20"
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
        # Keep diagnostics silent/background. The user sends them later
        # through the single Control Center BAT; no extra CMD is opened here.
        self._append_probe_log(profile_id, "BUTTON ✓ Kiểm tra Dọn quầy")
        self._append_probe_log(profile_id, "runtime_mode=IN_PROCESS_RESIDENT")
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
        try:
            paths[1].write_text("done\n", encoding="ascii")
        except OSError:
            pass

    def _start_clear_stall_probe(self) -> None:
        """Launch clone, then run the read-only probe inside this resident process."""
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
        run_id = time.strftime("%Y%m%d-%H%M%S")
        work_dir = core.APP_DIR / "clear-stall-probe" / profile_id / run_id
        stop_event = threading.Event()
        self._dev_probe_stop_events[profile_id] = stop_event
        self._clear_stall_probe_terminal.pop(profile_id, None)
        self._clear_stall_probe_starting.discard(profile_id)

        thread = threading.Thread(
            target=self._run_probe_thread,
            args=(profile_id, profile, int(proc.pid), friend, storage, work_dir, stop_event),
            name=f"kvtm-dev-clear-stall-probe-{profile_id[:8]}",
            daemon=True,
        )
        self._dev_probe_threads[profile_id] = thread
        self._append_probe_log(
            profile_id,
            f"probe_thread_start pid={proc.pid} report_dir={work_dir}",
        )
        self.auto_clear_stall_status.set(
            f"Kiểm tra resident • Nhà bạn {friend} • Kho VP {storage}"
        )
        thread.start()
        self._refresh_clear_stall_panel()

    def _run_probe_thread(
        self,
        profile_id: str,
        profile: dict,
        pid: int,
        friend: int,
        storage: int,
        work_dir: Path,
        stop_event: threading.Event,
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
                work_dir=work_dir,
            )

            def sink(payload: dict) -> None:
                data = dict(payload)
                data["profile_id"] = profile_id
                self._append_probe_event(profile_id, data)
                self.after(
                    0,
                    lambda event_data=dict(data): self._handle_clear_stall_probe_event(event_data),
                )

            sink({
                "event": "probe_progress",
                "message": "Resident runtime đã sẵn sàng; probe không import native lần hai",
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

    def _handle_clear_stall_probe_event(self, payload: dict) -> None:
        profile_id = str(payload.get("profile_id") or "")
        event = str(payload.get("event") or "")
        message = str(payload.get("message") or "")
        stage = str(payload.get("stage") or "")
        if event == "probe_boot":
            self._set_clear_stall_checkpoint(
                profile_id, f"GATE 1 • {stage or 'đang khởi tạo'}"
            )
        elif event == "probe_progress":
            self._set_clear_stall_checkpoint(
                profile_id, message or stage or "GATE 1 đang chạy"
            )
        elif event == "probe_ok":
            occupied = int(payload.get("occupied_new_total") or 0)
            planned = int(payload.get("planned_quantity") or 0)
            requested = int(payload.get("requested_quantity") or 0)
            reached = bool(payload.get("target_reached", False))
            summary = (
                f"GATE 1 PASS • {occupied}/20 ô có VP • "
                f"kế hoạch {planned}/{requested} • "
                f"target {'ĐỦ' if reached else 'THIẾU'}"
            )
            self._clear_stall_probe_terminal[profile_id] = "PASS"
            self._set_clear_stall_checkpoint(
                profile_id,
                summary,
                {
                    "ok": True,
                    "probe_only": True,
                    "occupied": occupied,
                    "planned_quantity": planned,
                    "requested_quantity": requested,
                    "target_reached": reached,
                    "report": str(payload.get("report") or ""),
                },
            )
        elif event == "probe_stopped":
            self._clear_stall_probe_terminal[profile_id] = "STOPPED"
            self._set_clear_stall_checkpoint(profile_id, "GATE 1 đã dừng an toàn")
        elif event == "probe_error":
            error = str(payload.get("error") or "Lỗi probe không xác định")
            self._clear_stall_probe_terminal[profile_id] = "FAIL"
            self._set_clear_stall_checkpoint(
                profile_id,
                "GATE 1 FAIL",
                {
                    "ok": False,
                    "probe_only": True,
                    "error": error,
                    "report": str(payload.get("report") or ""),
                },
            )
            if profile_id == self._active_profile_id:
                core.messagebox.showerror(core.APP_NAME, f"GATE 1 lỗi:\n{error}")
        elif event == "probe_exit":
            if profile_id not in self._clear_stall_probe_terminal:
                code = int(payload.get("returncode") or 0)
                self._clear_stall_probe_terminal[profile_id] = (
                    "PASS" if code == 0 else "FAIL"
                )

    def _finish_inprocess_probe(self, payload: dict) -> None:
        profile_id = str(payload.get("profile_id") or "")
        self._dev_probe_threads.pop(profile_id, None)
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
