"""Launch recovered AUTO KVTM PRO with running GameClientJS windows as devices.

Place this file and pc_driver.py beside local_launcher.py, then run this file
with the same Python 3.11 environment used by RUN_LOCAL.bat.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
if not (ROOT / "local_launcher.py").is_file():
    raise SystemExit("Hãy chép pc_auto_launcher.py và pc_driver.py vào thư mục AUTO KVTM có local_launcher.py")

# local_launcher prepares recovered pyc/native paths, offline login and gui modules.
import local_launcher  # noqa: E402
import gui  # noqa: E402
import gui_device  # noqa: E402
import uiautomator2 as u2  # noqa: E402
from pc_driver import PCDriver  # noqa: E402


PC_PREFIX = "PC:"
PROFILE_PREFIX = "PCID:"


def _running_pc_clients() -> list[dict]:
    script = (
        "$p=Get-CimInstance Win32_Process -Filter \"Name='GameClientJS.exe'\" | "
        "Select-Object ProcessId,ExecutablePath,CommandLine;"
        "@($p)|ConvertTo-Json -Compress"
    )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, encoding="utf-8-sig", errors="replace",
        creationflags=flags, timeout=15, check=True,
    )
    rows = json.loads(result.stdout or "[]")
    if isinstance(rows, dict):
        rows = [rows]
    return [r for r in rows if r.get("ProcessId")]


def _running_profile_map() -> dict[int, dict]:
    """Read Multi's authoritative stable profile ID -> current PID publication."""
    path = Path(os.environ.get("APPDATA", Path.home())) / "KVTM Multi" / "running_clients.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        clients = payload.get("clients", []) if isinstance(payload, dict) else []
        return {
            int(item["pid"]): item
            for item in clients
            if isinstance(item, dict) and item.get("pid")
        }
    except Exception:
        return {}


def _pc_entries() -> list[tuple[str, str, int]]:
    rows = _running_pc_clients()
    published = _running_profile_map()
    result = []
    for row in rows:
        pid = int(row["ProcessId"])
        item = published.get(pid, {})
        label = str(item.get("name") or f"PID {pid}")
        profile_id = str(item.get("profile_id") or "")
        device_id = f"{PROFILE_PREFIX}{profile_id}" if profile_id else f"{PC_PREFIX}{pid}"
        result.append((f"PC - {label} [{pid}]", device_id, pid))
    return result


def _pid_for_profile_id(profile_id: str) -> int | None:
    for _display_name, device_id, pid in _pc_entries():
        if device_id == f"{PROFILE_PREFIX}{profile_id}":
            return pid
    return None

_original_connect = u2.connect


def pc_connect(device_id=None, *args, **kwargs):
    text = str(device_id or "")
    if text.startswith(PROFILE_PREFIX):
        pid = _pid_for_profile_id(text[len(PROFILE_PREFIX):])
        if not pid:
            raise RuntimeError("Tài khoản ClientJS đang offline")
        return PCDriver(pid, reference_size=(1000, 1000))
    if text.startswith(PC_PREFIX):
        return PCDriver(int(text[len(PC_PREFIX):]), reference_size=(1000, 1000))
    return _original_connect(device_id, *args, **kwargs)


u2.connect = pc_connect


DM = gui_device.DeviceManagerMixin
_original_fetch = DM._fetch_device_data
_original_online = DM._is_adb_device_online
_original_install_float = DM._install_floating_button
_original_logcat = DM._start_logcat_monitor


def fetch_with_pc(self):
    try:
        data = _original_fetch(self)
    except Exception:
        data = {
            "emulator_paths": {}, "adb_id_list": [], "adb_id_to_name": {},
            "display_devices": [], "device_mapping": {}, "offline_tabs": [],
            "adb_id_pairs": {}, "all_tab_info": {},
        }
    for display_name, device_id, pid in _pc_entries():
        if device_id not in data["adb_id_list"]:
            data["adb_id_list"].append(device_id)
        data["adb_id_to_name"][device_id] = display_name
        if display_name not in data["display_devices"]:
            data["display_devices"].append(display_name)
        data["device_mapping"][display_name] = device_id
        data["adb_id_pairs"][device_id] = device_id
        data["all_tab_info"][device_id] = {
            "name": display_name, "index": pid, "emulator_type": "pc",
            "adb_id": device_id, "adb_id_alt": device_id,
            "exe_path": "GameClientJS.exe", "online": True,
        }
    return data


def online_with_pc(self, device_id):
    value = str(device_id)
    if value.startswith(PROFILE_PREFIX) or value.startswith(PC_PREFIX):
        try:
            if value.startswith(PROFILE_PREFIX):
                pid = _pid_for_profile_id(value[len(PROFILE_PREFIX):])
                if not pid:
                    return False
            else:
                pid = int(value[len(PC_PREFIX):])
            PCDriver(pid).hwnd
            return True
        except Exception:
            return False
    return _original_online(self, device_id)


def install_float_with_pc(self, device_id):
    if str(device_id).startswith((PC_PREFIX, PROFILE_PREFIX)):
        return None
    return _original_install_float(self, device_id)


def logcat_with_pc(self, device_id):
    if str(device_id).startswith((PC_PREFIX, PROFILE_PREFIX)):
        return None
    return _original_logcat(self, device_id)


DM._fetch_device_data = fetch_with_pc
DM._is_adb_device_online = online_with_pc
DM._install_floating_button = install_float_with_pc
DM._start_logcat_monitor = logcat_with_pc


if __name__ == "__main__":
    app = gui.AutomationGUI()
    app.mainloop()
