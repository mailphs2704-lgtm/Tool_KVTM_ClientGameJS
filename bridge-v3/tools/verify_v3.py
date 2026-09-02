from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import struct
import sys


REQUIRED_SOURCE = (
    "KvtmBridgeProtocol",
    "KVTM_BRIDGE_V3 CAPTURE3 INPUT4 BATCH_SWIPE NO_LAYOUT",
    "Local\\\\KVTM-CaptureV3-",
    "KVTM-CocosV3-",
    "kCaptureVersion = 3",
)
FORBIDDEN_SOURCE = (
    "WM_SIZING",
    "WM_EXITSIZEMOVE",
    "SC_MAXIMIZE",
    "SetWindowPos(",
    "ShowWindow(",
    "GetDpiForWindow",
    "AdjustWindowRect",
    "profiles.json",
    "settings.json",
)


def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    raise SystemExit(1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    source = root / "native" / "kvtm_bridge_v3.cpp"
    client = root / "python" / "kvtm_bridge_v3.py"
    dll = root / "bin" / "kvtm_bridge_v3.dll"
    loader = root / "bin" / "kvtm_loader_v3.exe"
    for path in (source, client):
        if not path.is_file():
            fail(f"missing source: {path}")
    text = source.read_text(encoding="utf-8")
    for token in REQUIRED_SOURCE:
        if token not in text:
            fail(f"source missing required token: {token}")
    for token in FORBIDDEN_SOURCE:
        if token in text:
            fail(f"forbidden layout/data token in V3 DLL: {token}")
    client_text = client.read_text(encoding="utf-8")
    for token in ("time.perf_counter", "requested_seconds", "actual_seconds", "UnmapViewOfFile.argtypes"):
        if token not in client_text:
            fail(f"timing client missing: {token}")
    if "duration * (len(" in client_text:
        fail("duration is multiplied by path length")
    if not dll.is_file() or not loader.is_file():
        fail("V3 binary missing; run Control [1] first")
    raw = dll.read_bytes()
    if len(raw) < 4096 or raw[:2] != b"MZ":
        fail("V3 DLL is not a valid PE candidate")
    pe_offset = struct.unpack_from("<I", raw, 0x3C)[0]
    if raw[pe_offset:pe_offset + 4] != b"PE\0\0":
        fail("V3 DLL PE signature missing")
    machine = struct.unpack_from("<H", raw, pe_offset + 4)[0]
    if machine != 0x014C:
        fail(f"V3 DLL must be x86; machine=0x{machine:04x}")
    print("BRIDGE V3 STATIC VERIFIED")
    print(f"dll_size={len(raw)}")
    print(f"dll_sha256={hashlib.sha256(raw).hexdigest()}")
    print("scope=capture,input")
    print("layout=absent")
    print("runtime_installed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
