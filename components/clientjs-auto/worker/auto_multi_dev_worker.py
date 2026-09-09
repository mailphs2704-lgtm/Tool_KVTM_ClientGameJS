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
_REQUIRED_BRIDGE_PROTOCOL = (
    "OK PONG KVTM_BRIDGE_V3 CAPTURE3 INPUT4 BATCH_SWIPE "
    "NO_LAYOUT CAPTURE3_SYNC2 CAPTURE3_FIXEDMAP CAPTURE3_WRITERMAP2 "
    "CAPTURE3_WRITERMSG1"
)
# Runtime errors are handled inside the worker. Multi must not interrupt the
# operator with modal error dialogs for transient image/navigation failures.
# A repeated identical failure is bounded so a deterministic code bug cannot
# create an endless recovery loop.
_AUTO_MAIN_SAME_ERROR_LIMIT = 10
_AUTO_MAIN_RECOVERY_NAV_ATTEMPTS = 8
_AUTO_MAIN_PASSIVE_MAIN_TIMEOUT = 2.5


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
    }


def _error_signature(exc: BaseException) -> str:
    """Stable short signature used only for the repeated-error circuit breaker."""
    return f"{type(exc).__name__}: {str(exc)}"


def _recover_auto_main_to_main_screen(automation, context, *, reason: str) -> bool:
    """Normalize an unknown own-farm camera state back to true exact-main.

    ``PopupActions.is_own_main_screen`` is intentionally only an own-farm HUD
    classifier: the same HUD remains visible on floor 1/2/3/... . Recovery must
    therefore never accept that signal as exact-main. First close modal/portal
    state, then require the dedicated world-space stall anchor. If that anchor is
    absent, send bounded goDown(1) steps and re-check the exact-main anchor after
    every step. This safely recovers a failure that happened on floor 2 without
    restarting the sale loop from the wrong camera position.
    """
    context.stage("auto-main-error-recovery-start")
    context.log(
        "AUTO MULTI DEV main-normalize • đưa camera về exact-main • "
        f"reason={reason}"
    )

    # First make sure we are on our own farm and any blocking panel is closed.
    # This may return while the camera is still on an upper farm floor; that is
    # expected. Only is_own_exact_main_screen() is allowed to finish recovery.
    try:
        automation.ensure_main_screen(timeout=_AUTO_MAIN_PASSIVE_MAIN_TIMEOUT)
    except Exception as exc:
        context.detail(
            "AUTO recovery farm-HUD preflight nonfatal • "
            f"{type(exc).__name__}: {exc}"
        )

    try:
        if automation.popup.is_own_exact_main_screen():
            context.stage("auto-main-error-recovery-main-ready")
            context.log("AUTO recovery PASS • exact-main đã sẵn sàng trước khi goDown")
            return True
    except Exception as exc:
        context.detail(
            "AUTO recovery initial exact-main probe nonfatal • "
            f"{type(exc).__name__}: {exc}"
        )

    for attempt in range(1, _AUTO_MAIN_RECOVERY_NAV_ATTEMPTS + 1):
        context.ensure_running()
        try:
            change = automation.function_one_pass_three_navigation.go_down_one_toward_main(
                f"auto-error-recovery-goDown(1)-{attempt}-of-"
                f"{_AUTO_MAIN_RECOVERY_NAV_ATTEMPTS}"
            )
            context.detail(
                "AUTO recovery goDown(1) • "
                f"attempt={attempt}/{_AUTO_MAIN_RECOVERY_NAV_ATTEMPTS} • "
                f"frame_change={float(change):.2f}"
            )
        except Exception as exc:
            # Recovery navigation is deliberately non-fatal. A stale frame or
            # boundary can fail one probe; the next exact-main check decides.
            context.detail(
                "AUTO recovery goDown(1) nonfatal • "
                f"attempt={attempt}/{_AUTO_MAIN_RECOVERY_NAV_ATTEMPTS} • "
                f"{type(exc).__name__}: {exc}"
            )

        try:
            if automation.popup.is_own_exact_main_screen():
                context.stage("auto-main-error-recovery-main-ready")
                context.log(
                    f"AUTO recovery PASS • exact-main sau goDown {attempt}/"
                    f"{_AUTO_MAIN_RECOVERY_NAV_ATTEMPTS}"
                )
                return True
        except Exception as exc:
            context.detail(
                "AUTO recovery exact-main probe nonfatal • "
                f"attempt={attempt}/{_AUTO_MAIN_RECOVERY_NAV_ATTEMPTS} • "
                f"{type(exc).__name__}: {exc}"
            )

    context.stage("auto-main-error-recovery-not-ready")
    context.log(
        "AUTO recovery chưa về exact-main sau "
        f"{_AUTO_MAIN_RECOVERY_NAV_ATTEMPTS} nhịp • dừng yên lặng để tránh thao tác mù"
    )
    return False


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
        # Configuration failures are terminal but still non-modal in Multi.
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
        from kvtm_automation.errors import AutomationStopped, ScreenTimeout
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

        # Floor demo keeps the old one-shot behavior. Resilient restart is only
        # enabled for the continuous AUTO Main pipeline.
        if effective_mode == "floor-demo":
            GameSessionWorkflow(automation).run(timeout=args.timeout)
            log(
                "PASS | vào game/đóng popup • chuẩn bị chạy Function đã chọn và bán VP theo Function"
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
        log(
            "AUTO MULTI DEV schedule • "
            f"function_id={function_id} • bán lại sau mỗi {sale_every} vòng • "
            f"chờ giữa vòng Function={loop_delay:.3f}s • "
            f"runtime_error_policy=recover-main-restart • "
            f"same_error_limit={_AUTO_MAIN_SAME_ERROR_LIMIT}"
        )

        last_error_signature = ""
        same_error_count = 0
        restart_ordinal = 0

        while True:
            context.ensure_running()
            try:
                GameSessionWorkflow(automation).run(timeout=args.timeout)

                # GameSession intentionally owns only portal/popup/own-farm HUD
                # recovery and does not move the camera. Before sale #1 or any
                # Function restart, require the world-space exact-main anchor.
                # This makes starting AUTO while the client is already on floor 2
                # safe: the worker normalizes downward before touching the stall.
                if not automation.popup.is_own_exact_main_screen():
                    log(
                        "AUTO MULTI DEV • farm HUD READY nhưng camera chưa ở exact-main "
                        "• chuẩn hóa xuống màn hình chính trước khi chạy scheduler"
                    )
                    normalized = _recover_auto_main_to_main_screen(
                        automation,
                        context,
                        reason="pipeline-start-camera-normalize",
                    )
                    if not normalized:
                        raise ScreenTimeout(
                            "Không chuẩn hóa được camera về exact-main trước AUTO Main"
                        )

                log(
                    "PASS | vào game/đóng popup • exact-main READY • "
                    "chuẩn bị chạy Function đã chọn và bán VP theo Function"
                )
                if restart_ordinal:
                    log(
                        f"AUTO MULTI DEV recovery • chạy lại pipeline từ main • "
                        f"restart={restart_ordinal}"
                    )

                result = AutoMainWorkflow(
                    automation,
                    function_id=function_id,
                    sale_every_loops=sale_every,
                    function_loop_delay_seconds=loop_delay,
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
                signature = _error_signature(exc)
                if signature == last_error_signature:
                    same_error_count += 1
                else:
                    last_error_signature = signature
                    same_error_count = 1
                restart_ordinal += 1

                emit(
                    "detail", workflow=WORKFLOW_NAME,
                    profile_id=args.profile_id,
                    message=(
                        "AUTO runtime exception captured internally • popup=disabled • "
                        f"restart={restart_ordinal} • same_error="
                        f"{same_error_count}/{_AUTO_MAIN_SAME_ERROR_LIMIT}\n"
                        + traceback.format_exc()
                    ),
                )
                log(
                    "AUTO MULTI DEV • bắt lỗi nội bộ, KHÔNG hiện popup • "
                    f"{signature} • cùng lỗi {same_error_count}/"
                    f"{_AUTO_MAIN_SAME_ERROR_LIMIT} • đang đưa về main"
                )

                recovered = _recover_auto_main_to_main_screen(
                    automation, context, reason=signature
                )
                if not recovered:
                    log(
                        "AUTO MULTI DEV • recovery không xác minh được main • "
                        "dừng yên lặng để tránh thao tác sai trạng thái"
                    )
                    emit(
                        "worker_stopped", workflow=WORKFLOW_NAME,
                        profile_id=args.profile_id,
                        reason=(
                            "recovery_not_main_ready; popup_disabled; "
                            f"last_error={signature}"
                        ),
                    )
                    return 0

                if same_error_count >= _AUTO_MAIN_SAME_ERROR_LIMIT:
                    log(
                        "AUTO MULTI DEV • cùng lỗi đã lặp đủ "
                        f"{_AUTO_MAIN_SAME_ERROR_LIMIT} lần • đã về main • "
                        "tạm dừng yên lặng để tránh vòng lặp vô hạn"
                    )
                    emit(
                        "worker_stopped", workflow=WORKFLOW_NAME,
                        profile_id=args.profile_id,
                        reason=(
                            "same_error_limit_reached; main_ready=true; "
                            f"last_error={signature}"
                        ),
                    )
                    return 0

                # Small cooperative settle after exact-main recovery. The next
                # iteration reruns GameSession and then starts AUTO Main fresh.
                context.ensure_running()
                automation.wait.sleep(0.75)
                continue
    except Exception as exc:
        # Bootstrap/bridge failures happen before the resilient pipeline exists.
        # Keep them in logs/status only; never ask the GUI to open an error modal.
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