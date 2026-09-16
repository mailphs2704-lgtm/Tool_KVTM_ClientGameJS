"""Run the recovered original AUTO PRO GUI against Cry-owned ClientJS only.

This launcher is intentionally isolated from AUTO MULTI DEV.  It keeps the
recovered GUI/business bytecode, uses the offline local launcher (no key/server),
and replaces the ADB device boundary with EngineDriver/Bridge V3.
"""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
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
_MUTEX_NAME = r"Local\KVTM_Cry_OriginalAutoPro_v1"
_ERROR_ALREADY_EXISTS = 183

# EngineDriver must resolve restart/profile identity from Stable Cry, never DEV.
os.environ["KVTM_MULTI_PROFILE_FILE"] = str(PROFILE_FILE)
os.environ["KVTM_AUTO_PRO_TRANSPORT"] = "bridge-v3"
os.environ["KVTM_AUTO_PRO_ADB_DISABLED"] = "1"

if os.name != "nt":
    raise SystemExit("AUTO PRO gốc cho Cry chỉ chạy trên Windows")

kernel32 = ctypes.windll.kernel32
_singleton_mutex = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
if not _singleton_mutex:
    raise ctypes.WinError()
if kernel32.GetLastError() == _ERROR_ALREADY_EXISTS:
    ctypes.windll.user32.MessageBoxW(
        None,
        "AUTO PRO gốc đang chạy.",
        "Kvtm_tool_Cry",
        0x00000040,
    )
    raise SystemExit(0)

# Prepares recovered Python/PyInstaller paths and installs local offline auth.
# Importing it does not start local_bridge; that code exists only in its __main__.
import local_launcher  # noqa: E402,F401
import gui  # noqa: E402
import gui_device  # noqa: E402
import uiautomator2 as u2  # noqa: E402
from engine_driver import EngineDriver  # noqa: E402


def _pid_alive(pid: int) -> bool:
    handle = kernel32.OpenProcess(0x00100000, False, int(pid))
    if not handle:
        return False
    try:
        return kernel32.WaitForSingleObject(handle, 0) == 0x00000102
    finally:
        kernel32.CloseHandle(handle)


def _cry_owned_clients() -> list[dict]:
    """Read metadata-only ownership; never inspect command lines or secrets."""
    try:
        payload = json.loads(OWNERSHIP_FILE.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return []
    rows = payload.get("clients", []) if isinstance(payload, dict) else []
    result = []
    for item in rows:
        if not isinstance(item, dict) or str(item.get("owner") or "").upper() != "CRY":
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
                "name": str(item.get("account_name") or item.get("profile_id") or f"PID {pid}"),
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

DM = gui_device.DeviceManagerMixin


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


def no_floating_button(self, device_id):
    del self, device_id
    return None


def no_logcat(self, device_id):
    del self, device_id
    return None


# Replace, rather than wrap, all ADB discovery/health side effects.
DM._fetch_device_data = fetch_cry_devices
DM._is_adb_device_online = cry_device_online
DM._install_floating_button = no_floating_button
DM._start_logcat_monitor = no_logcat


def main() -> int:
    app = gui.AutomationGUI()
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
