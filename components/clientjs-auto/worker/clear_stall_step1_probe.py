from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import traceback


def emit(event: str, **data) -> None:
    print(json.dumps({"event": event, **data}, ensure_ascii=False), flush=True)


def discover_single_game_pid() -> int:
    script = (
        "$p=@(Get-CimInstance Win32_Process -Filter \"Name='GameClientJS.exe'\" | "
        "Select-Object -ExpandProperty ProcessId);$p|ConvertTo-Json -Compress"
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
    value = json.loads(raw)
    pids = value if isinstance(value, list) else [value]
    pids = [int(pid) for pid in pids]
    if len(pids) != 1:
        raise RuntimeError(
            f"Bước 1 cần đúng 1 GameClientJS đang mở; hiện có {len(pids)} PID: {pids}"
        )
    return pids[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto-root", required=True)
    parser.add_argument("--pid", type=int)
    parser.add_argument("--profile-id", default="step1")
    parser.add_argument("--profile-name", default="Dọn quầy Step 1")
    parser.add_argument("--work-dir", default="data-dev/clear-stall-step1")
    args = parser.parse_args()

    auto_root = Path(args.auto_root).resolve()
    work_dir = Path(args.work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    pid = int(args.pid) if args.pid else discover_single_game_pid()

    try:
        emit(
            "step1_progress",
            stage="bootstrap-auto-main",
            message="Bước 1: nạp đúng bootstrap AUTO chính",
            pid=pid,
        )

        # This is the exact bootstrap used by the working AUTO ClientJS worker.
        # Step 1 deliberately does not use the clean/resident Dọn quầy runtime.
        from auto_worker import install_clientjs_runtime

        install_clientjs_runtime(auto_root)
        emit(
            "step1_progress",
            stage="auto-main-runtime-ready",
            message="Bước 1: runtime AUTO chính đã sẵn sàng",
        )

        # AUTO chính patches uiautomator2.connect("PC:<pid>") to EngineDriver.
        import uiautomator2 as u2

        driver = u2.connect(f"PC:{pid}")
        emit(
            "step1_progress",
            stage="auto-main-driver-ready",
            message=f"Bước 1: đã kết nối bằng {type(driver).__name__}",
            driver_type=type(driver).__name__,
        )

        # EngineDriver.screenshot() is authoritative here. On the currently
        # packaged touch-only DLL it automatically falls back to PCDriver capture,
        # exactly as the working AUTO does.
        frame = driver.screenshot(format="opencv")
        if frame is None or not hasattr(frame, "shape"):
            raise RuntimeError("AUTO chính không trả về frame OpenCV hợp lệ")

        import cv2

        output = work_dir / "step1-auto-main-capture.png"
        if not cv2.imwrite(str(output), frame):
            raise RuntimeError(f"Không ghi được ảnh kiểm tra: {output}")

        height, width = int(frame.shape[0]), int(frame.shape[1])
        emit(
            "step1_pass",
            stage="capture-pass",
            message="BƯỚC 1 PASS: AUTO chính đã kết nối và chụp được màn GameClientJS",
            pid=pid,
            profile_id=args.profile_id,
            profile_name=args.profile_name,
            driver_type=type(driver).__name__,
            width=width,
            height=height,
            capture=str(output),
        )
        return 0
    except Exception as exc:
        emit(
            "step1_error",
            stage="step1-failed",
            error=repr(exc),
            traceback=traceback.format_exc(),
            pid=pid,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
