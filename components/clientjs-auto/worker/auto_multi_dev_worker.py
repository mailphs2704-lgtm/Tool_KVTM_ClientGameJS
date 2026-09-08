from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import sys
import traceback

from clean_worker_support import (
    StopChannel,
    configure_utf8_stdio,
    emit,
    install_component_path,
)


WORKFLOW_NAME = "auto_multi_dev_main"
_REQUIRED_BRIDGE_PROTOCOL = (
    "OK PONG KVTM_BRIDGE_V3 CAPTURE3 INPUT4 BATCH_SWIPE "
    "NO_LAYOUT CAPTURE3_SYNC2 CAPTURE3_FIXEDMAP CAPTURE3_WRITERMAP2"
)


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


def _bootstrap_shared_image_runtime(auto_root: Path, profile_id: str) -> None:
    """Prepare only the clean shared image stack before Bridge V3 construction.

    Do not import ``local_launcher`` here. It belongs to the AUTO PRO runtime
    and can enter native robot-image initialization before the isolated Multi Dev
    worker reaches EngineDriver. Multi Dev needs only packaged Pillow/OpenCV/NumPy
    plus adaptive matching at this stage. EngineDriver remains the V3 transport.
    """

    root = Path(auto_root).resolve()
    install_component_path()
    os.environ["KVTM_SKIP_RUNTIME_SYNC"] = "1"

    def bootstrap_log(message: str) -> None:
        emit(
            "detail", workflow=WORKFLOW_NAME, profile_id=profile_id,
            message=str(message),
        )

    emit(
        "detail", workflow=WORKFLOW_NAME, profile_id=profile_id,
        message="Image bootstrap: shared clean runtime START",
    )
    from shared_runtime.image_runtime import install_binary_dependencies

    install_binary_dependencies(root, logger=bootstrap_log)

    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    adaptive_cv = importlib.import_module("adaptive_cv")
    adaptive_cv.install_adaptive_matching()

    missing = [
        name for name in ("PIL", "numpy", "cv2")
        if name not in sys.modules
    ]
    if missing:
        raise RuntimeError(
            "Shared image runtime không nạp đủ module: " + ", ".join(missing)
        )
    emit(
        "detail", workflow=WORKFLOW_NAME, profile_id=profile_id,
        message=(
            "Image bootstrap: shared clean runtime READY • "
            "PIL/numpy/cv2 resident • local_launcher=disabled"
        ),
    )


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

    try:
        emit(
            "worker_started", workflow=WORKFLOW_NAME,
            profile_id=args.profile_id, pid=args.pid,
            runtime="isolated-process", bridge="V3",
            capture_owner="single-worker",
        )
        _bootstrap_shared_image_runtime(
            Path(args.auto_root), str(args.profile_id)
        )

        install_component_path()
        # Multi Dev requires the exact current native revision. WRITERMAP2 binds
        # every CAPTUREW response to the unique shared mapping owned by the same
        # injected writer, preventing a PID-only mapping from being confused with
        # another resident/generation when dimensions or frame counters overlap.
        engine_driver = importlib.import_module("engine_driver")
        engine_driver._PROTOCOL_PREFIX = _REQUIRED_BRIDGE_PROTOCOL

        from capture3_same_request import install_capture3_same_request_wait

        install_capture3_same_request_wait(engine_driver)
        emit(
            "detail", workflow=WORKFLOW_NAME, profile_id=args.profile_id,
            message=(
                "DLL bridge V3: CAPTURE3 WRITERMAP2 ENABLED • "
                "mỗi CAPTUREW khóa đúng writer mapping • stale frame vẫn bị từ chối"
            ),
        )

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
        automation = KVAutomation(
            context,
            image_runtime_ready=True,
            speed_config=speed_values,
        )
        emit(
            "runtime_ready", workflow=WORKFLOW_NAME,
            profile_id=args.profile_id, bridge="V3",
            image_runtime="shared-clean-bootstrap",
        )
        speed = automation.speed_config
        log(
            "Tốc độ MULTI DEV | "
            f"kéo tầng={speed.floor_swipe_duration:.3f}s | "
            f"trồng/thu={speed.plant_harvest_duration:.3f}s | "
            f"sản xuất VP={speed.vp_production_delay:.3f}s | "
            f"check cây={speed.crop_check_interval:.3f}s"
        )
        GameSessionWorkflow(automation).run(timeout=args.timeout)
        log(
            "PASS | vào game/đóng popup và chuẩn bị startup route; "
            "exact-main gate chỉ chạy ở transition nghiệp vụ"
        )

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
        result_payload = result.to_dict()
        result_payload.pop("profile_id", None)
        emit(
            "worker_finished", workflow=WORKFLOW_NAME,
            profile_id=args.profile_id, outcome="auto_main_ready",
            **result_payload,
        )
        return 0
    except Exception as exc:
        try:
            if "AutomationStopped" in locals() and isinstance(exc, AutomationStopped):
                emit(
                    "worker_stopped", workflow=WORKFLOW_NAME,
                    profile_id=args.profile_id, reason=str(exc),
                )
                return 0
        except Exception:
            pass
        emit(
            "worker_error", workflow=WORKFLOW_NAME,
            profile_id=args.profile_id, error=repr(exc),
            traceback=traceback.format_exc(),
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
