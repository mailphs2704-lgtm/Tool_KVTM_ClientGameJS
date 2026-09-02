from __future__ import annotations

import argparse
from pathlib import Path
import os
import sys
import threading
import traceback

from clean_worker_support import (
    StopChannel,
    configure_utf8_stdio,
    emit,
    install_component_path,
)


WORKFLOW_NAME = "clear_stall_clean"
REQUIRED_STALL_VIEWS = 4
EXECUTION_GATE = "READ_ONLY_SCAN"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KVTM Multi clean Dọn quầy worker"
    )
    parser.add_argument("--auto-root", required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--profile-name", required=True)
    parser.add_argument("--friend-ordinal", type=int, required=True)
    # Historical UI/CLI name. Internally this is the clone inventory category
    # used when locating VP for resale, not a second physical friend stall.
    parser.add_argument("--stall-id", dest="resale_storage_id", type=int, required=True)
    parser.add_argument("--quantity", type=int, required=True)
    # Kept only so older Multi launchers remain compatible. The clean scanner
    # always uses exactly four overlapping views to cover 20 physical slots.
    parser.add_argument("--max-pages", type=int, default=REQUIRED_STALL_VIEWS)
    parser.add_argument("--work-dir", required=True)
    return parser


def _validate(args: argparse.Namespace) -> None:
    if not 1 <= int(args.friend_ordinal) <= 7:
        raise ValueError(
            "Bạn bè số phải trong khoảng 1..7 cho đường điều hướng đã xác nhận"
        )
    if not 1 <= int(args.resale_storage_id) <= 5:
        raise ValueError("Kho VP bán lại phải trong khoảng 1..5")
    if not 10 <= int(args.quantity) <= 1000:
        raise ValueError("Số lượng mua phải trong khoảng 10..1000 VP")
    if int(args.quantity) % 10:
        raise ValueError("Số lượng Dọn quầy phải là bội số của 10 VP")
    if int(args.max_pages) < REQUIRED_STALL_VIEWS:
        raise ValueError("Dọn đủ 20 ô cần đúng 4 view quầy")


def main() -> int:
    configure_utf8_stdio()
    args = _parser().parse_args()

    emit(
        "worker_boot",
        pid=args.pid,
        profile_id=args.profile_id,
        profile_name=args.profile_name,
        workflow=WORKFLOW_NAME,
        stage="process_started",
    )

    try:
        _validate(args)
    except Exception as exc:
        emit("worker_error", error=str(exc), workflow=WORKFLOW_NAME)
        return 2

    emit(
        "worker_boot",
        pid=args.pid,
        profile_id=args.profile_id,
        workflow=WORKFLOW_NAME,
        stage="clean_runtime_importing",
    )
    install_component_path()

    from kvtm_automation import AutomationContext, KVAutomation
    from kvtm_automation.errors import AutomationStopped
    from kvtm_automation.workflows.clear_stall import (
        ClearStallRequest,
        ClearStallWorkflow,
    )

    channel = StopChannel(
        on_stop=lambda command: emit(
            "worker_stopping",
            reason="user",
            command=command,
            workflow=WORKFLOW_NAME,
        )
    )
    channel.start()

    def log(message: str) -> None:
        emit("progress", message=str(message), workflow=WORKFLOW_NAME)

    def stage(stage_name: str) -> None:
        emit(
            "progress",
            message=str(stage_name),
            stage=str(stage_name),
            workflow=WORKFLOW_NAME,
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
    )

    workflow = None
    try:
        emit(
            "worker_boot",
            pid=args.pid,
            profile_id=args.profile_id,
            workflow=WORKFLOW_NAME,
            stage="clientjs_engine_connecting",
        )
        runtime_ready = threading.Event()

        def runtime_watchdog() -> None:
            if runtime_ready.wait(90.0):
                return
            emit(
                "worker_error",
                profile_id=args.profile_id,
                workflow=WORKFLOW_NAME,
                error=(
                    "Clean image runtime bị treo quá 90s khi cold-load đồng bộ; "
                    "worker dừng an toàn trước navigation/mua/bán"
                ),
                diagnostics={
                    "source_file": str(Path(__file__).name),
                    "function": "runtime_watchdog",
                    "stage": "clean_runtime_importing",
                },
            )
            os._exit(86)

        threading.Thread(
            target=runtime_watchdog,
            name="kvtm-clean-runtime-watchdog",
            daemon=True,
        ).start()
        automation = KVAutomation(context)
        runtime_ready.set()
        emit(
            "worker_boot",
            pid=args.pid,
            profile_id=args.profile_id,
            workflow=WORKFLOW_NAME,
            stage="clientjs_engine_ready",
        )

        request = ClearStallRequest(
            profile_id=args.profile_id,
            friend_ordinal=args.friend_ordinal,
            resale_storage_id=args.resale_storage_id,
            buy_quantity=args.quantity,
            work_dir=Path(args.work_dir),
            # Gate 1 is deliberately non-destructive. Purchase/resale stays
            # locked until the read-only 20-slot scan passes on live ClientJS.
            probe_only=True,
        )
        workflow = ClearStallWorkflow(request, automation)
        emit(
            "worker_started",
            pid=args.pid,
            profile_id=args.profile_id,
            profile_name=args.profile_name,
            workflow=WORKFLOW_NAME,
            friend_ordinal=args.friend_ordinal,
            resale_storage_id=args.resale_storage_id,
            quantity=args.quantity,
            stall_views=REQUIRED_STALL_VIEWS,
            execution_gate=EXECUTION_GATE,
        )

        emit(
            "progress",
            workflow=WORKFLOW_NAME,
            stage="READ_ONLY_SCAN",
            message="GATE 1: chỉ quét quầy, KHÔNG click mua/bán",
        )
        result = workflow.probe()
        payload = result.to_dict()
        emit(
            "worker_finished",
            workflow=WORKFLOW_NAME,
            **payload,
        )
        return 0

    except AutomationStopped as exc:
        emit(
            "worker_stopped",
            profile_id=args.profile_id,
            workflow=WORKFLOW_NAME,
            reason="user",
            error=str(exc),
        )
        return 0
    except InterruptedError as exc:
        emit(
            "worker_stopped",
            profile_id=args.profile_id,
            workflow=WORKFLOW_NAME,
            reason="user",
            error=str(exc),
        )
        return 0
    except Exception as exc:
        emit(
            "worker_error",
            profile_id=args.profile_id,
            workflow=WORKFLOW_NAME,
            error=repr(exc),
            traceback=traceback.format_exc(),
            diagnostics={
                "source_file": str(Path(__file__).name),
                "function": "main",
            },
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
