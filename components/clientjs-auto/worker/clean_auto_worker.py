from __future__ import annotations

import argparse
from pathlib import Path
import traceback

from clean_worker_support import (
    StopChannel,
    configure_utf8_stdio,
    emit,
    install_component_path,
)


WORKFLOW_NAME = "auto_multi_dev_clean"


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="KVTM clean AUTO bootstrap worker")
    parser.add_argument("--auto-root", required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--profile-name", required=True)
    parser.add_argument("--profile-file", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

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

    def stage(name: str) -> None:
        emit(
            "progress", workflow=WORKFLOW_NAME,
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
        profile_file=Path(args.profile_file),
    )
    try:
        emit(
            "worker_started", workflow=WORKFLOW_NAME, pid=args.pid,
            profile_id=args.profile_id, profile_name=args.profile_name,
            runtime="clean-python-only", legacy_pyc=False,
        )
        automation = KVAutomation(context)
        result = GameSessionWorkflow(automation).run(timeout=args.timeout)
        emit("worker_finished", workflow=WORKFLOW_NAME, **result.to_dict())
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
