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
        "version": 1,
        "mode": "read_only_live_probe",
        "profile_id": args.profile_id,
        "profile_name": args.profile_name,
        "pid": args.pid,
        "friend_ordinal": args.friend_ordinal,
        "stall_id": args.stall_id,
        "started_at": time.time(),
        "views": [],
    }

    def log(message: str) -> None:
        emit("probe_progress", message=str(message))

    try:
        emit("probe_boot", stage="loading_auto_pro_runtime")
        automation_module = install_headless_clientjs_runtime(
            Path(args.auto_root).resolve()
        )
        emit("probe_boot", stage="constructing_controller")
        automation = automation_module.FarmAutomation(
            f"PC:{args.pid}",
            136,
            gui_ref=GuiProxy(),
            options={},
            skip_items=[],
        )
        adapter = AutoProNavigationAdapter(
            automation,
            stop_event=stop_event,
            logger=log,
        )
        emit("probe_boot", stage="controller_ready")

        adapter.ensure_main_screen()
        adapter.configure_target(args.friend_ordinal, args.stall_id)
        adapter.go_to_friend_home(args.friend_ordinal)
        adapter.open_target_stall(args.stall_id)

        covered_physical_slots: list[int] = []
        occupied_new_physical_slots: list[int] = []
        frame_size = None

        for view in range(1, AUTO_PRO_STALL_VIEW_COUNT + 1):
            if stop_event.is_set():
                raise InterruptedError("Live probe da duoc yeu cau dung")

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
            view_report = {
                "view": view,
                "capture": str(capture_path),
                "new_local_slots": list(new_local),
                "new_physical_slots": new_physical,
                "occupied_visible_slots": occupied_visible,
                "occupied_new_physical_slots": occupied_new,
                "signature": scan.signature,
            }
            report["views"].append(view_report)
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
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
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
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        emit("probe_stopped", report=str(report_path), error=str(exc))
        return 0
    except Exception as exc:
        report["ok"] = False
        report["error"] = repr(exc)
        report["traceback"] = traceback.format_exc()
        report["completed_at"] = time.time()
        try:
            report_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
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
        if adapter is not None:
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
