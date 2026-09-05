from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
from typing import Callable


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _unprotect(encoded: str) -> bytes:
    import base64

    encrypted = base64.b64decode(str(encoded))
    source_buffer = ctypes.create_string_buffer(encrypted)
    source = DATA_BLOB(
        len(encrypted),
        ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    output = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(source), None, None, None, None, 0, ctypes.byref(output)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)


def _split_command_line(command_line: str) -> list[str]:
    argc = ctypes.c_int()
    argv = ctypes.windll.shell32.CommandLineToArgvW(
        str(command_line), ctypes.byref(argc)
    )
    if not argv:
        raise ctypes.WinError()
    try:
        return [argv[index] for index in range(argc.value)]
    finally:
        ctypes.windll.kernel32.LocalFree(argv)


class ProfileProcessResolver:
    """Resolve one ClientJS account by immutable profile data, never PID alone."""

    def __init__(
        self,
        profile_id: str,
        profile_file: Path,
        *,
        logger: Callable[[str], None] | None = None,
    ) -> None:
        self.profile_id = str(profile_id)
        self.profile_file = Path(profile_file).resolve()
        self.logger = logger
        self.profile = self._load_profile()

    def _log(self, message: str) -> None:
        if self.logger is not None:
            self.logger(str(message))

    def _load_profile(self) -> dict:
        payload = json.loads(self.profile_file.read_text(encoding="utf-8"))
        profiles = payload.get("profiles", []) if isinstance(payload, dict) else payload
        if not isinstance(profiles, list):
            raise RuntimeError("profiles.json không có danh sách profile")
        profile = next(
            (
                item for item in profiles
                if isinstance(item, dict)
                and str(item.get("id") or "") == self.profile_id
            ),
            None,
        )
        if profile is None:
            raise RuntimeError(f"Không tìm thấy profile cố định {self.profile_id}")
        return profile

    @staticmethod
    def is_alive(pid: int) -> bool:
        handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, int(pid))
        if not handle:
            return False
        try:
            return ctypes.windll.kernel32.WaitForSingleObject(handle, 0) == 0x102
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)

    def current_pid(self) -> int | None:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        script = (
            "$p=Get-CimInstance Win32_Process -Filter \"Name='GameClientJS.exe'\" | "
            "Select-Object ProcessId,CommandLine;@($p)|ConvertTo-Json -Compress"
        )
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, encoding="utf-8-sig", errors="replace",
            creationflags=flags, timeout=15, check=True,
        )
        rows = json.loads(result.stdout or "[]")
        if isinstance(rows, dict):
            rows = [rows]
        wanted_game = os.path.normcase(
            os.path.abspath(str(self.profile.get("game_dir") or ""))
        )
        secret_args = json.loads(_unprotect(self.profile["secret"]).decode("utf-8"))
        for row in rows:
            args = _split_command_line(row.get("CommandLine") or "")
            if len(args) < 2:
                continue
            running_game = os.path.normcase(os.path.abspath(args[1]))
            if running_game == wanted_game and args[2:] == secret_args:
                return int(row["ProcessId"])
        return None
