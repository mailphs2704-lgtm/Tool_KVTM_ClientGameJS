from __future__ import annotations

import argparse
import json
from pathlib import Path
import threading
import time
import traceback

from clean_worker_support import (
    StopChannel,
    configure_utf8_stdio,
    emit,
    install_component_path,
)


PROBE_VERSION = 5
STALL_VIEW_COUNT = 4
TOTAL_STALL_SLOTS = 20


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only clean ClientJS Dọn quầy probe"
    )
    parser.add_argument("--auto-root", required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--profile-name", required=True)
    parser.add_argument("--friend-ordinal", type=int, required=True)
    parser.add_argument("--stall-id", dest="resale_storage_id", type=int, required=True)
    parser.add_argument("--work-dir", required=True)
    return parser


def _save_frame(path: Path, frame) -> None:
    import cv2

    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), frame):
        raise RuntimeError(f"Không lưu được ảnh probe: {path}")


def main() -> int:
    configure_utf8_stdio()
    args = _parser().parse_args()
    if not 1 <= int(args.friend_ordinal) <= 7:
        emit("probe_error", error="Bạn bè số phải trong khoảng 1..7")
        return 2
    if not 1 <= int(args.resale_storage_id) <= 5:
        emit("probe_error", error="Kho VP bán lại phải trong khoảng 1..5")
        return 2

    component_root = install_component_path()
    work_dir = Path(args.work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    report_path = work_dir / "report.json"
    templates_dir = work_dir / "templates"

    report_lock = threading.RLock()
    report: dict[str, object] = {
        "version": PROBE_VERSION,
        "mode": "clean_read_only_live_probe",
        "profile_id": args.profile_id,
        "profile_name": args.profile_name,
        "pid": args.pid,
        "friend_ordinal": args.friend_ordinal,
        "resale_storage_id": args.resale_storage_id,
        "started_at": time.time(),
        "checkpoints": [],
        "stages": [],
        "views": [],
    }

    def persist() -> None:
        with report_lock:
            temporary = report_path.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(report_path)

    def checkpoint(name: str, **details) -> None:
        entry = {"stage": str(name), "at": time.time(), **details}
        with report_lock:
            checkpoints = report["checkpoints"]
            assert isinstance(checkpoints, list)
            checkpoints.append(entry)
            report["last_stage"] = str(name)
            persist()
        emit("probe_boot", stage=str(name), **details)

    channel = StopChannel(
        on_stop=lambda command: _record_stop(report, report_lock, persist, command)
    )
    channel.start()

    def log(message: str) -> None:
        emit("probe_progress", message=str(message))

    def stage(name: str) -> None:
        emit("probe_progress", message=str(name), stage=str(name))

    from kvtm_automation import AutomationContext, KVAutomation
    from kvtm_automation.errors import AutomationStopped
    from kvtm_automation.runtime.driver import ClientJSDriverFactory

    context = AutomationContext(
        pid=args.pid,
        profile_id=args.profile_id,
        profile_name=args.profile_name,
        auto_root=Path(args.auto_root),
        work_dir=work_dir,
        stop_event=channel.event,
        logger=log,
        stage_reporter=stage,
    )

    automation = None
    current_view = 1

    def capture(name: str, driver) -> object:
        checkpoint(f"{name}-capture-start")
        frame = driver.screenshot(format="opencv")
        height, width = frame.shape[:2]
        if (int(width), int(height)) != (1000, 1000):
            raise RuntimeError(
                f"ClientJS phải là 1000x1000; hiện tại {width}x{height}"
            )
        path = work_dir / f"stage-{len(report['stages']):02d}-{name}.png"
        _save_frame(path, frame)
        entry = {
            "stage": str(name),
            "capture": str(path),
            "frame_size": [int(width), int(height)],
            "at": time.time(),
        }
        with report_lock:
            stages = report["stages"]
            assert isinstance(stages, list)
            stages.append(entry)
            report["frame_size"] = [int(width), int(height)]
            report["last_stage"] = str(name)
            persist()
        emit(
            "probe_progress",
            message=f"Đã chụp {name} ({width}x{height})",
            stage=str(name),
            capture=str(path),
        )
        return frame

    try:
        checkpoint("clean-runtime-start")
        factory = ClientJSDriverFactory(component_root, Path(args.auto_root))

        # First capture uses the plain Windows ClientJS bridge. This guarantees
        # diagnostics even if the engine bridge cannot be constructed later.
        checkpoint("raw-window-connecting")
        raw_bundle = factory.raw(args.pid)
        capture("raw-window", raw_bundle.driver)
        context.ensure_running()

        checkpoint("clientjs-engine-connecting")
        automation = KVAutomation(context)
        capture("engine-ready", automation.driver)
        context.ensure_running()

        checkpoint("waiting-main-screen")
        automation.ensure_main_screen(timeout=90.0)
        capture("main-screen", automation.driver)

        checkpoint("navigating-friend", friend_ordinal=args.friend_ordinal)
        automation.navigation.go_to_friend(args.friend_ordinal)
        capture("friend-home", automation.driver)

        checkpoint("opening-friend-stall")
        automation.stall.open_friend_stall()
        capture("stall-open", automation.driver)

        covered: list[int] = []
        occupied: list[int] = []
        for view in range(1, STALL_VIEW_COUNT + 1):
            context.ensure_running()
            current_view = view
            checkpoint(f"scanning-view-{view:02d}")
            frame = automation.vision.frame()
            view_path = work_dir / f"view-{view:02d}.png"
            _save_frame(view_path, frame)
            observations = automation.stall.scan_view(
                view,
                templates_dir,
                frame=frame,
            )
            new_local = automation.stall.new_local_slots(view)
            new_physical = [
                automation.stall.physical_slot(view, slot)
                for slot in new_local
            ]
            observed_physical = [
                int(item.physical_slot) for item in observations
            ]
            covered.extend(new_physical)
            occupied.extend(observed_physical)
            view_entry = {
                "view": view,
                "capture": str(view_path),
                "new_local_slots": list(new_local),
                "new_physical_slots": new_physical,
                "occupied_new_physical_slots": observed_physical,
            }
            with report_lock:
                views = report["views"]
                assert isinstance(views, list)
                views.append(view_entry)
                report["last_stage"] = f"view-{view:02d}"
                persist()
            emit(
                "probe_progress",
                message=(
                    f"Probe view {view}/4 • {len(observations)} ô mới có VP • "
                    f"đã phủ {min(TOTAL_STALL_SLOTS, 8 + (view - 1) * 4)}/20"
                ),
                view=view,
                capture=str(view_path),
            )
            if view < STALL_VIEW_COUNT:
                automation.stall.next_view()

        expected = list(range(1, TOTAL_STALL_SLOTS + 1))
        if covered != expected:
            raise RuntimeError(f"Mapping quầy không phủ đúng 20 ô: {covered}")

        with report_lock:
            report["covered_physical_slots"] = covered
            report["occupied_new_physical_slots"] = sorted(set(occupied))
            report["occupied_new_total"] = len(set(occupied))
            report["ok"] = True
            report["completed_at"] = time.time()
            report["last_stage"] = "completed"
            persist()
        emit(
            "probe_ok",
            profile_id=args.profile_id,
            report=str(report_path),
            occupied_new_total=len(set(occupied)),
            frame_size=[1000, 1000],
        )
        return 0

    except (AutomationStopped, InterruptedError) as exc:
        with report_lock:
            report["ok"] = False
            report["stopped"] = True
            report["error"] = str(exc)
            report["completed_at"] = time.time()
            persist()
        emit("probe_stopped", report=str(report_path), error=str(exc))
        return 0
    except Exception as exc:
        with report_lock:
            report["ok"] = False
            report["error"] = repr(exc)
            report["traceback"] = traceback.format_exc()
            report["completed_at"] = time.time()
            persist()
        if automation is not None and not channel.event.is_set():
            try:
                capture("error-state", automation.driver)
            except Exception:
                pass
        emit(
            "probe_error",
            error=repr(exc),
            traceback=traceback.format_exc(),
            report=str(report_path),
        )
        return 1
    finally:
        if automation is not None and not channel.event.is_set():
            try:
                automation.stall.rewind_to_first(current_view)
            except Exception:
                pass
            try:
                automation.navigation.return_home(timeout=30.0)
            except Exception:
                pass


def _record_stop(
    report: dict[str, object],
    lock: threading.RLock,
    persist,
    command: dict,
) -> None:
    with lock:
        report["stop_requested_at"] = time.time()
        report["stop_requested_stage"] = str(
            report.get("last_stage") or "worker-starting"
        )
        persist()
    emit(
        "probe_stopping",
        reason="user",
        command=command,
        stage=str(report.get("stop_requested_stage") or ""),
    )


if __name__ == "__main__":
    raise SystemExit(main())
