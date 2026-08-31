from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import threading
import time
import traceback


def emit(event: str, **data) -> None:
    print(json.dumps({"event": event, **data}, ensure_ascii=True), flush=True)


def command_reader(stop_event: threading.Event) -> None:
    for line in sys.stdin:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        action = str(payload.get("command") or "").strip().lower()
        if action in {"stop", "pause"}:
            stop_event.set()
            emit("probe_stopping", reason="user")
            return


def save_frame(path: Path, frame) -> None:
    import cv2

    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), frame):
        raise RuntimeError(f"Khong luu duoc anh probe: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto-root", required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--profile-name", required=True)
    parser.add_argument("--friend-ordinal", type=int, required=True)
    parser.add_argument("--stall-id", type=int, required=True)
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()

    if not 1 <= args.friend_ordinal <= 500:
        emit("probe_error", error="Ban be so phai trong khoang 1..500")
        return 2
    if not 1 <= args.stall_id <= 4:
        emit("probe_error", error="Quay phai trong khoang 1..4")
        return 2

    emit(
        "probe_boot",
        pid=args.pid,
        profile_id=args.profile_id,
        profile_name=args.profile_name,
        stage="importing_runtime",
    )

    from auto_worker import (
        GuiProxy,
        configure_utf8_stdio,
        install_headless_clientjs_runtime,
    )

    configure_utf8_stdio()
    workflow_root = Path(__file__).resolve().parents[1] / "workflows"
    sys.path.insert(0, str(workflow_root))

    from clear_stall.adapter import AutoProNavigationAdapter
    from clear_stall.detector import (
        AUTO_PRO_STALL_VIEW_COUNT,
        StallScanner,
        TOTAL_STALL_SLOTS,
        new_local_slots_for_view,
        physical_slot_index,
    )

    stop_event = threading.Event()
    threading.Thread(
        target=command_reader,
        args=(stop_event,),
        daemon=True,
    ).start()

    work_dir = Path(args.work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    report_path = work_dir / "report.json"
    scanner = StallScanner(work_dir / "templates")
    adapter = None
    forward_swipes = 0
    report: dict[str, object] = {
        "version": 3,
        "mode": "read_only_live_probe",
        "profile_id": args.profile_id,
        "profile_name": args.profile_name,
        "pid": args.pid,
        "friend_ordinal": args.friend_ordinal,
        "stall_id": args.stall_id,
        "started_at": time.time(),
        "checkpoints": [],
        "stages": [],
        "views": [],
    }

    def persist_report() -> None:
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def checkpoint(stage: str, **details) -> None:
        entry = {"stage": str(stage), "at": time.time(), **details}
        report["checkpoints"].append(entry)
        report["last_stage"] = str(stage)
        persist_report()
        emit("probe_boot", stage=str(stage), **details)

    def log(message: str) -> None:
        emit("probe_progress", message=str(message))

    def capture_driver(stage: str, driver):
        checkpoint(f"{stage}-capture-start")
        frame = driver.screenshot(format="opencv")
        height, width = frame.shape[:2]
        capture_path = work_dir / f"stage-{len(report['stages']):02d}-{stage}.png"
        save_frame(capture_path, frame)
        entry = {
            "stage": stage,
            "capture": str(capture_path),
            "frame_size": [int(width), int(height)],
            "at": time.time(),
        }
        report["stages"].append(entry)
        report["last_stage"] = stage
        persist_report()
        emit(
            "probe_progress",
            message=f"Da chup trang thai: {stage} ({width}x{height})",
            stage=stage,
            capture=str(capture_path),
        )
        return frame

    def capture_stage(stage: str):
        if adapter is None:
            return None
        return capture_driver(stage, adapter.driver)

    try:
        # Persist every blocking boundary before entering it. This makes a
        # stopped probe diagnostically useful even when no AUTO PRO object was
        # fully constructed yet.
        checkpoint("loading-auto-pro-runtime")
        automation_module = install_headless_clientjs_runtime(
            Path(args.auto_root).resolve()
        )
        checkpoint("auto-pro-runtime-loaded")

        # Always capture the real GameClientJS window before engine injection.
        # This is deliberately independent from ADBController/ImageProcessor.
        checkpoint("raw-window-driver-constructing")
        from pc_driver import PCDriver
        raw_driver = PCDriver(args.pid, reference_size=(1000, 1000))
        checkpoint("raw-window-driver-ready")
        capture_driver("raw-window", raw_driver)

        # Build the Cocos EngineDriver exactly once. ADBController normally
        # reaches it through uiautomator2.connect("PC:<pid>"). Reusing this
        # preconnected instance prevents duplicate profile lookup / bridge
        # injection during FarmAutomation construction.
        checkpoint("engine-driver-constructing")
        from engine_driver import EngineDriver
        engine_driver = EngineDriver(args.pid, reference_size=(1000, 1000))
        checkpoint("engine-driver-ready")
        capture_driver("engine-driver", engine_driver)

        import uiautomator2 as u2
        previous_connect = u2.connect
        wanted_device = f"PC:{args.pid}"

        def reuse_connect(device_id=None, *connect_args, **connect_kwargs):
            if str(device_id or "") == wanted_device:
                return engine_driver
            return previous_connect(device_id, *connect_args, **connect_kwargs)

        u2.connect = reuse_connect
        checkpoint("preconnected-driver-bound")

        checkpoint("farm-automation-constructing")
        automation = automation_module.FarmAutomation(
            wanted_device,
            136,
            gui_ref=GuiProxy(),
            options={},
            skip_items=[],
        )
        checkpoint("farm-automation-constructed")
        adapter = AutoProNavigationAdapter(
            automation,
            stop_event=stop_event,
            logger=log,
        )
        checkpoint("controller-ready")
        capture_stage("controller-ready")

        checkpoint("starting-autopro-popup-guard")
        adapter.start_auto_pro_popup_guard()

        checkpoint("waiting-main-screen")
        adapter.ensure_main_screen(timeout=45.0)
        capture_stage("main-screen")

        adapter.configure_target(args.friend_ordinal, args.stall_id)
        checkpoint("navigating-friend")
        adapter.go_to_friend_home(args.friend_ordinal, verify=False)
        capture_stage("friend-home")

        checkpoint("opening-friend-stall")
        adapter.open_target_stall(args.stall_id, verify=False)
        capture_stage("stall-open")

        covered_physical_slots: list[int] = []
        occupied_new_physical_slots: list[int] = []
        frame_size = None

        for view in range(1, AUTO_PRO_STALL_VIEW_COUNT + 1):
            if stop_event.is_set():
                raise InterruptedError("Live probe da duoc yeu cau dung")

            checkpoint(f"scanning-view-{view:02d}")
            frame = adapter.screenshot()
            height, width = frame.shape[:2]
            capture_path = work_dir / f"view-{view:02d}.png"
            save_frame(capture_path, frame)

            if frame_size is None:
                frame_size = [int(width), int(height)]
                report["frame_size"] = frame_size
            elif frame_size != [int(width), int(height)]:
                raise RuntimeError(
                    f"Kich thuoc screenshot thay doi trong probe: "
                    f"{frame_size[0]}x{frame_size[1]} -> {width}x{height}"
                )

            if (width, height) != (1000, 1000):
                raise RuntimeError(
                    f"ClientJS phai dung 1000x1000 cho toa do Auto Pro; "
                    f"hien tai {width}x{height}"
                )

            scan = scanner.scan_page(frame, view)
            new_local = tuple(new_local_slots_for_view(view))
            new_local_set = set(new_local)
            new_physical = [
                physical_slot_index(view, local_slot)
                for local_slot in new_local
            ]
            occupied_visible = [int(slot.slot) for slot in scan.slots]
            occupied_new = [
                int(slot.physical_slot)
                for slot in scan.slots
                if slot.slot in new_local_set
            ]

            covered_physical_slots.extend(new_physical)
            occupied_new_physical_slots.extend(occupied_new)
            report["views"].append(
                {
                    "view": view,
                    "capture": str(capture_path),
                    "new_local_slots": list(new_local),
                    "new_physical_slots": new_physical,
                    "occupied_visible_slots": occupied_visible,
                    "occupied_new_physical_slots": occupied_new,
                    "signature": scan.signature,
                }
            )
            report["last_stage"] = f"view-{view:02d}"
            persist_report()
            emit(
                "probe_progress",
                message=(
                    f"Probe view {view}/{AUTO_PRO_STALL_VIEW_COUNT}: "
                    f"{len(occupied_new)} VP moi; "
                    f"da phu {min(TOTAL_STALL_SLOTS, 8 + (view - 1) * 4)}/20 o"
                ),
                view=view,
                occupied_new=len(occupied_new),
                capture=str(capture_path),
            )

            if view < AUTO_PRO_STALL_VIEW_COUNT:
                adapter.swipe_next_stall_page()
                forward_swipes += 1

        expected_slots = list(range(1, TOTAL_STALL_SLOTS + 1))
        if covered_physical_slots != expected_slots:
            raise RuntimeError(
                f"Probe khong phu dung 20 o vat ly: {covered_physical_slots}"
            )

        report["covered_physical_slots"] = covered_physical_slots
        report["occupied_new_physical_slots"] = sorted(
            set(occupied_new_physical_slots)
        )
        report["occupied_new_total"] = len(
            set(occupied_new_physical_slots)
        )
        report["completed_at"] = time.time()
        report["ok"] = True
        report["last_stage"] = "completed"
        persist_report()
        emit(
            "probe_ok",
            profile_id=args.profile_id,
            report=str(report_path),
            occupied_new_total=int(report["occupied_new_total"]),
            frame_size=report.get("frame_size"),
        )
        return 0
    except InterruptedError as exc:
        report["ok"] = False
        report["stopped"] = True
        report["error"] = str(exc)
        report["completed_at"] = time.time()
        persist_report()
        emit("probe_stopped", report=str(report_path), error=str(exc))
        return 0
    except Exception as exc:
        report["ok"] = False
        report["error"] = repr(exc)
        report["traceback"] = traceback.format_exc()
        report["completed_at"] = time.time()
        try:
            if adapter is not None and not stop_event.is_set():
                capture_stage("error-state")
        except Exception:
            pass
        persist_report()
        emit(
            "probe_error",
            error=repr(exc),
            traceback=traceback.format_exc(),
            report=str(report_path),
        )
        return 1
    finally:
        if adapter is not None and not stop_event.is_set():
            while forward_swipes > 0:
                try:
                    adapter.swipe_previous_stall_page()
                    forward_swipes -= 1
                except Exception:
                    break
            try:
                adapter.return_to_clone_home()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
