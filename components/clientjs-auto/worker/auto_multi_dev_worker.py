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
    "NO_LAYOUT CAPTURE3_SYNC2 CAPTURE3_FIXEDMAP CAPTURE3_WRITERMAP2 "
    "CAPTURE3_WRITERMSG1"
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AUTO MULTI DEV isolated V3 worker")
    parser.add_argument("--auto-root", required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--profile-name", required=True)
    parser.add_argument("--profile-file", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument(
        "--mode", choices=("main", "floor-demo", "builder"), default="main"
    )
    parser.add_argument("--plan-json", default="")
    parser.add_argument("--speed-json", default="{}")
    parser.add_argument("--timeout", type=float, default=180.0)
    return parser


def _bootstrap_shared_image_runtime(auto_root: Path, profile_id: str) -> None:
    """Prepare only the clean shared image stack before Bridge V3 construction."""
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

    missing = [name for name in ("PIL", "numpy", "cv2") if name not in sys.modules]
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


def _load_builder_plan(args) -> tuple[str, dict | None]:
    """Resolve Builder only from an explicit CLI plan or per-run marker file."""
    effective_mode = str(args.mode)
    source = ""
    if args.mode == "builder":
        source = str(args.plan_json or "")
    elif args.mode == "main":
        marker = Path(args.work_dir).resolve() / "auto-builder-plan.json"
        if marker.is_file():
            source = marker.read_text(encoding="utf-8")
            effective_mode = "builder"
    if effective_mode != "builder":
        return effective_mode, None
    try:
        plan = json.loads(source)
        if not isinstance(plan, dict):
            raise ValueError("plan phải là object")
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"AUTO Builder plan không hợp lệ: {exc}") from exc
    return effective_mode, plan


def _load_auto_main_config(args, effective_mode: str) -> dict:
    """Load one GUI-selected Function schedule for this isolated run."""
    default = {
        "version": 1,
        "function_id": "function_1",
        "sale_every_loops": 1,
        "function_loop_delay_seconds": 0.0,
        "friend_refresh_enabled": False,
    }
    if effective_mode != "main":
        return default
    marker = Path(args.work_dir).resolve() / "auto-main-config.json"
    if not marker.is_file():
        return default
    try:
        raw = json.loads(marker.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"AUTO Main config JSON lỗi: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("AUTO Main config phải là object")
    if int(raw.get("version", 1) or 1) != 1:
        raise ValueError("AUTO Main config version chưa hỗ trợ")
    function_id = str(raw.get("function_id") or "function_1").strip()
    sale_every = int(raw.get("sale_every_loops", 1) or 1)
    loop_delay = float(raw.get("function_loop_delay_seconds", 0.0) or 0.0)
    friend_refresh_enabled = bool(raw.get("friend_refresh_enabled", False))
    if not function_id:
        raise ValueError("AUTO Main config thiếu function_id")
    if not 1 <= sale_every <= 999:
        raise ValueError("AUTO Main sale_every_loops phải trong 1..999")
    if not 0.0 <= loop_delay <= 3600.0:
        raise ValueError("AUTO Main function_loop_delay_seconds phải trong 0..3600")
    return {
        "version": 1,
        "function_id": function_id,
        "sale_every_loops": sale_every,
        "function_loop_delay_seconds": loop_delay,
        "friend_refresh_enabled": friend_refresh_enabled,
    }


def main() -> int:
    configure_utf8_stdio()
    args = _parser().parse_args()
    try:
        speed_values = json.loads(args.speed_json)
        if not isinstance(speed_values, dict):
            raise ValueError("speed-json phải là object")
        effective_mode, builder_plan = _load_builder_plan(args)
        auto_main_config = _load_auto_main_config(args, effective_mode)
    except (json.JSONDecodeError, ValueError) as exc:
        emit(
            "progress", workflow=WORKFLOW_NAME, profile_id=args.profile_id,
            message=f"AUTO MULTI DEV dừng yên lặng • cấu hình lỗi: {exc}",
        )
        emit(
            "worker_stopped", workflow=WORKFLOW_NAME,
            profile_id=args.profile_id, reason=str(exc),
        )
        return 2

    try:
        emit(
            "worker_started", workflow=WORKFLOW_NAME,
            profile_id=args.profile_id, pid=args.pid,
            runtime="isolated-process", bridge="V3",
            capture_owner="single-worker",
        )
        _bootstrap_shared_image_runtime(Path(args.auto_root), str(args.profile_id))

        install_component_path()
        engine_driver = importlib.import_module("engine_driver")
        engine_driver._PROTOCOL_PREFIX = _REQUIRED_BRIDGE_PROTOCOL

        from capture3_same_request import install_capture3_same_request_wait

        install_capture3_same_request_wait(engine_driver)
        emit(
            "detail", workflow=WORKFLOW_NAME, profile_id=args.profile_id,
            message=(
                "DLL bridge V3: CAPTURE3 WRITERMAP2+WRITERMSG1 ENABLED • "
                "mỗi CAPTUREW khóa đúng writer mapping + dispatch • "
                "stale frame vẫn bị từ chối"
            ),
        )

        from kvtm_automation import AutomationContext, KVAutomation
        from kvtm_automation.errors import (
            AutomationStopped,
            ClientRestartRequested,
        )
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
            f"thu VP={speed.vp_collect_delay:.3f}s | "
            f"sản xuất VP={speed.vp_production_delay:.3f}s | "
            f"check cây={speed.crop_check_interval:.3f}s"
        )

        if effective_mode == "builder":
            from kvtm_automation.workflows.auto_builder import AutoBuilderRunner

            assert builder_plan is not None
            log(
                f"AUTO Builder worker mode • plan={builder_plan.get('name') or 'AUTO tự tạo'}"
            )
            result = AutoBuilderRunner(automation, builder_plan).run()
            result_payload = result.to_dict()
            result_payload.pop("profile_id", None)
            emit(
                "worker_finished", workflow=WORKFLOW_NAME,
                profile_id=args.profile_id, outcome="auto_builder_ready",
                **result_payload,
            )
            return 0

        if effective_mode == "floor-demo":
            GameSessionWorkflow(automation).run(timeout=args.timeout)
            log(
                "PASS | startup + popup watch 60s • MAIN theo startup contract"
            )
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

        function_id = str(auto_main_config["function_id"])
        sale_every = int(auto_main_config["sale_every_loops"])
        loop_delay = float(auto_main_config["function_loop_delay_seconds"])
        friend_refresh_enabled = bool(auto_main_config["friend_refresh_enabled"])
        log(
            "AUTO MULTI DEV schedule • "
            f"function_id={function_id} • bán lại sau mỗi {sale_every} vòng • "
            f"chờ giữa vòng Function={loop_delay:.3f}s • "
            f"qua nhà bạn #1 sau mỗi 3 vòng="
            f"{'BẬT' if friend_refresh_enabled else 'TẮT'} • "
            "runtime_error_policy=typed-recovery-only • "
            "unregistered_error=fail-close"
        )

        try:
            # Startup owns the operator-approved invariant that a fresh
            # login/restart begins at MAIN. Do not manufacture another MAIN proof
            # with goDown(1) here.
            GameSessionWorkflow(automation).run(timeout=args.timeout)
            if not automation.popup.is_own_exact_main_screen():
                raise RuntimeError(
                    "Startup kết thúc nhưng exact-main contract không còn hợp lệ"
                )

            log(
                "PASS | startup + popup watch 60s • MAIN READY • "
                "bàn giao trực tiếp cho AUTO Main"
            )
            result = AutoMainWorkflow(
                automation,
                function_id=function_id,
                sale_every_loops=sale_every,
                function_loop_delay_seconds=loop_delay,
                friend_refresh_enabled=friend_refresh_enabled,
            ).run()
            result_payload = result.to_dict()
            result_payload.pop("profile_id", None)
            emit(
                "worker_finished", workflow=WORKFLOW_NAME,
                profile_id=args.profile_id, outcome="auto_main_ready",
                **result_payload,
            )
            return 0
        except ClientRestartRequested as exc:
            # Scheduled ClientJS restart is a lifecycle request, not an AUTO
            # failure and not a generic AutomationStopped. Emit a dedicated
            # lifecycle event, then a compatibility terminal event so the
            # current Multi supervisor can hand the exact profile to its restart
            # adapter without mistaking this for an unregistered runtime error.
            emit(
                "client_restart_requested", workflow=WORKFLOW_NAME,
                profile_id=args.profile_id,
                reason=str(exc),
                function_id=function_id,
            )
            emit(
                "worker_stopped", workflow=WORKFLOW_NAME,
                profile_id=args.profile_id,
                reason=str(exc),
                lifecycle_event="client_restart_requested",
                function_id=function_id,
            )
            log(
                "AUTO MULTI DEV • scheduled ClientJS restart requested at safe boundary"
            )
            return 75
        except AutomationStopped as exc:
            emit(
                "worker_stopped", workflow=WORKFLOW_NAME,
                profile_id=args.profile_id, reason=str(exc),
            )
            return 0
        except Exception as exc:
            # RecoveryManager owns all registered typed recovery. Anything that
            # escapes it is intentionally fail-close; restarting the Function or
            # blindly normalizing to MAIN here would lose the interrupted module
            # checkpoint and violate the global recovery contract.
            emit(
                "detail", workflow=WORKFLOW_NAME,
                profile_id=args.profile_id,
                message=(
                    "AUTO unregistered runtime exception • fail-close • "
                    "không restart Function/pipeline\n" + traceback.format_exc()
                ),
            )
            log(
                "AUTO MULTI DEV • lỗi chưa có recovery policy • fail-close • "
                f"{type(exc).__name__}: {exc}"
            )
            emit(
                "worker_stopped", workflow=WORKFLOW_NAME,
                profile_id=args.profile_id,
                reason=(
                    "unregistered_runtime_error; recovery=fail-close; "
                    f"error={type(exc).__name__}: {exc}"
                ),
            )
            return 1
    except Exception as exc:
        # Bootstrap/bridge failures happen before the business recovery graph is
        # available. Keep them in worker logs/status and stop without touching
        # Function state.
        emit(
            "detail", workflow=WORKFLOW_NAME, profile_id=args.profile_id,
            message="AUTO fatal bootstrap exception • popup=disabled\n" + traceback.format_exc(),
        )
        emit(
            "progress", workflow=WORKFLOW_NAME, profile_id=args.profile_id,
            message=f"AUTO MULTI DEV dừng yên lặng • {type(exc).__name__}: {exc}",
        )
        emit(
            "worker_stopped", workflow=WORKFLOW_NAME,
            profile_id=args.profile_id, reason=repr(exc),
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
