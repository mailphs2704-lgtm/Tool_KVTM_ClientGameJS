from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import sys
import time
import traceback

from clean_worker_support import (
    StopChannel,
    configure_utf8_stdio,
    emit,
    install_component_path,
)


WORKFLOW_NAME = "auto_multi_dev_main"
_AUTO_MAIN_FRESH_MARKER = ".fresh-client-start.json"
_FRESH_MARKER_MAX_AGE_SECONDS = 300.0
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
        "--mode", choices=("main", "function-3-step-1", "builder"), default="main"
    )
    parser.add_argument(
        "--startup-mode", choices=("auto", "fresh", "reentry"), default="auto"
    )
    parser.add_argument("--plan-json", default="")
    parser.add_argument("--speed-json", default="{}")
    parser.add_argument("--timeout", type=float, default=180.0)
    return parser


def _resolve_startup_mode(args) -> tuple[str, str]:
    """Resolve fresh ClientJS startup vs AUTO re-entry without camera guessing.

    The DEV parent writes a one-shot marker only when AUTO Main itself had to
    launch this exact ClientJS process. An already-running/adopted ClientJS has
    no marker and therefore always re-enters through bounded unknown-camera
    recovery. Explicit CLI modes remain available for diagnostics.
    """
    requested = str(args.startup_mode)
    if requested in {"fresh", "reentry"}:
        return requested, f"explicit:{requested}"

    marker = Path(args.work_dir).resolve().parent / _AUTO_MAIN_FRESH_MARKER
    if not marker.is_file():
        return "reentry", "no-fresh-launch-marker"

    try:
        raw = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        try:
            marker.unlink(missing_ok=True)
        except OSError:
            pass
        return "reentry", f"invalid-fresh-launch-marker:{type(exc).__name__}"

    # One launch marker authorizes exactly one startup decision. Consume it
    # before any image/bootstrap work so a failed worker cannot later mislabel
    # the same still-running ClientJS as a second fresh login.
    try:
        marker.unlink(missing_ok=True)
    except OSError:
        pass

    if not isinstance(raw, dict):
        return "reentry", "fresh-launch-marker-not-object"

    try:
        version = int(raw.get("version", 0) or 0)
        marker_pid = int(raw.get("pid", 0) or 0)
        created_at = float(raw.get("created_at", 0.0) or 0.0)
    except (TypeError, ValueError):
        return "reentry", "fresh-launch-marker-fields-invalid"

    marker_profile = str(raw.get("profile_id") or "")
    age = time.time() - created_at
    if version != 1:
        return "reentry", f"fresh-launch-marker-version:{version}"
    if marker_profile != str(args.profile_id):
        return "reentry", "fresh-launch-marker-profile-mismatch"
    if marker_pid != int(args.pid):
        return "reentry", "fresh-launch-marker-pid-mismatch"
    if age < -5.0 or age > _FRESH_MARKER_MAX_AGE_SECONDS:
        return "reentry", f"fresh-launch-marker-stale:{age:.1f}s"
    return "fresh", f"fresh-launch-marker-match:age={age:.1f}s"


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
        "warehouse_upgrade_enabled": False,
        "warehouse_upgrade_mode": "warehouse_1",
        "warehouse_upgrade_interval_hours": 2,
        "warehouse_upgrade_allow_diamond_slot_delete": False,
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
    warehouse_enabled = bool(raw.get("warehouse_upgrade_enabled", False))
    warehouse_mode = str(raw.get("warehouse_upgrade_mode", "warehouse_1"))
    if warehouse_mode not in {"warehouse_1", "warehouse_2", "both", "max"}:
        raise ValueError("AUTO Main warehouse_upgrade_mode không hợp lệ")
    warehouse_hours = int(raw.get("warehouse_upgrade_interval_hours", 2) or 2)
    if not 1 <= warehouse_hours <= 168:
        raise ValueError("AUTO Main warehouse_upgrade_interval_hours phải trong 1..168")
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
        "warehouse_upgrade_enabled": warehouse_enabled,
        "warehouse_upgrade_mode": warehouse_mode,
        "warehouse_upgrade_interval_hours": warehouse_hours,
        "warehouse_upgrade_allow_diamond_slot_delete": bool(
            raw.get("warehouse_upgrade_allow_diamond_slot_delete", False)
        ),
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
        startup_mode, startup_mode_reason = _resolve_startup_mode(args)
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

    emit(
        "detail", workflow=WORKFLOW_NAME, profile_id=args.profile_id,
        message=(
            "AUTO lifecycle resolve | "
            f"requested={args.startup_mode} | resolved={startup_mode} | "
            f"reason={startup_mode_reason} | client_pid={int(args.pid)}"
        ),
    )

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
        from kvtm_automation.errors import AutomationStopped
        from kvtm_automation.workflows.game_session import GameSessionWorkflow

        channel = StopChannel(
            on_stop=lambda command: emit(
                "worker_stopping", workflow=WORKFLOW_NAME,
                profile_id=args.profile_id, command=command,
            )
        )
        channel.start()

        def action(message: str) -> None:
            emit(
                "progress", workflow=WORKFLOW_NAME,
                profile_id=args.profile_id, message=str(message),
            )

        def detail(message: str) -> None:
            emit(
                "detail", workflow=WORKFLOW_NAME,
                profile_id=args.profile_id, message=str(message),
            )

        def log(message: str) -> None:
            """Worker/bootstrap chatter belongs to Log chi tiết, not action milestones."""
            detail(message)

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
            logger=action,
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

        def prepare_runtime_camera() -> None:
            if startup_mode == "fresh":
                log(
                    "AUTO lifecycle • fresh ClientJS • chạy startup popup watch 60s"
                )
                GameSessionWorkflow(automation).run(timeout=args.timeout)
                if not automation.popup.is_own_exact_main_screen():
                    raise RuntimeError(
                        "Startup kết thúc nhưng exact-main contract không còn hợp lệ"
                    )
                log(
                    "PASS | fresh startup + popup watch 60s • MAIN READY"
                )
                return

            from kvtm_automation.recovery import RecoveryManager

            log(
                "AUTO lifecycle • re-entry trên ClientJS đang chạy • "
                "bỏ popup startup 60s • recovery unknown → exact MAIN"
            )
            recovery = RecoveryManager(
                automation,
                function_id="lifecycle_reentry",
            )
            recovery.recover_unknown_to_main(
                "AUTO re-entry existing ClientJS",
                reason="auto-reentry-existing-client",
            )
            if not automation.popup.is_own_exact_main_screen():
                raise RuntimeError(
                    "AUTO re-entry recovery kết thúc nhưng chưa chứng minh exact-main"
                )
            log(
                "PASS | AUTO re-entry • exact MAIN READY • popup startup đã bỏ qua"
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

        if effective_mode == "function-3-step-1":
            from kvtm_automation.workflows.auto_function_three import (
                FunctionThreeWorkflow,
            )

            prepare_runtime_camera()
            log(
                "AUTO MULTI DEV TEST • chạy liền Function 3 Step 1 → Step 2 → Step 3 • "
                "bắt đầu từ exact MAIN • không vào AUTO Main"
            )
            result = FunctionThreeWorkflow(automation).run_steps_1_2_and_3()
            result_payload = result.to_dict()
            result_payload.pop("profile_id", None)
            log(
                "AUTO MULTI DEV TEST • Function 3 Step 1-3 DONE • "
                f"Step2 Trà={result.planted_teas}/24 • Nước táo={result.apple_juices}/9 • "
                f"Step3 Trà hàng dưới={result.planted_tea_bottom_row}/3 • "
                f"Bông={result.cotton_planted}/27 • Vải vàng={result.yellow_fabrics}/9 • "
                f"đứng tầng {result.end_floor}"
            )
            emit(
                "worker_finished", workflow=WORKFLOW_NAME,
                profile_id=args.profile_id,
                outcome="function_3_step_1_finished",
                **result_payload,
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
            f"startup_mode={startup_mode} • "
            "runtime_error_policy=typed-checkpoint-first+global-fallback • "
            "unregistered_error=ESCx3->stay->exact-main->friend1->resume-same-loop • "
            "client_restart=BLOCK"
        )

        try:
            prepare_runtime_camera()
            log(
                "PASS | lifecycle camera READY • bàn giao trực tiếp cho AUTO Main"
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
        except AutomationStopped as exc:
            emit(
                "worker_stopped", workflow=WORKFLOW_NAME,
                profile_id=args.profile_id, reason=str(exc),
            )
            return 0
        except Exception as exc:
            # Normal AUTO Main runtime exceptions are recovered inside
            # AutoMainWorkflow. This last-resort lifecycle catch remains only for
            # failures outside/around that recovery graph.
            emit(
                "detail", workflow=WORKFLOW_NAME,
                profile_id=args.profile_id,
                message=(
                    "AUTO unregistered runtime exception • fail-close • "
                    "outside global AUTO Main recovery graph\n" + traceback.format_exc()
                ),
            )
            log(
                "AUTO MULTI DEV • lỗi nằm ngoài global AUTO Main recovery graph • "
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
