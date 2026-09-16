from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


__all__ = ["start_runtime_diagnostic"]

_LOG_LIMIT_BYTES = 8 * 1024 * 1024
_SAMPLE_SECONDS = 2.0
_HEARTBEAT_SECONDS = 10.0
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010
STILL_ACTIVE = 259


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _append(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size >= _LOG_LIMIT_BYTES:
        rotated = path.with_name(path.stem + "-previous" + path.suffix)
        try:
            if rotated.exists():
                rotated.unlink()
            os.replace(path, rotated)
        except OSError:
            pass
    record = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), **payload}
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def _process_snapshot(pid: int) -> dict:
    kernel32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    handle = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, int(pid)
    )
    if not handle:
        return {"alive": False}
    try:
        exit_code = wintypes.DWORD()
        alive = bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)))
        alive = alive and int(exit_code.value) == STILL_ACTIVE
        if not alive:
            return {"alive": False, "exit_code": int(exit_code.value)}

        memory = PROCESS_MEMORY_COUNTERS()
        memory.cb = ctypes.sizeof(memory)
        memory_ok = bool(
            psapi.GetProcessMemoryInfo(
                handle, ctypes.byref(memory), ctypes.sizeof(memory)
            )
        )
        handle_count = wintypes.DWORD()
        handles_ok = bool(
            kernel32.GetProcessHandleCount(handle, ctypes.byref(handle_count))
        )
        creation = wintypes.FILETIME()
        exit_time = wintypes.FILETIME()
        kernel = wintypes.FILETIME()
        user = wintypes.FILETIME()
        times_ok = bool(
            kernel32.GetProcessTimes(
                handle,
                ctypes.byref(creation),
                ctypes.byref(exit_time),
                ctypes.byref(kernel),
                ctypes.byref(user),
            )
        )

        def filetime_value(value) -> int:
            return (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)

        result = {"alive": True}
        if memory_ok:
            result["working_set_mb"] = round(memory.WorkingSetSize / 1048576.0, 1)
            result["private_mb"] = round(memory.PagefileUsage / 1048576.0, 1)
        if handles_ok:
            result["handles"] = int(handle_count.value)
        if times_ok:
            result["cpu_seconds"] = round(
                (filetime_value(kernel) + filetime_value(user)) / 10_000_000.0,
                2,
            )
        return result
    finally:
        kernel32.CloseHandle(handle)


def _window_state(pid: int) -> dict:
    user32 = ctypes.windll.user32
    windows = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def callback(hwnd, _lparam):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if int(owner.value) == int(pid) and user32.IsWindowVisible(hwnd):
            windows.append(int(hwnd))
        return True

    user32.EnumWindows(callback, 0)
    hung = any(bool(user32.IsHungAppWindow(hwnd)) for hwnd in windows)
    return {"visible_windows": len(windows), "responding": not hung}


def _client_pids(data_root: Path) -> list[int]:
    path = data_root / "running_clients.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        clients = raw.get("clients", []) if isinstance(raw, dict) else []
    except (FileNotFoundError, OSError, ValueError, TypeError):
        return []
    result = []
    for item in clients:
        if not isinstance(item, dict):
            continue
        try:
            pid = int(item.get("pid") or 0)
        except (TypeError, ValueError):
            continue
        if pid > 0 and pid not in result:
            result.append(pid)
    return result


def _monitor(parent_pid: int, data_root: Path, product: str) -> int:
    diagnostic_root = data_root / "diagnostics"
    log_path = diagnostic_root / "runtime-diagnostic-current.jsonl"
    pointer_path = diagnostic_root / "LATEST.txt"
    diagnostic_root.mkdir(parents=True, exist_ok=True)
    pointer_path.write_text(str(log_path), encoding="utf-8")
    _append(
        log_path,
        {
            "event": "diagnostic_started",
            "product": product,
            "monitor_pid": os.getpid(),
            "multi_pid": int(parent_pid),
            "policy": "no-command-line,no-profile-content,no-token",
        },
    )
    previous_state = None
    last_heartbeat = 0.0
    previous_cpu = None
    previous_sample_at = None
    while True:
        started = time.monotonic()
        multi = _process_snapshot(parent_pid)
        if not multi.get("alive"):
            _append(
                log_path,
                {"event": "multi_exited", "multi_pid": int(parent_pid), **multi},
            )
            return 0
        multi.update(_window_state(parent_pid))
        now = time.monotonic()
        cpu_total = multi.get("cpu_seconds")
        if isinstance(cpu_total, (int, float)) and previous_cpu is not None:
            elapsed = max(0.001, now - float(previous_sample_at))
            multi["cpu_percent_one_core"] = round(
                max(0.0, float(cpu_total) - float(previous_cpu)) * 100.0 / elapsed,
                1,
            )
        previous_cpu = cpu_total
        previous_sample_at = now

        client_rows = []
        for pid in _client_pids(data_root):
            snapshot = _process_snapshot(pid)
            if snapshot.get("alive"):
                snapshot.update(_window_state(pid))
            client_rows.append(snapshot)
        client_summary = {
            "total": len(client_rows),
            "alive": sum(1 for row in client_rows if row.get("alive")),
            "not_responding": sum(
                1 for row in client_rows
                if row.get("alive") and not row.get("responding", True)
            ),
            "working_set_mb": round(
                sum(float(row.get("working_set_mb", 0.0)) for row in client_rows),
                1,
            ),
        }
        state = (
            bool(multi.get("responding", True)),
            client_summary["alive"],
            client_summary["not_responding"],
        )
        event = None
        if previous_state is not None and state != previous_state:
            event = "state_changed"
        if not multi.get("responding", True):
            event = "multi_not_responding"
        if event or now - last_heartbeat >= _HEARTBEAT_SECONDS:
            _append(
                log_path,
                {
                    "event": event or "heartbeat",
                    "product": product,
                    "multi_pid": int(parent_pid),
                    "multi": multi,
                    "clientjs": client_summary,
                    "disk_free_mb": round(
                        shutil.disk_usage(data_root).free / 1048576.0, 1
                    ),
                    "sample_lag_ms": round(
                        max(0.0, time.monotonic() - started) * 1000.0, 1
                    ),
                },
            )
            last_heartbeat = now
        previous_state = state
        time.sleep(_SAMPLE_SECONDS)


def start_runtime_diagnostic(data_root: Path, product: str) -> subprocess.Popen | None:
    if os.name != "nt":
        return None
    flags = (
        getattr(subprocess, "CREATE_NO_WINDOW", 0)
        | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
    )
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--monitor",
            str(os.getpid()),
            str(Path(data_root).resolve()),
            str(product),
        ],
        cwd=str(Path(__file__).resolve().parent),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )


if __name__ == "__main__":
    if len(sys.argv) != 5 or sys.argv[1] != "--monitor":
        raise SystemExit(2)
    raise SystemExit(_monitor(int(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]))
