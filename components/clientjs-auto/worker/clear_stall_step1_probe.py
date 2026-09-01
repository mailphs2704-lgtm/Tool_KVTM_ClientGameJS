from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import traceback


def emit(event: str, **data) -> None:
    print(json.dumps({"event": event, **data}, ensure_ascii=False), flush=True)


def discover_game_pids() -> list[int]:
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
    return sorted({int(pid) for pid in pids})


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

    try:
        pids = [int(args.pid)] if args.pid else discover_game_pids()
        emit(
            "step1_progress",
            stage="clients-detected",
            message=f"Bước 1: phát hiện {len(pids)} GameClientJS; sẽ thử từng PID bằng AUTO chính",
            pids=pids,
        )

        # Reuse the exact bootstrap used by the working AUTO ClientJS worker.
        # Step 1 deliberately does not use any clean/resident Dọn quầy runtime.
        emit(
            "step1_progress",
            stage="bootstrap-auto-main",
            message="Bước 1: nạp đúng bootstrap AUTO chính",
        )
        from auto_worker import install_clientjs_runtime

        install_clientjs_runtime(auto_root)
        emit(
            "step1_progress",
            stage="auto-main-runtime-ready",
            message="Bước 1: runtime AUTO chính đã sẵn sàng",
        )

        # AUTO chính patches uiautomator2.connect("PC:<pid>") to EngineDriver.
        import uiautomator2 as u2
        import cv2

        successes: list[dict] = []
        failures: list[dict] = []
        for pid in pids:
            try:
                emit(
                    "step1_progress",
                    stage="auto-main-driver-connecting",
                    message=f"Bước 1: thử PID {pid}",
                    pid=pid,
                )
                driver = u2.connect(f"PC:{pid}")
                emit(
                    "step1_progress",
                    stage="auto-main-driver-ready",
                    message=f"Bước 1: PID {pid} đã kết nối bằng {type(driver).__name__}",
                    pid=pid,
                    driver_type=type(driver).__name__,
                )

                # EngineDriver.screenshot() is authoritative. With the current
                # touch-only DLL it falls back to PCDriver capture, exactly as
                # the working AUTO does.
                frame = driver.screenshot(format="opencv")
                if frame is None or not hasattr(frame, "shape"):
                    raise RuntimeError("AUTO chính không trả về frame OpenCV hợp lệ")

                output = work_dir / f"step1-auto-main-capture-pid-{pid}.png"
                if not cv2.imwrite(str(output), frame):
                    raise RuntimeError(f"Không ghi được ảnh kiểm tra: {output}")

                height, width = int(frame.shape[0]), int(frame.shape[1])
                result = {
                    "pid": pid,
                    "driver_type": type(driver).__name__,
                    "width": width,
                    "height": height,
                    "capture": str(output),
                }
                successes.append(result)
                emit(
                    "step1_pid_pass",
                    stage="capture-pass",
                    message=f"Bước 1: PID {pid} chụp ảnh PASS",
                    **result,
                )
            except Exception as exc:
                failure = {
                    "pid": pid,
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                }
                failures.append(failure)
                emit(
                    "step1_pid_error",
                    stage="capture-failed",
                    message=f"Bước 1: PID {pid} lỗi; tiếp tục PID khác",
                    **failure,
                )

        if not successes:
            emit(
                "step1_error",
                stage="step1-failed",
                error="Không PID GameClientJS nào chụp ảnh PASS bằng luồng AUTO chính",
                failures=failures,
            )
            return 1

        emit(
            "step1_pass",
            stage="capture-pass",
            message="BƯỚC 1 PASS: AUTO chính đã kết nối và chụp được ít nhất một GameClientJS",
            profile_id=args.profile_id,
            profile_name=args.profile_name,
            detected_pids=pids,
            successes=successes,
            failures=failures,
        )
        return 0
    except Exception as exc:
        emit(
            "step1_error",
            stage="step1-failed",
            error=repr(exc),
            traceback=traceback.format_exc(),
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
