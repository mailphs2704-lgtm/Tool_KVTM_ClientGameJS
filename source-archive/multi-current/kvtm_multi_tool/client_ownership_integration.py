from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import time
import uuid


OWNER_ENV = "KVTM_CLIENT_OWNER"
OWNER_DEV = "DEV"
OWNER_CRY = "CRY"
REGISTRY_SCHEMA = 1
REGISTRY_DIR = Path(os.environ.get("APPDATA", Path.home())) / "KVTM Client Ownership"
REGISTRY_FILE = REGISTRY_DIR / "clients.json"
MUTEX_NAME = r"Local\KVTM_Client_Ownership_v1"
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
WAIT_OBJECT_0 = 0x00000000
WAIT_ABANDONED = 0x00000080


class OwnershipError(RuntimeError):
    pass


class ForeignOwnershipError(OwnershipError):
    pass


class _FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", wintypes.DWORD),
        ("dwHighDateTime", wintypes.DWORD),
    ]


def current_owner() -> str:
    configured = str(os.environ.get(OWNER_ENV) or "").strip().upper()
    if configured in {OWNER_DEV, OWNER_CRY}:
        return configured
    channel = str(os.environ.get("KVTM_PRODUCT_CHANNEL") or "").strip().lower()
    return OWNER_CRY if channel == "stable" else OWNER_DEV


def _creation_token(pid: int) -> str | None:
    if os.name != "nt" or int(pid) <= 0:
        return None
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return None
    try:
        created = _FILETIME()
        exited = _FILETIME()
        kernel = _FILETIME()
        user = _FILETIME()
        ok = kernel32.GetProcessTimes(
            handle,
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(kernel),
            ctypes.byref(user),
        )
        if not ok:
            return None
        value = (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)
        return f"{value:016x}"
    finally:
        kernel32.CloseHandle(handle)


class _NamedMutex:
    def __init__(self, name: str = MUTEX_NAME, timeout_ms: int = 5000):
        self.name = str(name)
        self.timeout_ms = int(timeout_ms)
        self.handle = None

    def __enter__(self):
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        self.handle = kernel32.CreateMutexW(None, False, self.name)
        if not self.handle:
            raise ctypes.WinError()
        result = kernel32.WaitForSingleObject(self.handle, self.timeout_ms)
        if result not in (WAIT_OBJECT_0, WAIT_ABANDONED):
            kernel32.CloseHandle(self.handle)
            self.handle = None
            raise OwnershipError("Timeout waiting for ClientJS ownership registry lock")
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.handle:
            kernel32 = ctypes.windll.kernel32
            kernel32.ReleaseMutex(self.handle)
            kernel32.CloseHandle(self.handle)
            self.handle = None


class ClientOwnershipRegistry:
    """Cross-tool ownership for ClientJS processes; metadata only, never secrets."""

    def __init__(self, owner: str | None = None, instance: str | None = None):
        self.owner = str(owner or current_owner()).strip().upper()
        if self.owner not in {OWNER_DEV, OWNER_CRY}:
            raise OwnershipError(f"Unsupported ClientJS owner: {self.owner}")
        self.instance = str(
            instance
            or os.environ.get("KVTM_MULTI_INSTANCE_NAME")
            or ("Kvtm_tool_Cry" if self.owner == OWNER_CRY else "KVTM Multi DEV")
        )

    @staticmethod
    def process_creation_token(pid: int) -> str | None:
        return _creation_token(int(pid))

    def _read_unlocked(self) -> dict:
        if not REGISTRY_FILE.is_file():
            return {"schema": REGISTRY_SCHEMA, "clients": []}
        try:
            payload = json.loads(REGISTRY_FILE.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            raise OwnershipError(f"ClientJS ownership registry is unreadable: {exc}") from exc
        if not isinstance(payload, dict) or int(payload.get("schema") or 0) != REGISTRY_SCHEMA:
            raise OwnershipError("ClientJS ownership registry schema is invalid")
        clients = payload.get("clients")
        if not isinstance(clients, list):
            raise OwnershipError("ClientJS ownership registry clients list is invalid")
        return {"schema": REGISTRY_SCHEMA, "clients": clients}

    def _write_unlocked(self, clients: list[dict]) -> None:
        REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": REGISTRY_SCHEMA,
            "updated_at": time.time(),
            "clients": clients,
        }
        temp = REGISTRY_DIR / (
            f".{REGISTRY_FILE.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        )
        try:
            temp.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temp, REGISTRY_FILE)
        finally:
            try:
                if temp.exists():
                    temp.unlink()
            except OSError:
                pass

    @staticmethod
    def _normalized(entry: dict) -> dict | None:
        if not isinstance(entry, dict):
            return None
        try:
            pid = int(entry.get("pid") or 0)
        except (TypeError, ValueError):
            return None
        creation_token = str(entry.get("creation_token") or "")
        profile_id = str(entry.get("profile_id") or "")
        owner = str(entry.get("owner") or "").upper()
        if pid <= 0 or not creation_token or not profile_id or owner not in {OWNER_DEV, OWNER_CRY}:
            return None
        return {
            "pid": pid,
            "creation_token": creation_token,
            "profile_id": profile_id,
            "account_name": str(entry.get("account_name") or profile_id),
            "owner": owner,
            "instance": str(entry.get("instance") or owner),
            "claimed_at": float(entry.get("claimed_at") or 0.0),
        }

    def _prune(self, clients: list[dict]) -> tuple[list[dict], bool]:
        kept: list[dict] = []
        changed = False
        seen_pids: set[int] = set()
        seen_profiles: set[str] = set()
        for raw in clients:
            entry = self._normalized(raw)
            if entry is None:
                changed = True
                continue
            token = _creation_token(entry["pid"])
            if token is None or token != entry["creation_token"]:
                changed = True
                continue
            if entry["pid"] in seen_pids or entry["profile_id"] in seen_profiles:
                changed = True
                continue
            seen_pids.add(entry["pid"])
            seen_profiles.add(entry["profile_id"])
            kept.append(entry)
        return kept, changed

    def snapshot(self) -> list[dict]:
        with _NamedMutex():
            payload = self._read_unlocked()
            clients, changed = self._prune(payload["clients"])
            if changed:
                self._write_unlocked(clients)
            return [dict(item) for item in clients]

    def lookup_profile(self, profile_id: str) -> dict | None:
        wanted = str(profile_id or "")
        return next(
            (item for item in self.snapshot() if item["profile_id"] == wanted),
            None,
        )

    def lookup_pid(self, pid: int) -> dict | None:
        wanted = int(pid)
        return next((item for item in self.snapshot() if item["pid"] == wanted), None)

    def claim(
        self,
        pid: int,
        profile_id: str,
        account_name: str,
        *,
        replace_pid: int | None = None,
    ) -> dict:
        pid = int(pid)
        profile_id = str(profile_id or "")
        if pid <= 0 or not profile_id:
            raise OwnershipError("Cannot claim ClientJS without pid/profile_id")
        token = _creation_token(pid)
        if token is None:
            raise OwnershipError(f"ClientJS PID {pid} is not alive")

        with _NamedMutex():
            payload = self._read_unlocked()
            clients, _changed = self._prune(payload["clients"])

            if replace_pid:
                old_pid = int(replace_pid)
                retained: list[dict] = []
                for item in clients:
                    if item["pid"] == old_pid or item["profile_id"] == profile_id:
                        if item["owner"] != self.owner:
                            raise ForeignOwnershipError(
                                f"{account_name} đang thuộc {item['owner']}"
                            )
                        continue
                    retained.append(item)
                clients = retained

            for item in clients:
                same_pid = item["pid"] == pid
                same_profile = item["profile_id"] == profile_id
                if not (same_pid or same_profile):
                    continue
                if (
                    item["owner"] == self.owner
                    and same_pid
                    and same_profile
                    and item["creation_token"] == token
                ):
                    item["account_name"] = str(account_name or profile_id)
                    item["instance"] = self.instance
                    self._write_unlocked(clients)
                    return dict(item)
                raise ForeignOwnershipError(
                    f"{account_name} đang chạy bởi {item['owner']} "
                    f"(PID {item['pid']})"
                )

            entry = {
                "pid": pid,
                "creation_token": token,
                "profile_id": profile_id,
                "account_name": str(account_name or profile_id),
                "owner": self.owner,
                "instance": self.instance,
                "claimed_at": time.time(),
            }
            clients.append(entry)
            self._write_unlocked(clients)
            return dict(entry)

    def release_dead(self) -> None:
        self.snapshot()

    def self_owned(self, pid: int, profile_id: str | None = None) -> bool:
        entry = self.lookup_pid(int(pid))
        if not entry or entry["owner"] != self.owner:
            return False
        return profile_id is None or entry["profile_id"] == str(profile_id)

    @staticmethod
    def set_window_title(pid: int, title: str) -> bool:
        if os.name != "nt" or int(pid) <= 0:
            return False
        user32 = ctypes.windll.user32
        found = {"value": False}
        target_pid = int(pid)
        safe_title = str(title or "").strip()
        if not safe_title:
            return False

        enum_proc_type = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
        )

        @enum_proc_type
        def callback(hwnd, _lparam):
            window_pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
            if int(window_pid.value) != target_pid:
                return True
            if not user32.IsWindowVisible(hwnd):
                return True
            if int(user32.GetWindowTextLengthW(hwnd)) <= 0:
                return True
            if user32.SetWindowTextW(hwnd, safe_title):
                found["value"] = True
            return True

        user32.EnumWindows(callback, 0)
        return bool(found["value"])


def install_client_ownership_integration(app_cls, core) -> None:
    """Install one-owner ClientJS policy around the existing Multi lifecycle."""

    if getattr(app_cls, "_client_ownership_integration_installed", False):
        return

    registry = ClientOwnershipRegistry()
    original_init = app_cls.__init__
    original_refresh = app_cls.refresh
    original_adopt = app_cls._adopt_running_clients
    original_launch = app_cls._launch
    original_stop_selected = app_cls.stop_selected
    original_worker_event = getattr(app_cls, "_handle_auto_worker_event", None)

    def profile_for(self, profile_id: str) -> dict | None:
        wanted = str(profile_id or "")
        return next(
            (
                profile
                for profile in self.profiles
                if str(profile.get("id") or "") == wanted
            ),
            None,
        )

    def account_name(self, profile_id: str) -> str:
        profile = profile_for(self, profile_id)
        return str((profile or {}).get("name") or profile_id)

    def schedule_title(self, profile_id: str, pid: int, attempt: int = 0) -> None:
        try:
            entry = registry.lookup_pid(int(pid))
        except OwnershipError:
            return
        if not entry or entry["owner"] != registry.owner:
            return
        if registry.set_window_title(int(pid), account_name(self, profile_id)):
            return
        if attempt < 20:
            self.after(
                500,
                lambda p=str(profile_id), n=int(pid), a=attempt + 1:
                    schedule_title(self, p, n, a),
            )

    def decorate_rows(self) -> None:
        try:
            by_profile = {item["profile_id"]: item for item in registry.snapshot()}
        except OwnershipError as exc:
            self.note.set(f"ClientJS ownership registry lỗi: {exc}")
            return

        profiles = {
            str(profile.get("id") or ""): profile for profile in self.profiles
        }
        for profile_id, profile in profiles.items():
            entry = by_profile.get(profile_id)
            if not entry:
                continue

            if self.offline_tree.exists(profile_id):
                icon = self.offline_tree.item(profile_id, "text")
                was_selected = profile_id in self.offline_tree.selection()
                self.offline_tree.delete(profile_id)
                self.online_tree.insert(
                    "",
                    "end",
                    iid=profile_id,
                    text=icon,
                    values=(
                        str(profile.get("name") or "Chưa đặt tên"),
                        f"{entry['pid']} • ONL • {entry['owner']}",
                    ),
                )
                if was_selected:
                    self.online_tree.selection_set(profile_id)
            elif self.online_tree.exists(profile_id):
                self.online_tree.item(
                    profile_id,
                    values=(
                        str(profile.get("name") or "Chưa đặt tên"),
                        f"{entry['pid']} • ONL • {entry['owner']}",
                    ),
                )

            if entry["owner"] == registry.owner:
                schedule_title(self, profile_id, int(entry["pid"]))

    def ownership_refresh(self) -> None:
        original_refresh(self)
        decorate_rows(self)

    def ownership_adopt(self, rows: list[dict]) -> None:
        try:
            owned_pids = {
                int(item["pid"])
                for item in registry.snapshot()
                if item["owner"] == registry.owner
            }
        except OwnershipError as exc:
            self.note.set(f"Không adopt ClientJS: ownership registry lỗi: {exc}")
            owned_pids = set()

        filtered = []
        for row in rows or []:
            try:
                pid = int((row or {}).get("pid") or 0)
            except (TypeError, ValueError):
                continue
            if pid in owned_pids:
                filtered.append(row)

        result = original_adopt(self, filtered)
        for profile_id, process in list(self.processes.items()):
            try:
                if process and process.poll() is None and registry.self_owned(
                    int(process.pid), str(profile_id)
                ):
                    schedule_title(self, str(profile_id), int(process.pid))
            except Exception:
                continue
        return result

    def ownership_launch(self, profile, *args, **kwargs):
        profile = profile or {}
        profile_id = str(profile.get("id") or "")
        name = str(profile.get("name") or profile_id)
        if not profile_id:
            raise OwnershipError("Profile không có id để claim ClientJS")

        existing = registry.lookup_profile(profile_id)
        if existing:
            if existing["owner"] != registry.owner:
                raise ForeignOwnershipError(
                    f"{name} đang chạy bởi {existing['owner']} "
                    f"(PID {existing['pid']}); {registry.owner} chỉ theo dõi read-only"
                )
            process = self.processes.get(profile_id)
            if (
                not process
                or int(process.pid) != int(existing["pid"])
                or process.poll() is not None
            ):
                self.processes[profile_id] = core.RunningProcessRef(int(existing["pid"]))
            schedule_title(self, profile_id, int(existing["pid"]))
            return None

        result = original_launch(self, profile, *args, **kwargs)
        process = self.processes.get(profile_id)
        if not process or process.poll() is not None:
            return result

        try:
            registry.claim(int(process.pid), profile_id, name)
        except Exception:
            try:
                process.terminate()
            except Exception:
                pass
            self.processes.pop(profile_id, None)
            raise

        schedule_title(self, profile_id, int(process.pid))
        return result

    def ownership_stop_selected(self, *args, **kwargs):
        selected = list(map(str, self.selected_ids()))
        if not selected:
            return original_stop_selected(self, *args, **kwargs)

        try:
            by_profile = {item["profile_id"]: item for item in registry.snapshot()}
        except OwnershipError as exc:
            self.note.set(f"Không dừng ClientJS: ownership registry lỗi: {exc}")
            return None

        foreign = [
            profile_id
            for profile_id in selected
            if (
                by_profile.get(profile_id)
                and by_profile[profile_id]["owner"] != registry.owner
            )
        ]
        allowed = [profile_id for profile_id in selected if profile_id not in foreign]
        if foreign and not allowed:
            labels = ", ".join(account_name(self, item) for item in foreign)
            owners = ", ".join(
                sorted({by_profile[item]["owner"] for item in foreign})
            )
            self.note.set(
                f"Không dừng {labels}: ClientJS đang thuộc tool khác ({owners})"
            )
            return None

        saved_checked = set(self._checked_profiles)
        try:
            self._checked_profiles = set(allowed)
            result = original_stop_selected(self, *args, **kwargs)
        finally:
            self._checked_profiles = saved_checked

        if foreign:
            labels = ", ".join(account_name(self, item) for item in foreign)
            self.note.set(f"Bỏ qua ClientJS thuộc tool khác: {labels}")
        self.after(700, lambda: ownership_refresh(self))
        return result

    def ownership_worker_event(self, payload: dict) -> None:
        result = original_worker_event(self, payload)
        if str((payload or {}).get("event") or "") != "client_pid_changed":
            return result

        profile_id = str((payload or {}).get("profile_id") or "")
        new_pid = int((payload or {}).get("new_pid") or 0)
        old_pid = int((payload or {}).get("old_pid") or 0)
        if not profile_id or new_pid <= 0:
            return result

        try:
            registry.claim(
                new_pid,
                profile_id,
                account_name(self, profile_id),
                replace_pid=old_pid if old_pid > 0 else None,
            )
            schedule_title(self, profile_id, new_pid)
        except Exception as exc:
            process = self.processes.get(profile_id)
            if process and int(process.pid) == new_pid:
                try:
                    process.terminate()
                except Exception:
                    pass
                self.processes.pop(profile_id, None)
            self.note.set(f"ClientJS PID mới bị từ chối ownership: {exc}")
        return result

    def ownership_init(self, *args, **kwargs):
        result = original_init(self, *args, **kwargs)

        def tick():
            if not self.winfo_exists():
                return
            try:
                ownership_refresh(self)
            except Exception as exc:
                try:
                    self.note.set(f"Ownership refresh lỗi: {exc}")
                except Exception:
                    pass
            self.after(1500, tick)

        self.after(500, tick)
        return result

    app_cls.__init__ = ownership_init
    app_cls.refresh = ownership_refresh
    app_cls._adopt_running_clients = ownership_adopt
    app_cls._launch = ownership_launch
    app_cls.stop_selected = ownership_stop_selected
    if original_worker_event is not None:
        app_cls._handle_auto_worker_event = ownership_worker_event
    app_cls._client_ownership_integration_installed = True

    print(
        f"[KVTM {registry.owner}] ClientJS ownership READY • "
        "shared PID+creation-token registry • foreign clients read-only",
        flush=True,
    )
