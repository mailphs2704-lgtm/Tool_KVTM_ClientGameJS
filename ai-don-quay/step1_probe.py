from __future__ import annotations

import argparse
import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import time
import traceback


def emit(event: str, **data) -> None:
    print(json.dumps({"event": event, **data}, ensure_ascii=False), flush=True)


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _blob(data: bytes):
    buffer = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def _unprotect(value: str) -> bytes:
    source, source_buffer = _blob(base64.b64decode(value))
    entropy, entropy_buffer = _blob(b"KVTM-MULTI-v1")
    result = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(source), None, ctypes.byref(entropy), None, None, 0x01, ctypes.byref(result)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(result.pbData)
        del source_buffer, entropy_buffer


def _split_command_line(command_line: str) -> list[str]:
    count = ctypes.c_int()
    parser = ctypes.windll.shell32.CommandLineToArgvW
    parser.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    parser.restype = ctypes.POINTER(wintypes.LPWSTR)
    argv = parser(command_line, ctypes.byref(count))
    if not argv:
        raise ctypes.WinError()
    try:
        return [argv[index] for index in range(count.value)]
    finally:
        ctypes.windll.kernel32.LocalFree(argv)


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path or ""))


def _running_game_rows() -> list[dict]:
    script = (
        "$p=@(Get-CimInstance Win32_Process -Filter \"Name='GameClientJS.exe'\" | "
        "Select-Object ProcessId,ExecutablePath,CommandLine);"
        "$p|ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8-sig",
        errors="replace",
        timeout=15,
        check=True,
    )
    raw = (result.stdout or "").strip()
    if not raw or raw == "null":
        raise RuntimeError("Không có GameClientJS.exe nào đang chạy")
    rows = json.loads(raw)
    if isinstance(rows, dict):
        rows = [rows]
    return [row for row in rows if isinstance(row, dict)]


def _targets_from_profiles(profiles_file: Path, rows: list[dict]) -> list[dict]:
    profiles = json.loads(profiles_file.read_text(encoding="utf-8"))
    if not isinstance(profiles, list):
        raise RuntimeError("profiles.json của DEV không phải danh sách")

    prepared_profiles: list[dict] = []
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        profile_id = str(profile.get("id") or "")
        client = str(profile.get("client") or "")
        game_dir = str(profile.get("game_dir") or "")
        protected_secret = profile.get("secret")
        if not profile_id or not client or not game_dir or not protected_secret:
            continue
        try:
            secret_args = json.loads(_unprotect(str(protected_secret)).decode("utf-8"))
        except Exception:
            continue
        if not isinstance(secret_args, list):
            continue
        prepared_profiles.append(
            {
                "id": profile_id,
                "name": str(profile.get("name") or profile_id),
                "client": _norm(client),
                "game_dir": _norm(game_dir),
                "secret_args": [str(item) for item in secret_args],
            }
        )

    targets: list[dict] = []
    seen: set[int] = set()
    for row in rows:
        try:
            pid = int(row.get("ProcessId"))
            executable = _norm(str(row.get("ExecutablePath") or ""))
            argv = _split_command_line(str(row.get("CommandLine") or ""))
        except Exception:
            continue
        if len(argv) < 2:
            continue
        running_game = _norm(argv[1])
        running_secret = [str(item) for item in argv[2:]]
        for profile in prepared_profiles:
            if executable != profile["client"]:
                continue
            if running_game != profile["game_dir"]:
                continue
            if running_secret != profile["secret_args"]:
                continue
            if pid in seen:
                break
            seen.add(pid)
            targets.append(
                {
                    "pid": pid,
                    "profile_id": profile["id"],
                    "profile_name": profile["name"],
                    "identity_source": "profiles.json",
                }
            )
            break
    return targets


def _targets_from_fresh_running_map(running_map_file: Path, rows: list[dict]) -> list[dict]:
    try:
        age = max(0.0, time.time() - running_map_file.stat().st_mtime)
    except OSError as exc:
        raise RuntimeError(f"Không đọc được running_clients.json: {exc}") from exc
    if age > 30.0:
        raise RuntimeError(
            f"running_clients.json đã cũ {age:.1f}s; cần Multi DEV đang mở để xác nhận PID an toàn"
        )

    payload = json.loads(running_map_file.read_text(encoding="utf-8"))
    clients = payload.get("clients", []) if isinstance(payload, dict) else []
    if not isinstance(clients, list):
        raise RuntimeError("running_clients.json của DEV không đúng schema")

    live_game_pids = set()
    for row in rows:
        try:
            live_game_pids.add(int(row.get("ProcessId")))
        except (TypeError, ValueError):
            continue

    targets: list[dict] = []
    seen: set[int] = set()
    for item in clients:
        if not isinstance(item, dict):
            continue
        try:
            pid = int(item.get("pid"))
        except (TypeError, ValueError):
            continue
        profile_id = str(item.get("profile_id") or "")
        if pid <= 0 or not profile_id or pid not in live_game_pids or pid in seen:
            continue
        seen.add(pid)
        targets.append(
            {
                "pid": pid,
                "profile_id": profile_id,
                "profile_name": str(item.get("name") or profile_id),
                "identity_source": "running_clients.json",
            }
        )

    if not targets:
        raise RuntimeError(
            "running_clients.json không chứa PID GameClientJS DEV còn sống; không thử client khác"
        )
    return targets


def discover_dev_game_targets(auto_root: Path) -> list[dict]:
    data_dir = auto_root.parent / "data-dev"
    profiles_file = data_dir / "profiles.json"
    running_map_file = data_dir / "running_clients.json"
    rows = _running_game_rows()

    if profiles_file.is_file():
        targets = _targets_from_profiles(profiles_file, rows)
        if targets:
            return sorted(targets, key=lambda item: int(item["pid"]))
        raise RuntimeError(
            "Có profiles.json DEV nhưng không profile nào khớp GameClientJS đang chạy; "
            "không fallback sang client ngoài profile"
        )

    if running_map_file.is_file():
        targets = _targets_from_fresh_running_map(running_map_file, rows)
        return sorted(targets, key=lambda item: int(item["pid"]))

    raise RuntimeError(
        "Không có nguồn định danh DEV an toàn: thiếu cả profiles.json và running_clients.json"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto-root", required=True)
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()

    auto_root = Path(args.auto_root).resolve()
    work_dir = Path(args.work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        targets = discover_dev_game_targets(auto_root)
        sources = sorted({str(item.get("identity_source") or "") for item in targets})
        emit(
            "step1_progress",
            stage="dev-clients-detected",
            message=(
                f"Bước 1: tìm thấy {len(targets)} GameClientJS thuộc Multi DEV; "
                "mọi client ngoài nguồn định danh DEV đã bị loại"
            ),
            identity_sources=sources,
            targets=targets,
        )

        worker_root = Path(__file__).resolve().parents[1] / "components" / "clientjs-auto" / "worker"
        worker_text = str(worker_root)
        if worker_text not in os.sys.path:
            os.sys.path.insert(0, worker_text)

        emit("step1_progress", stage="bootstrap-auto-main", message="Bước 1: nạp đúng bootstrap AUTO chính")
        from auto_worker import install_clientjs_runtime

        install_clientjs_runtime(auto_root)
        emit("step1_progress", stage="auto-main-runtime-ready", message="Bước 1: runtime AUTO chính đã sẵn sàng")

        import uiautomator2 as u2
        import cv2

        successes: list[dict] = []
        failures: list[dict] = []
        for target in targets:
            pid = int(target["pid"])
            try:
                emit(
                    "step1_progress",
                    stage="auto-main-driver-connecting",
                    message=f"Bước 1: thử DEV profile {target['profile_name']} PID {pid}",
                    pid=pid,
                    profile_id=target["profile_id"],
                    identity_source=target.get("identity_source"),
                )
                driver = u2.connect(f"PC:{pid}")
                emit(
                    "step1_progress",
                    stage="auto-main-driver-ready",
                    message=f"Bước 1: PID {pid} đã kết nối bằng {type(driver).__name__}",
                    pid=pid,
                    driver_type=type(driver).__name__,
                )
                frame = driver.screenshot(format="opencv")
                if frame is None or not hasattr(frame, "shape"):
                    raise RuntimeError("AUTO chính không trả về frame OpenCV hợp lệ")
                output = work_dir / f"step1-auto-main-capture-pid-{pid}.png"
                if not cv2.imwrite(str(output), frame):
                    raise RuntimeError(f"Không ghi được ảnh kiểm tra: {output}")
                result = {
                    "pid": pid,
                    "profile_id": target["profile_id"],
                    "profile_name": target["profile_name"],
                    "driver_type": type(driver).__name__,
                    "width": int(frame.shape[1]),
                    "height": int(frame.shape[0]),
                    "capture": str(output),
                }
                successes.append(result)
                emit("step1_pid_pass", stage="capture-pass", message=f"Bước 1: DEV PID {pid} chụp ảnh PASS", **result)
            except Exception as exc:
                failure = {
                    "pid": pid,
                    "profile_id": target["profile_id"],
                    "profile_name": target["profile_name"],
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                }
                failures.append(failure)
                emit("step1_pid_error", stage="capture-failed", message=f"Bước 1: DEV PID {pid} lỗi", **failure)

        if not successes:
            emit("step1_error", stage="step1-failed", error="Không PID DEV nào chụp ảnh PASS bằng luồng AUTO chính", failures=failures)
            return 1

        emit(
            "step1_pass",
            stage="capture-pass",
            message="BƯỚC 1 PASS: AUTO chính đã kết nối và chụp được GameClientJS thuộc Multi DEV",
            successes=successes,
            failures=failures,
        )
        return 0
    except Exception as exc:
        emit("step1_error", stage="step1-failed", error=repr(exc), traceback=traceback.format_exc())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
