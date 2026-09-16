"""Clean adapter for the operator-uploaded AUTO KVTM PRO package.

Source snapshot: autoproreal.zip
SHA256: d3366f3e687fc3a3e2ecbc848ac160ed2452c39187e8009eb8b1d3d09de78328

Only recovered original bytecode/assets are loaded.  Key/server and tracking
boundaries are replaced locally; ADB is disabled; input/capture use Bridge V3.
"""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parent
PYC = ROOT / "runtime" / "pyc"
INTERNAL = ROOT / "_internal"
DATA_ROOT = Path(
    os.environ.get("KVTM_MULTI_APP_DIR")
    or (Path(os.environ.get("APPDATA", Path.home())) / "Kvtm_tool_Cry")
)
PROFILE_FILE = DATA_ROOT / "profiles.json"
OWNERSHIP_FILE = (
    Path(os.environ.get("APPDATA", Path.home()))
    / "KVTM Client Ownership"
    / "clients.json"
)
DEVICE_PREFIX = "CRY:"
_MUTEX_NAME = r"Local\KVTM_Cry_UploadedAutoPro_v1"
_ERROR_ALREADY_EXISTS = 183

if os.name != "nt":
    raise SystemExit("AUTO PRO gốc cho Cry chỉ chạy trên Windows")
if sys.version_info[:2] != (3, 11):
    raise SystemExit("AUTO PRO gốc yêu cầu CPython 3.11 x64")

kernel32 = ctypes.windll.kernel32
_singleton_mutex = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
if not _singleton_mutex:
    raise ctypes.WinError()
if kernel32.GetLastError() == _ERROR_ALREADY_EXISTS:
    ctypes.windll.user32.MessageBoxW(
        None, "AUTO PRO gốc đang chạy.", "Kvtm_tool_Cry", 0x00000040
    )
    raise SystemExit(0)

os.environ["KVTM_MULTI_PROFILE_FILE"] = str(PROFILE_FILE)
os.environ["KVTM_AUTO_PRO_TRANSPORT"] = "bridge-v3"
os.environ["KVTM_AUTO_PRO_ADB_DISABLED"] = "1"


def _prepare_uploaded_runtime() -> None:
    """Expose package data/native modules without importing old sidecar patches."""
    for source in INTERNAL.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(INTERNAL)
        if len(relative.parts) < 2:
            continue
        package_root = PYC / relative.parts[0]
        if not package_root.exists():
            continue
        destination = PYC / relative
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if (
                not destination.exists()
                or source.stat().st_size != destination.stat().st_size
            ):
                shutil.copy2(source, destination)
        except OSError:
            pass

    sys.path.insert(0, str(PYC))
    sys.path.insert(0, str(INTERNAL))
    for subdir in ("win32", "win32/lib", "Pythonwin", "pywin32_system32"):
        candidate = INTERNAL / subdir
        if candidate.exists():
            sys.path.insert(0, str(candidate))
    if hasattr(os, "add_dll_directory"):
        for candidate in (
            INTERNAL,
            INTERNAL / "cv2",
            INTERNAL / "numpy.libs",
            INTERNAL / "pywin32_system32",
            INTERNAL / "Pythonwin",
        ):
            if candidate.exists():
                try:
                    os.add_dll_directory(str(candidate))
                except OSError:
                    pass
    os.environ["PATH"] = str(INTERNAL) + os.pathsep + os.environ.get("PATH", "")
    os.chdir(ROOT)


_prepare_uploaded_runtime()

from PIL import _imaging as _pil_imaging  # noqa: E402,F401
import offline_api  # noqa: E402
import gui_base  # noqa: E402

offline_api.install_gui_base(gui_base)

# Patch authentication before GUI modules snapshot LoginPopup/API functions.
import gui_popups  # noqa: E402


class OfflineLoginPopup:
    def __init__(self, parent, on_login_success=None, *args, **kwargs):
        del args, kwargs
        self.parent = parent
        self.on_login_success = on_login_success
        self.current_device_id = "LOCAL-DEVICE"
        self.token = "LOCAL-OFFLINE"
        self.auth = offline_api.local_profile()
        if on_login_success:
            parent.after(100, self._finish_login)

    def _finish_login(self):
        profile = offline_api.local_profile()
        self.on_login_success(
            profile["name"],
            profile["expired_at"],
            profile["functions"],
            profile["wallet"],
            profile["ref_id"],
        )

    def get_latest_version(self): return None
    def destroy(self): return None
    def protocol(self, *args, **kwargs): return None
    def deiconify(self): return None
    def withdraw(self): return None
    def grab_set(self): return None


gui_popups.LoginPopup = OfflineLoginPopup

import gui  # noqa: E402
import gui_device  # noqa: E402
import uiautomator2 as u2  # noqa: E402
from engine_driver import EngineDriver  # noqa: E402

gui.LoginPopup = OfflineLoginPopup
AutomationGUI = gui.AutomationGUI
AutomationGUI.get_license_key = lambda self: "LOCAL"
AutomationGUI.get_device_id = lambda self: "LOCAL-DEVICE"
AutomationGUI.start_expiration_scheduler = lambda self: None
AutomationGUI.check_license_validity = lambda self: True
AutomationGUI.check_key_validity_now = lambda self: True
AutomationGUI._maybe_show_login_notice = lambda self: None
AutomationGUI._check_update_after_login = lambda self: None
AutomationGUI._check_completed_orders_after_login = lambda self: None
AutomationGUI.send_telegram_notification = lambda self, *args, **kwargs: None
AutomationGUI.send_registration_renewal_notification = (
    lambda self, *args, **kwargs: None
)


def _pid_alive(pid: int) -> bool:
    handle = kernel32.OpenProcess(0x00100000, False, int(pid))
    if not handle:
        return False
    try:
        return kernel32.WaitForSingleObject(handle, 0) == 0x00000102
    finally:
        kernel32.CloseHandle(handle)


def _cry_owned_clients() -> list[dict]:
    """Read Cry ownership metadata only; do not inspect commands or credentials."""
    try:
        payload = json.loads(OWNERSHIP_FILE.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return []
    rows = payload.get("clients", []) if isinstance(payload, dict) else []
    result = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        if str(item.get("owner") or "").upper() != "CRY":
            continue
        try:
            pid = int(item.get("pid") or 0)
        except (TypeError, ValueError):
            continue
        if pid <= 0 or not _pid_alive(pid):
            continue
        result.append(
            {
                "pid": pid,
                "profile_id": str(item.get("profile_id") or ""),
                "name": str(
                    item.get("account_name")
                    or item.get("profile_id")
                    or f"PID {pid}"
                ),
            }
        )
    return result


def bridge_v3_connect(device_id=None, *args, **kwargs):
    del args, kwargs
    value = str(device_id or "")
    if not value.startswith(DEVICE_PREFIX):
        raise RuntimeError("ADB đã tắt trong AUTO PRO gốc của Cry")
    pid_text = value[len(DEVICE_PREFIX):]
    if not pid_text.isdigit():
        raise RuntimeError(f"Thiết bị Cry không hợp lệ: {value}")
    return EngineDriver(int(pid_text), reference_size=(1000, 1000))


u2.connect = bridge_v3_connect
DeviceManager = gui_device.DeviceManagerMixin


def fetch_cry_devices(self):
    del self
    data = {
        "emulator_paths": {},
        "adb_id_list": [],
        "adb_id_to_name": {},
        "display_devices": [],
        "device_mapping": {},
        "offline_tabs": [],
        "adb_id_pairs": {},
        "all_tab_info": {},
    }
    for item in _cry_owned_clients():
        pid = int(item["pid"])
        device_id = f"{DEVICE_PREFIX}{pid}"
        display_name = f"Cry - {item['name']} [{pid}]"
        data["adb_id_list"].append(device_id)
        data["adb_id_to_name"][device_id] = display_name
        data["display_devices"].append(display_name)
        data["device_mapping"][display_name] = device_id
        data["adb_id_pairs"][device_id] = device_id
        data["all_tab_info"][device_id] = {
            "name": display_name,
            "index": pid,
            "emulator_type": "clientjs-bridge-v3",
            "adb_id": device_id,
            "adb_id_alt": device_id,
            "exe_path": "GameClientJS.exe",
            "online": True,
            "profile_id": item["profile_id"],
        }
    return data


def cry_device_online(self, device_id):
    del self
    value = str(device_id or "")
    if not value.startswith(DEVICE_PREFIX):
        return False
    pid_text = value[len(DEVICE_PREFIX):]
    return pid_text.isdigit() and _pid_alive(int(pid_text))


def no_device_side_effect(self, device_id):
    del self, device_id
    return None


# Replace discovery outright: no call path reaches adb.exe/uiautomator2 setup/logcat.
DeviceManager._fetch_device_data = fetch_cry_devices
DeviceManager._is_adb_device_online = cry_device_online
DeviceManager._install_floating_button = no_device_side_effect
DeviceManager._start_logcat_monitor = no_device_side_effect


def main() -> int:
    app = AutomationGUI()
    try:
        app.title("AUTO KVTM PRO gốc • Kvtm_tool_Cry • Bridge V3")
    except Exception:
        pass
    app.mainloop()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        if _singleton_mutex:
            kernel32.CloseHandle(_singleton_mutex)
