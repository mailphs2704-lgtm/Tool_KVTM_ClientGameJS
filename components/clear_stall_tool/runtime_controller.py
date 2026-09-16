from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Callable

try:
    from .profile_store import ProfileStore
except ImportError:
    from profile_store import ProfileStore

EventCallback = Callable[[str, str, dict], None]
DEFAULT_CLIENT = Path(r"C:\Program Files\ZingPlay\data\flutter_assets\assets\runtime\GameClientJS.exe")
DEFAULT_GAME = Path(os.environ.get("APPDATA", Path.home())) / "VNG Corporation" / "ZingPlay" / "zpp" / "24" / "game"

class RuntimeLayoutError(RuntimeError):
    pass

class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

def _blob(data: bytes):
    buffer = ctypes.create_string_buffer(data)
    return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer

def _unprotect(value: str) -> bytes:
    if os.name != "nt":
        raise RuntimeError("DPAPI profile chỉ chạy trên Windows")
    source, source_buffer = _blob(base64.b64decode(value))
    entropy, entropy_buffer = _blob(b"KVTM-MULTI-v1")
    result = _DataBlob()
    ok = ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(source), None, ctypes.byref(entropy), None, None, 0x01, ctypes.byref(result))
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(result.pbData)
        del source_buffer, entropy_buffer

class RuntimePaths:
    def __init__(self, source_root: Path) -> None:
        self.source_root = Path(source_root).resolve()
        self.runtime_root = self._discover_runtime_root()
        self.multi_dir = self.runtime_root / "Multi"
        self.worker_dir = self.runtime_root / "components" / "clientjs-auto" / "worker"
        self.auto_root = self.runtime_root / "AUTO_PRO"
        for required in (self.multi_dir / "client_ownership_integration.py", self.worker_dir / "clear_stall_probe_runtime.py", self.auto_root / "engine_driver.py", self.auto_root / "bin" / "kvtm_loader_v3.exe", self.auto_root / "bin" / "kvtm_bridge_v3.dll"):
            if not required.exists():
                raise RuntimeLayoutError(f"Runtime AUTO MULTI DEV thiếu {required.name}. Hãy build Multi DEV bằng Control Center [1].")

    def _discover_runtime_root(self) -> Path:
        candidates: list[Path] = []
        configured = os.environ.get("KVTM_MULTI_DEV_RUNTIME")
        if configured:
            candidates.append(Path(configured))
        candidates.append(self.source_root / "dist" / "KVTM-ClientJS-Suite-Multi-DEV")
        candidates.append(self.source_root.parent / "Tool_KVTM_Multi_DEV" / "dist" / "KVTM-ClientJS-Suite-Multi-DEV")
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            result = subprocess.run(["git", "-C", str(self.source_root), "worktree", "list", "--porcelain"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10, creationflags=flags)
            for line in result.stdout.splitlines():
                if line.startswith("worktree "):
                    root = Path(line[len("worktree "):].strip())
                    candidates.append(root / "dist" / "KVTM-ClientJS-Suite-Multi-DEV")
        except Exception:
            pass
        seen: set[str] = set()
        for candidate in candidates:
            key = os.path.normcase(str(candidate.resolve()))
            if key in seen:
                continue
            seen.add(key)
            if ((candidate / "Multi" / "kvtm_multi_dev_entry.py").is_file() and (candidate / "components" / "clientjs-auto" / "worker" / "clear_stall_probe_runtime.py").is_file() and (candidate / "AUTO_PRO").is_dir()):
                return candidate.resolve()
        raise RuntimeLayoutError("Không tìm thấy runtime AUTO MULTI DEV. Hãy chạy KVTM_DEV_CONTROL.bat -> [1] ở D:\\Tool_KVTM_Multi_DEV.")

class ClearStallController:
    MAX_CONCURRENCY = 2

    def __init__(self, root, store: ProfileStore, callback: EventCallback) -> None:
        self.root = root
        self.store = store
        self.callback = callback
        self.paths = RuntimePaths(Path(__file__).resolve().parents[2])
        self._enabled: set[str] = set()
        self._stop_events: dict[str, threading.Event] = {}
        self._workers: dict[str, subprocess.Popen] = {}
        self._clients: dict[str, subprocess.Popen] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._semaphore = threading.Semaphore(self.MAX_CONCURRENCY)
        self._closed = False
        self._ownership_registry = self._load_ownership_registry()

    def _load_ownership_registry(self):
        text = str(self.paths.multi_dir)
        if text not in sys.path:
            sys.path.insert(0, text)
        from client_ownership_integration import ClientOwnershipRegistry
        return ClientOwnershipRegistry(owner="DEV", instance="KVTM Dọn Quầy")

    def _emit(self, profile_id: str, event: str, **data) -> None:
        try:
            self.root.after(0, lambda: self.callback(str(profile_id), str(event), dict(data)))
        except Exception:
            pass

    def enabled(self, profile_id: str) -> bool:
        return str(profile_id) in self._enabled

    def start(self, profile_id: str) -> None:
        pid = str(profile_id or "")
        if not pid or self._closed or pid in self._enabled:
            return
        if self.store.profile(pid) is None:
            self._emit(pid, "error", message="Profile không còn trong profiles.json của Dọn quầy")
            return
        self._enabled.add(pid)
        stop_event = threading.Event()
        self._stop_events[pid] = stop_event
        self._emit(pid, "running", message="Đã bật lịch Dọn quầy")
        thread = threading.Thread(target=self._schedule_loop, args=(pid, stop_event), name=f"kvtm-clear-stall-{pid[:8]}", daemon=True)
        self._threads[pid] = thread
        thread.start()

    def stop(self, profile_id: str) -> None:
        pid = str(profile_id or "")
        self._enabled.discard(pid)
        event = self._stop_events.get(pid)
        if event:
            event.set()
        worker = self._workers.get(pid)
        if worker and worker.poll() is None and worker.stdin:
            try:
                worker.stdin.write(json.dumps({"command": "stop"}) + "\n")
                worker.stdin.flush()
            except OSError:
                pass
        self._emit(pid, "stopped", message="Đã dừng Dọn quầy")

    def stop_all(self) -> None:
        for pid in list(self._enabled | set(self._workers)):
            self.stop(pid)

    def close(self) -> None:
        self._closed = True
        self.stop_all()

    def _schedule_loop(self, profile_id: str, stop_event: threading.Event) -> None:
        first = True
        while not stop_event.is_set() and profile_id in self._enabled and not self._closed:
            if not first:
                interval = int(self.store.ensure_job(profile_id).get("interval_minutes", 65))
                if stop_event.wait(max(5, interval) * 60):
                    break
            first = False
            if stop_event.is_set() or profile_id not in self._enabled:
                break
            with self._semaphore:
                if stop_event.is_set() or profile_id not in self._enabled:
                    break
                try:
                    self._run_once(profile_id, stop_event)
                except Exception as exc:
                    self._emit(profile_id, "cycle_error", message=str(exc))
        self._emit(profile_id, "stopped", message="Dọn quầy đã dừng")

    def _identity_busy(self, profile: dict) -> dict | None:
        return self._ownership_registry.lookup_identity(str(profile.get("id") or ""), "", str(profile.get("name") or profile.get("id") or ""))

    def _launch_client(self, profile: dict) -> subprocess.Popen:
        existing = self._identity_busy(profile)
        if existing:
            raise RuntimeError(f"Tài khoản đang được {existing.get('instance') or existing.get('owner')} sử dụng (PID {existing.get('pid')}); Dọn quầy không giành quyền điều khiển.")
        client = Path(profile.get("client") or DEFAULT_CLIENT)
        game_dir = Path(profile.get("game_dir") or DEFAULT_GAME)
        if not client.is_file():
            raise FileNotFoundError(f"Không thấy GameClientJS.exe: {client}")
        if not game_dir.is_dir():
            raise FileNotFoundError(f"Không thấy dữ liệu KVTM: {game_dir}")
        secret = profile.get("secret")
        if not secret:
            raise RuntimeError("Profile thiếu secret đăng nhập đã mã hóa")
        secret_args = json.loads(_unprotect(str(secret)).decode("utf-8"))
        if not isinstance(secret_args, list):
            raise RuntimeError("Profile secret không phải danh sách launch args")
        proc = subprocess.Popen([str(client), str(game_dir), *map(str, secret_args)], cwd=str(game_dir))
        try:
            self._ownership_registry.claim(proc.pid, str(profile.get("id") or ""), f"standalone:{profile.get('id')}", str(profile.get("name") or profile.get("id") or ""))
        except Exception:
            try:
                proc.terminate()
            except OSError:
                pass
            raise
        return proc

    def _resize_client(self, pid: int, stop_event: threading.Event) -> None:
        auto_text = str(self.paths.auto_root)
        if auto_text not in sys.path:
            sys.path.insert(0, auto_text)
        from pc_driver import find_window
        deadline = time.monotonic() + 25.0
        hwnd = 0
        while time.monotonic() < deadline and not stop_event.is_set():
            hwnd = int(find_window(int(pid)) or 0)
            if hwnd:
                break
            time.sleep(0.10)
        if not hwnd:
            raise RuntimeError("ClientJS đã mở nhưng chưa tìm thấy cửa sổ để chuẩn hóa 1000x1000")
        rect = wintypes.RECT(0, 0, 1000, 1000)
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -16)
        ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        ctypes.windll.user32.AdjustWindowRectEx(ctypes.byref(rect), style, False, ex_style)
        width, height = rect.right - rect.left, rect.bottom - rect.top
        if not ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, width, height, 0x0002 | 0x0004 | 0x0040):
            raise ctypes.WinError()

    def _run_once(self, profile_id: str, stop_event: threading.Event) -> None:
        profile = self.store.profile(profile_id)
        if profile is None:
            raise RuntimeError("Profile đã bị xóa khỏi snapshot Dọn quầy")
        job = self.store.ensure_job(profile_id)
        quantity = int(job.get("buy_quantity", 10))
        if quantity % 10 or not 10 <= quantity <= 1000:
            raise RuntimeError("Số lượng Dọn quầy phải là bội số 10 trong 10..1000")
        self._emit(profile_id, "cycle_start", message="Đang mở ClientJS cho Dọn quầy")
        proc = self._launch_client(profile)
        self._clients[profile_id] = proc
        try:
            self._resize_client(proc.pid, stop_event)
            if stop_event.wait(2.5):
                return
            run_id = time.strftime("%Y%m%d-%H%M%S")
            work_dir = self.store.app_dir / "runs" / profile_id / run_id
            work_dir.mkdir(parents=True, exist_ok=True)
            worker_file = Path(__file__).resolve().parent / "standalone_clear_stall_worker.py"
            allowed = list(job.get("allowed_item_ids") or [])
            args = [sys.executable, str(worker_file), "--runtime-root", str(self.paths.runtime_root), "--profile-file", str(self.store.profile_file), "--pid", str(proc.pid), "--profile-id", profile_id, "--profile-name", str(profile.get("name") or profile_id), "--friend-ordinal", str(int(job.get("target_friend_ordinal", 1))), "--stall-id", str(int(job.get("target_stall_id", 2))), "--quantity", str(quantity), "--max-stall-passes", str(int(job.get("max_scan_pages", 10))), "--allowed-items-json", json.dumps(allowed, ensure_ascii=True), "--drag-speed", str(float(job.get("clear_stall_drag_speed", 0.35))), "--work-dir", str(work_dir)]
            env = os.environ.copy()
            env["KVTM_MULTI_PROFILE_FILE"] = str(self.store.profile_file)
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            worker = subprocess.Popen(args, cwd=str(self.paths.auto_root), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1, creationflags=flags, env=env)
            self._workers[profile_id] = worker
            terminal_ok = False
            if worker.stdout:
                for raw_line in worker.stdout:
                    if stop_event.is_set() and worker.poll() is None and worker.stdin:
                        try:
                            worker.stdin.write(json.dumps({"command": "stop"}) + "\n")
                            worker.stdin.flush()
                        except OSError:
                            pass
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        payload = {"event": "probe_progress", "message": line}
                    event = str(payload.get("event") or "")
                    message = str(payload.get("message") or payload.get("error") or "")
                    if event in {"probe_progress", "probe_boot"} and message:
                        self._emit(profile_id, "progress", message=message)
                    elif event == "probe_ok":
                        terminal_ok = True
                        self._emit(profile_id, "progress", message="Dọn quầy hoàn tất")
                    elif event == "probe_error":
                        self._emit(profile_id, "progress", message=message or "Dọn quầy lỗi")
            rc = worker.wait()
            if stop_event.is_set():
                return
            if rc != 0:
                raise RuntimeError(f"Worker Dọn quầy kết thúc mã {rc}")
            if not terminal_ok:
                raise RuntimeError("Worker Dọn quầy đã thoát nhưng chưa phát bằng chứng probe_ok; không ghi nhận hoàn tất.")
            stamp = time.strftime("%H:%M %d/%m/%Y")
            self.store.mark_clean(profile_id, stamp)
            self._emit(profile_id, "cycle_done", message="Dọn quầy hoàn tất", last_clean=stamp)
        finally:
            self._workers.pop(profile_id, None)
            client = self._clients.pop(profile_id, None)
            if client is not None and client.poll() is None:
                try:
                    client.terminate()
                    client.wait(timeout=5)
                except Exception:
                    try:
                        client.kill()
                    except OSError:
                        pass
