from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import sys
import threading
import traceback

from clean_worker_support import (
    StopChannel,
    configure_utf8_stdio,
    emit,
    install_component_path,
)


WORKFLOW_NAME = "auto_multi_dev_main"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AUTO MULTI DEV isolated V3 worker")
    parser.add_argument("--auto-root", required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--profile-name", required=True)
    parser.add_argument("--profile-file", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--mode", choices=("main", "floor-demo"), default="main")
    parser.add_argument("--speed-json", default="{}")
    parser.add_argument("--timeout", type=float, default=180.0)
    return parser


def main() -> int:
    configure_utf8_stdio()
    args = _parser().parse_args()
    try:
        speed_values = json.loads(args.speed_json)
        if not isinstance(speed_values, dict):
            raise ValueError("speed-json phải là object")
    except (json.JSONDecodeError, ValueError) as exc:
        emit("worker_error", workflow=WORKFLOW_NAME, error=str(exc))
        return 2

    install_component_path()
    from kvtm_automation import AutomationContext, KVAutomation
    from kvtm_automation.errors import AutomationStopped
    from kvtm_automation.workflows.game_session import GameSessionWorkflow

    channel = StopChannel(
        on_stop=lambda command: emit(
            "worker_stopping", workflow=WORKFLOW_NAME,
            profile_id=args.profile_id, command=command,
        )
    )
    channel.start()

    def log(message: str) -> None:
        emit(
            "progress", workflow=WORKFLOW_NAME,
            profile_id=args.profile_id, message=str(message),
        )

    def detail(message: str) -> None:
        emit(
            "detail", workflow=WORKFLOW_NAME,
            profile_id=args.profile_id, message=str(message),
        )

    def stage(name: str) -> None:
        emit(
            "stage", workflow=WORKFLOW_NAME,
            profile_id=args.profile_id, stage=str(name), message=str(name),
        )

    context = AutomationContext(
        pid=args.pid,
        profile_id=args.profile_id,
        profile_name=args.profile_name,
        auto_root=Path(args.auto_root),
        work_dir=Path(args.work_dir),
        stop_event=channel.event,
        logger=log,
        stage_reporter=stage,
        detail_logger=detail,
        profile_file=Path(args.profile_file),
    )

    try:
        runtime_ready = threading.Event()

        def runtime_watchdog() -> None:
            if runtime_ready.wait(90.0):
                return
            emit(
                "worker_error", workflow=WORKFLOW_NAME,
                profile_id=args.profile_id,
                error="Runtime ảnh worker bị treo quá 90 giây",
                stage="image-runtime-loading",
            )
            os._exit(86)

        threading.Thread(
            target=runtime_watchdog,
            name="auto-multi-dev-worker-watchdog",
            daemon=True,
        ).start()
        emit(
            "worker_started", workflow=WORKFLOW_NAME,
            profile_id=args.profile_id, pid=args.pid,
            runtime="isolated-process", bridge="V3",
            capture_owner="single-worker",
        )

        # Use the exact image/bootstrap route already proven by the historical
        # AUTO worker. This is technical runtime preparation only; the clean
        # Multi Dev workflow and assets remain the sole business implementation.
        auto_root = Path(args.auto_root).resolve()
        auto_root_text = str(auto_root)
        if auto_root_text not in sys.path:
            sys.path.insert(0, auto_root_text)
        os.environ["KVTM_SKIP_RUNTIME_SYNC"] = "1"
        detail("Image bootstrap: local_launcher proven route START")
        importlib.import_module("local_launcher")
        # engine_driver imports adaptive_cv, which initializes the same
        # NumPy/OpenCV stack used successfully by the AUTO PRO worker.
        importlib.import_module("engine_driver")
        adaptive_cv = importlib.import_module("adaptive_cv")
        adaptive_cv.install_adaptive_matching()
        missing_image_modules = [
            name for name in ("PIL", "numpy", "cv2")
            if name not in sys.modules
        ]
        if missing_image_modules:
            raise RuntimeError(
                "Bootstrap AUTO PRO không nạp đủ image runtime: "
                + ", ".join(missing_image_modules)
            )
        detail(
            "Image bootstrap: proven route READY • "
            "PIL/numpy/cv2 đã resident trong worker độc lập"
        )

        automation = KVAutomation(
            context,
            image_runtime_ready=True,
            speed_config=speed_values,
        )
        runtime_ready.set()
        speed = automation.speed_config
        log(
            "Tốc độ MULTI DEV | "
            f"kéo tầng={speed.floor_swipe_duration:.3f}s | "
            f"trồng/thu={speed.plant_harvest_duration:.3f}s | "
            f"sản xuất VP={speed.vp_production_delay:.3f}s | "
            f"check cây={speed.crop_check_interval:.3f}s"
        )
        session = GameSessionWorkflow(automation).run(timeout=args.timeout)
        log("PASS | vào game, đóng popup, xác nhận màn hình chính")

        if args.mode == "floor-demo":
            context.stage("floor-demo-1-to-6-start")
            movement = automation.floors.reference_main_to_floor_6()
            emit(
                "worker_finished", workflow=WORKFLOW_NAME,
                profile_id=args.profile_id, outcome="floor_demo_finished",
                requested_steps=movement.requested_steps,
                completed_steps=movement.completed_steps,
                frame_change_scores=list(movement.frame_change_scores),
            )
            return 0

        from kvtm_automation.workflows.auto_main import AutoMainWorkflow
        result = AutoMainWorkflow(automation).run()
        emit(
            "worker_finished", workflow=WORKFLOW_NAME,
            profile_id=args.profile_id, outcome="auto_main_ready",
            **result.to_dict(),
        )
        return 0
    except AutomationStopped as exc:
        emit(
            "worker_stopped", workflow=WORKFLOW_NAME,
            profile_id=args.profile_id, reason=str(exc),
        )
        return 0
    except Exception as exc:
        emit(
            "worker_error", workflow=WORKFLOW_NAME,
            profile_id=args.profile_id, error=repr(exc),
            traceback=traceback.format_exc(),
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
