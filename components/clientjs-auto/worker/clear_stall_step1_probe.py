from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import traceback


def emit(event: str, **data) -> None:
    print(json.dumps({"event": event, **data}, ensure_ascii=False), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto-root", required=True)
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--profile-name", required=True)
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()

    auto_root = Path(args.auto_root).resolve()
    work_dir = Path(args.work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        emit(
            "step1_progress",
            stage="bootstrap-auto-main",
            message="Bước 1: nạp đúng bootstrap AUTO chính",
            pid=args.pid,
        )

        # Reuse the exact runtime bootstrap used by the working AUTO ClientJS.
        # This intentionally does not use the new clean/resident bridge stack.
        from auto_worker import install_clientjs_runtime

        install_clientjs_runtime(auto_root)
        emit(
            "step1_progress",
            stage="auto-main-runtime-ready",
            message="Bước 1: runtime AUTO chính đã sẵn sàng",
        )

        # The working AUTO patches uiautomator2.connect("PC:<pid>") to EngineDriver.
        import uiautomator2 as u2

        driver = u2.connect(f"PC:{args.pid}")
        emit(
            "step1_progress",
            stage="auto-main-driver-ready",
            message=f"Bước 1: đã kết nối bằng {type(driver).__name__}",
            driver_type=type(driver).__name__,
        )

        # Capture exactly as the working EngineDriver does. Its screenshot()
        # already falls back to PCDriver capture when the injected DLL is an old
        # touch-only build without CAPTURE support.
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
            pid=args.pid,
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
            pid=args.pid,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
