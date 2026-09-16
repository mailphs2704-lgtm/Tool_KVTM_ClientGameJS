from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import time
import uuid


OWNER_ENV = "KVTM_CLIENT_OWNER"
OWNER_DEV = "DEV"
OWNER_CRY = "CRY"
REGISTRY_SCHEMA = 2
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


def _alias(value: str) -> str:
    return " ".join(str(value or "").strip().casefold().split())


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
    """Shared metadata-only ownership for ClientJS processes."""

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
        if not isinstance(payload, dict):
            raise OwnershipError("ClientJS ownership registry is invalid")
        schema = int(payload.get("schema") or 0)
        if schema not in {1, REGISTRY_SCHEMA}:
            raise OwnershipError("ClientJS ownership registry schema is invalid")
        clients = payload.get("clients")
        if not isinstance(clients, list):
            raise OwnershipError("ClientJS ownership registry clients list is invalid")
        return {"schema": schema, "clients": clients}

    def _write_unlocked(self, clients: list[dict]) -> None:
        REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": REGISTRY_SCHEMA,
            "updated_at": time.time(),
            "clients": clients,
        }
        temp = REGISTRY_DIR / f".{REGISTRY_FILE.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
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
        account_name = str(entry.get("account_name") or profile_id)
        account_key = str(entry.get("account_key") or f"profile:{profile_id}")
        owner = str(entry.get("owner") or "").upper()
        if pid <= 0 or not creation_token or not profile_id or owner not in {OWNER_DEV, OWNER_CRY}:
            return None
        return {
            "pid": pid,
            "creation_token": creation_token,
            "profile_id": profile_id,
            "account_key": account_key,
            "account_name": account_name,
            "owner": owner,
            "instance": str(entry.get("instance") or owner),
            "claimed_at": float(entry.get("claimed_at") or 0.0),
        }

    def _prune(self, clients: list[dict]) -> tuple[list[dict], bool]:
        kept: list[dict] = []
        changed = False
        seen_pids: set[int] = set()
        seen_profiles: set[str] = set()
        seen_accounts: set[str] = set()
        seen_aliases: set[str] = set()
        for raw in clients:
            entry = self._normalized(raw)
            if entry is None:
                changed = True
                continue
            token = _creation_token(entry["pid"])
            if token is None or token != entry["creation_token"]:
                changed = True
                continue
            account_key = entry["account_key"]
            account_alias = _alias(entry["account_name"])
            if (
                entry["pid"] in seen_pids
                or entry["profile_id"] in seen_profiles
                or account_key in seen_accounts
                or (account_alias and account_alias in seen_aliases)
            ):
                changed = True
                continue
            seen_pids.add(entry["pid"])
            seen_profiles.add(entry["profile_id"])
            seen_accounts.add(account_key)
            if account_alias:
                seen_aliases.add(account_alias)
            kept.append(entry)
        return kept, changed

    def snapshot(self) -> list[dict]:
        with _NamedMutex():
            payload = self._read_unlocked()
            clients, changed = self._prune(payload["clients"])
            if changed or int(payload.get("schema") or 0) != REGISTRY_SCHEMA:
                self._write_unlocked(clients)
            return [dict(item) for item in clients]

    @staticmethod
    def _matches_identity(
        item: dict, profile_id: str, account_key: str, account_name: str
    ) -> bool:
        same_profile = item["profile_id"] == str(profile_id or "")
        same_account = bool(account_key) and item["account_key"] == str(account_key)
        wanted_alias = _alias(account_name)
        same_alias = bool(wanted_alias) and _alias(item["account_name"]) == wanted_alias
        return same_profile or same_account or same_alias

    def lookup_identity(
        self, profile_id: str, account_key: str, account_name: str
    ) -> dict | None:
        return next(
            (
                item
                for item in self.snapshot()
                if self._matches_identity(item, profile_id, account_key, account_name)
            ),
            None,
        )

    def lookup_pid(self, pid: int) -> dict | None:
        wanted = int(pid)
        return next((item for item in self.snapshot() if item["pid"] == wanted), None)

    def claim(
        self,
        pid: int,
        profile_id: str,
        account_key: str,
        account_name: str,
        *,
        replace_pid: int | None = None,
    ) -> dict:
        pid = int(pid)
        profile_id = str(profile_id or "")
        account_key = str(account_key or "")
        account_name = str(account_name or profile_id)
        if pid <= 0 or not profile_id or not account_key:
            raise OwnershipError("Cannot claim ClientJS without pid/profile/account identity")
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
                    same_identity = self._matches_identity(
                        item, profile_id, account_key, account_name
                    )
                    if item["pid"] == old_pid or same_identity:
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
                same_account = item["account_key"] == account_key
                same_alias = bool(_alias(account_name)) and _alias(item["account_name"]) == _alias(account_name)
                if not (same_pid or same_profile or same_account or same_alias):
                    continue
                if (
                    item["owner"] == self.owner
                    and same_pid
                    and item["creation_token"] == token
                ):
                    item["profile_id"] = profile_id
                    item["account_key"] = account_key
                    item["account_name"] = account_name
                    item["instance"] = self.instance
                    self._write_unlocked(clients)
                    return dict(item)
                error_type = ForeignOwnershipError if item["owner"] != self.owner else OwnershipError
                raise error_type(
                    f"{account_name} đang chạy bởi {item['owner']} "
                    f"(PID {item['pid']})"
                )

            entry = {
                "pid": pid,
                "creation_token": token,
                "profile_id": profile_id,
                "account_key": account_key,
                "account_name": account_name,
                "owner": self.owner,
                "instance": self.instance,
                "claimed_at": time.time(),
            }
            clients.append(entry)
            self._write_unlocked(clients)
            return dict(entry)

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

    def account_name_for_profile(self, profile: dict | None) -> str:
        profile = profile or {}
        return str(profile.get("name") or profile.get("id") or "Tài khoản")

    def account_key_for_profile(self, profile: dict | None) -> str:
        profile = profile or {}
        try:
            signature = self._profile_signature(profile)
        except Exception:
            signature = None
        if signature:
            payload = json.dumps(
                signature,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
            return "sig:" + hashlib.sha256(payload).hexdigest()
        fallback = _alias(account_name_for_profile(self, profile))
        return "alias:" + hashlib.sha256(fallback.encode("utf-8")).hexdigest()

    def identity_for_profile(self, profile: dict | None) -> tuple[str, str, str]:
        profile = profile or {}
        return (
            str(profile.get("id") or ""),
            account_key_for_profile(self, profile),
            account_name_for_profile(self, profile),
        )

    def entry_for_profile(self, profile: dict | None, snapshot: list[dict] | None = None) -> dict | None:
        profile_id, account_key, account_name = identity_for_profile(self, profile)
        rows = snapshot if snapshot is not None else registry.snapshot()
        return next(
            (
                item
                for item in rows
                if registry._matches_identity(item, profile_id, account_key, account_name)
            ),
            None,
        )

    def schedule_title(self, profile_id: str, pid: int, attempt: int = 0) -> None:
        try:
            entry = registry.lookup_pid(int(pid))
        except OwnershipError:
            return
        if not entry or entry["owner"] != registry.owner:
            return
        if registry.set_window_title(int(pid), str(entry["account_name"])):
            return
        if attempt < 120:
            self.after(
                500,
                lambda p=str(profile_id), n=int(pid), a=attempt + 1:
                    schedule_title(self, p, n, a),
            )

    def decorate_rows(self) -> None:
        try:
            snapshot = registry.snapshot()
        except OwnershipError as exc:
            self.note.set(f"ClientJS ownership registry lỗi: {exc}")
            return

        for profile in self.profiles:
            profile_id = str(profile.get("id") or "")
            entry = entry_for_profile(self, profile, snapshot)
            if not profile_id or not entry:
                continue
            values = (
                str(profile.get("name") or "Chưa đặt tên"),
                f"{entry['pid']} • ONL • {entry['owner']}",
            )
            if self.offline_tree.exists(profile_id):
                icon = self.offline_tree.item(profile_id, "text")
                was_selected = profile_id in self.offline_tree.selection()
                self.offline_tree.delete(profile_id)
                self.online_tree.insert(
                    "", "end", iid=profile_id, text=icon, values=values
                )
                if was_selected:
                    self.online_tree.selection_set(profile_id)
            elif self.online_tree.exists(profile_id):
                self.online_tree.item(profile_id, values=values)

            if entry["owner"] == registry.owner:
                schedule_title(self, profile_id, int(entry["pid"]))

    def ownership_refresh(self) -> None:
        original_refresh(self)
        decorate_rows(self)

    def ownership_adopt(self, rows: list[dict]) -> None:
        try:
            snapshot = registry.snapshot()
        except OwnershipError as exc:
            self.note.set(f"Không adopt ClientJS: ownership registry lỗi: {exc}")
            snapshot = []

        # AUTO PRO gốc restarts the exact Cry profile inside EngineDriver.  The
        # replacement PID initially has no registry row, so filtering only
        # already-owned PIDs creates a deadlock: Cry can neither adopt nor claim
        # it.  Reclaim only for the Stable CRY owner and only after the complete
        # saved profile signature (game path + protected launch arguments)
        # matches. DEV never enters this recovery path.
        if registry.owner == OWNER_CRY:
            signatures = {
                str(profile.get("id") or ""): self._profile_signature(profile)
                for profile in self.profiles
            }
            for row in rows or []:
                try:
                    pid = int(
                        (row or {}).get("ProcessId")
                        or (row or {}).get("pid")
                        or 0
                    )
                    args = core.split_windows_command_line(
                        (row or {}).get("CommandLine") or ""
                    )
                    if pid <= 0 or len(args) < 2:
                        continue
                    running_signature = (
                        os.path.normcase(os.path.abspath(args[1])),
                        args[2:],
                    )
                    profile = next(
                        (
                            item for item in self.profiles
                            if signatures.get(str(item.get("id") or ""))
                            == running_signature
                        ),
                        None,
                    )
                    if profile is None:
                        continue
                    profile_id, account_key, account_name = identity_for_profile(
                        self, profile
                    )
                    existing = entry_for_profile(self, profile, snapshot)
                    if existing is not None:
                        # A live self/foreign owner remains authoritative. Never
                        # replace it merely because another matching PID exists.
                        continue
                    claimed = registry.claim(
                        pid, profile_id, account_key, account_name
                    )
                    snapshot.append(claimed)
                    print(
                        "[KVTM CRY] replacement ClientJS reclaimed • "
                        f"profile={profile_id} pid={pid}",
                        flush=True,
                    )
                except ForeignOwnershipError:
                    continue
                except Exception as exc:
                    print(
                        "[KVTM CRY] replacement reclaim skipped • "
                        f"{type(exc).__name__}: {exc}",
                        flush=True,
                    )

        owned_pids = {
            int(item["pid"])
            for item in snapshot
            if item["owner"] == registry.owner
        }
        filtered = []
        for row in rows or []:
            try:
                pid = int((row or {}).get("ProcessId") or (row or {}).get("pid") or 0)
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
        profile_id, account_key, account_name = identity_for_profile(self, profile)
        if not profile_id:
            raise OwnershipError("Profile không có id để claim ClientJS")

        existing = registry.lookup_identity(profile_id, account_key, account_name)
        if existing:
            if existing["owner"] != registry.owner:
                raise ForeignOwnershipError(
                    f"{account_name} đang chạy bởi {existing['owner']} "
                    f"(PID {existing['pid']}); {registry.owner} chỉ theo dõi read-only"
                )
            if existing["profile_id"] != profile_id:
                raise OwnershipError(
                    f"{account_name} đã chạy trong {registry.owner} "
                    f"(PID {existing['pid']}); không mở trùng account"
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
            registry.claim(
                int(process.pid), profile_id, account_key, account_name
            )
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
            snapshot = registry.snapshot()
        except OwnershipError as exc:
            self.note.set(f"Không dừng ClientJS: ownership registry lỗi: {exc}")
            return None

        foreign: list[str] = []
        allowed: list[str] = []
        foreign_entries: dict[str, dict] = {}
        for profile_id in selected:
            profile = profile_for(self, profile_id)
            entry = entry_for_profile(self, profile, snapshot)
            if entry and entry["owner"] != registry.owner:
                foreign.append(profile_id)
                foreign_entries[profile_id] = entry
            else:
                allowed.append(profile_id)

        if foreign and not allowed:
            labels = ", ".join(account_name_for_profile(self, profile_for(self, item)) for item in foreign)
            owners = ", ".join(sorted({foreign_entries[item]["owner"] for item in foreign}))
            self.note.set(f"Không dừng {labels}: ClientJS đang thuộc tool khác ({owners})")
            return None

        saved_checked = set(self._checked_profiles)
        try:
            self._checked_profiles = set(allowed)
            result = original_stop_selected(self, *args, **kwargs)
        finally:
            self._checked_profiles = saved_checked
        if foreign:
            labels = ", ".join(account_name_for_profile(self, profile_for(self, item)) for item in foreign)
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
        profile = profile_for(self, profile_id)
        if not profile or new_pid <= 0:
            return result
        _profile_id, account_key, account_name = identity_for_profile(self, profile)
        try:
            registry.claim(
                new_pid,
                profile_id,
                account_key,
                account_name,
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
        for tree in (self.online_tree, self.offline_tree):
            tree.heading("pid", text="PID • TOOL")
            tree.column("pid", width=155, minwidth=145, stretch=False, anchor="center")
            tree.column("name", width=190, minwidth=120, stretch=True, anchor="w")

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

        self.after(300, tick)
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
        "account-key+alias+PID creation token • foreign clients read-only",
        flush=True,
    )
