from __future__ import annotations

import argparse
import json
from pathlib import Path
import queue
import sys
import threading
import time
import traceback

def emit(event: str, **data) -> None:
    print(json.dumps({"event": event, **data}, ensure_ascii=True), flush=True)


def command_reader(commands: queue.Queue) -> None:
    for line in sys.stdin:
        try:
            commands.put(json.loads(line))
        except json.JSONDecodeError:
            continue


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto-root", required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--profile-name", required=True)
    parser.add_argument("--friend-ordinal", type=int, required=True)
    parser.add_argument("--stall-id", type=int, required=True)
    parser.add_argument("--quantity", type=int, required=True)
    parser.add_argument("--max-pages", type=int, required=True)
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()

    emit(
        "worker_boot",
        pid=args.pid,
        profile_id=args.profile_id,
        profile_name=args.profile_name,
        workflow="clear_stall_python",
        stage="process_started",
    )
    emit(
        "worker_boot",
        pid=args.pid,
        profile_id=args.profile_id,
        workflow="clear_stall_python",
        stage="importing_auto_worker",
    )
    from auto_worker import (
        GuiProxy,
        configure_utf8_stdio,
        install_headless_clientjs_runtime,
    )
    configure_utf8_stdio()

    if not 1 <= args.friend_ordinal <= 500:
        emit("worker_error", error="Bạn bè số phải trong khoảng 1..500")
        return 2
    if not 1 <= args.stall_id <= 4:
        emit("worker_error", error="Quầy phải trong khoảng 1..4")
        return 2
    if not 1 <= args.quantity <= 999:
        emit("worker_error", error="Số lượng mua phải trong khoảng 1..999")
        return 2
    if not 1 <= args.max_pages <= 50:
        emit("worker_error", error="Số trang quét phải trong khoảng 1..50")
        return 2

    workflow_root = Path(__file__).resolve().parents[1] / "workflows"
    sys.path.insert(0, str(workflow_root))
    from clear_stall.adapter import AutoProNavigationAdapter
    from clear_stall.transaction import VisualTransactionExecutor
    from clear_stall.workflow import ClearStallRequest, ClearStallWorkflow

    stop_event = threading.Event()
    commands: queue.Queue = queue.Queue()
    threading.Thread(
        target=command_reader, args=(commands,), daemon=True
    ).start()

    def log(message: str) -> None:
        emit("progress", message=str(message))

    workflow = None
    try:
        emit(
            "worker_boot",
            pid=args.pid,
            profile_id=args.profile_id,
            profile_name=args.profile_name,
            workflow="clear_stall_python",
            stage="loading_auto_pro_runtime",
        )
        automation_module = install_headless_clientjs_runtime(
            Path(args.auto_root).resolve()
        )
        emit(
            "worker_boot",
            pid=args.pid,
            profile_id=args.profile_id,
            workflow="clear_stall_python",
            stage="constructing_controller",
        )
        # Function 136 is used only to construct AUTO PRO's controller and
        # image library. automation.start()/produceItems_* is never called.
        automation = automation_module.FarmAutomation(
            f"PC:{args.pid}",
            136,
            gui_ref=GuiProxy(),
            options={},
            skip_items=[],
        )
        emit(
            "worker_boot",
            pid=args.pid,
            profile_id=args.profile_id,
            workflow="clear_stall_python",
            stage="controller_ready",
        )
        adapter = AutoProNavigationAdapter(
            automation, stop_event=stop_event, logger=log
        )
        executor = VisualTransactionExecutor(
            adapter.controller, stop_event=stop_event, logger=log
        )
        request = ClearStallRequest(
            profile_id=args.profile_id,
            friend_ordinal=args.friend_ordinal,
            stall_id=args.stall_id,
            buy_quantity=args.quantity,
            max_scan_pages=args.max_pages,
            work_dir=Path(args.work_dir),
        )
        workflow = ClearStallWorkflow(
            request, adapter, stop_event=stop_event, logger=log
        )
        emit(
            "worker_started",
            pid=args.pid,
            profile_id=args.profile_id,
            profile_name=args.profile_name,
            workflow="clear_stall_python",
        )

        outcome: dict[str, object] = {"done": False, "error": None}

        def run_workflow() -> None:
            try:
                detected = workflow.discover_source_items()
                pending = workflow.prepare_manifest_items(detected)
                bought = workflow.execute_purchases(pending, executor)
                sold = workflow.execute_resale(executor)
                outcome["bought"] = bought
                outcome["sold"] = sold
            except Exception as exc:
                outcome["error"] = exc
                try:
                    workflow.fail(exc)
                except Exception:
                    pass
            finally:
                outcome["done"] = True

        task = threading.Thread(target=run_workflow, daemon=True)
        task.start()
        command_accept_after = time.monotonic() + 4.0
        while not bool(outcome["done"]):
            try:
                command = commands.get(timeout=0.20)
            except queue.Empty:
                continue
            action = str(command.get("command") or "").lower()
            if action in {"stop", "pause"}:
                if time.monotonic() < command_accept_after:
                    emit(
                        "log",
                        message=(
                            "Đã bỏ qua lệnh Dừng xuất hiện trong 4 giây "
                            "khởi động đầu"
                        ),
                        ignored_command=command,
                    )
                    continue
                stop_event.set()
                emit(
                    "worker_stopping",
                    reason="user",
                    command=command,
                )
        task.join(timeout=3.0)
        error = outcome.get("error")
        if error is not None:
            emit(
                "worker_error",
                error=repr(error),
                traceback="".join(
                    traceback.format_exception(
                        type(error), error, error.__traceback__
                    )
                ),
            )
            return 1
        emit(
            "worker_finished",
            profile_id=args.profile_id,
            workflow="clear_stall_python",
            bought=int(outcome.get("bought") or 0),
            sold=int(outcome.get("sold") or 0),
        )
        return 0
    except Exception as exc:
        if workflow is not None:
            try:
                workflow.fail(exc)
            except Exception:
                pass
        emit(
            "worker_error",
            error=repr(exc),
            traceback=traceback.format_exc(),
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
