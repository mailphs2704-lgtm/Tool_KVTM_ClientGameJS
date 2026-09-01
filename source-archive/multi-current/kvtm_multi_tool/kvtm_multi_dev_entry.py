from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import subprocess
import time

import kvtm_multi as core
import kvtm_multi_entry as production


class MultiDevApp(production.MultiApp):
    """DEV-only shell for safe clear-stall live verification.

    Production scheduling remains implemented in kvtm_multi_entry.MultiApp.
    This subclass deliberately suppresses automatic clear-stall scheduling while
    a feature is being live-verified and adds a detached console that mirrors
    probe activity without becoming part of the probe execution path.
    """

    def _build_auto_panel(self) -> None:
        super()._build_auto_panel()
        self._clear_stall_probe_log_consoles: dict[str, subprocess.Popen] = {}
        self._clear_stall_probe_log_paths: dict[str, tuple[Path, Path]] = {}
        self._refresh_clear_stall_panel()

    def _poll_clear_stall_schedule(self) -> None:
        """Do not auto-start transaction-capable Dọn quầy jobs in Multi DEV."""
        if self._bridge_stop.is_set():
            return
        self.after(1000, self._poll_clear_stall_schedule)

    def _clear_stall_profile(self) -> tuple[str | None, dict | None]:
        """Resolve the selected profile, falling back to one running clone in DEV."""
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

    def _dev_probe_blocked(self, profile_id: str | None) -> bool:
        """Return True only when an automation worker really owns ClientJS."""
        if not profile_id:
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
        if any(
            self._worker_alive(w)
            for w in getattr(self, "_clear_stall_probe_workers", {}).values()
        ):
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

    @staticmethod
    def _extract_work_dir(worker) -> Path | None:
        args = getattr(worker, "args", None)
        if not isinstance(args, (list, tuple)):
            return None
        values = [str(item) for item in args]
        try:
            index = values.index("--work-dir")
            return Path(values[index + 1]).resolve()
        except (ValueError, IndexError, OSError):
            return None

    def _probe_log_paths_for_worker(
        self, profile_id: str, worker
    ) -> tuple[Path, Path] | None:
        cached = self._clear_stall_probe_log_paths.get(profile_id)
        if cached:
            return cached
        work_dir = self._extract_work_dir(worker)
        if work_dir is None:
            return None
        work_dir.mkdir(parents=True, exist_ok=True)
        paths = (work_dir / "activity.log", work_dir / ".probe-console-done")
        self._clear_stall_probe_log_paths[profile_id] = paths
        return paths

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
            summary = (
                "PASS   probe hoàn tất • "
                f"occupied={int(payload.get('occupied_new_total') or 0)}/20"
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

    def _open_probe_log_console(self, profile_id: str, worker) -> None:
        paths = self._probe_log_paths_for_worker(profile_id, worker)
        if paths is None or os.name != "nt":
            return
        log_path, done_path = paths
        try:
            done_path.unlink(missing_ok=True)
            log_path.touch(exist_ok=True)
        except OSError:
            return

        helper = core.TOOL_DIR / "clear_stall_probe_console.py"
        if not helper.is_file():
            return
        title = f"KVTM DEV - Don quay probe - {profile_id[:8]}"
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
                ["cmd.exe", "/c", command],
                cwd=str(core.TOOL_DIR),
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010),
            )
        except OSError:
            return
        self._clear_stall_probe_log_consoles[profile_id] = console

    def _launch_clear_stall_probe_worker(self, profile_id: str) -> None:
        """Launch the production read-only probe, then attach a DEV log console."""
        super()._launch_clear_stall_probe_worker(profile_id)
        worker = getattr(self, "_clear_stall_probe_workers", {}).get(profile_id)
        if self._worker_alive(worker):
            self._open_probe_log_console(profile_id, worker)

    def _read_clear_stall_probe_worker(self, profile_id: str, worker) -> None:
        """Mirror worker JSON to activity.log while preserving UI event handling."""
        paths = self._probe_log_paths_for_worker(profile_id, worker)
        log_path = paths[0] if paths else None
        done_path = paths[1] if paths else None
        log_stream = None
        try:
            if log_path is not None:
                log_stream = log_path.open("a", encoding="utf-8", errors="replace")
                log_stream.write(
                    "\n" + "=" * 78 + "\n"
                    + f"KVTM DEV CLEAR STALL PROBE • profile={profile_id}\n"
                    + f"started={time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    + "=" * 78 + "\n"
                )
                log_stream.flush()

            if worker.stdout:
                for line in worker.stdout:
                    raw_line = line.rstrip("\r\n")
                    if not raw_line:
                        continue
                    try:
                        payload = json.loads(raw_line)
                    except json.JSONDecodeError:
                        payload = {
                            "event": "probe_progress",
                            "message": raw_line,
                        }
                    payload["profile_id"] = profile_id
                    if log_stream is not None:
                        log_stream.write(self._activity_text(payload, raw_line))
                        log_stream.flush()
                    self.after(
                        0,
                        lambda data=dict(payload):
                        self._handle_clear_stall_probe_event(data),
                    )

            try:
                returncode = worker.wait(timeout=1.0)
            except Exception:
                returncode = -1
            exit_payload = {
                "event": "probe_exit",
                "profile_id": profile_id,
                "returncode": returncode,
            }
            if log_stream is not None:
                log_stream.write(
                    self._activity_text(
                        exit_payload,
                        json.dumps(exit_payload, ensure_ascii=False),
                    )
                )
                log_stream.write(
                    f"finished={time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                log_stream.flush()
            self.after(
                0,
                lambda data=exit_payload: self._handle_clear_stall_probe_event(data),
            )
        finally:
            if log_stream is not None:
                log_stream.close()
            if done_path is not None:
                try:
                    done_path.write_text("done\n", encoding="ascii")
                except OSError:
                    pass

    def _on_close(self) -> None:
        for _profile_id, paths in tuple(
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
