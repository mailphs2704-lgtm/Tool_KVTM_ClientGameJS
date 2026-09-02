from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import threading
import time
import traceback
from typing import Callable


PROBE_VERSION = 9
STALL_VIEW_COUNT = 4
TOTAL_STALL_SLOTS = 20


@dataclass(frozen=True)
class ProbeConfig:
    auto_root: Path
    pid: int
    profile_id: str
    profile_name: str
    friend_ordinal: int
    resale_storage_id: int
    buy_quantity: int
    work_dir: Path


EventSink = Callable[[dict], None]


def run_probe(
    config: ProbeConfig,
    *,
    emit_event: EventSink,
    stop_event: threading.Event,
    image_runtime_ready: bool = False,
) -> int:
    """Run the read-only Dọn quầy probe.

    The same function is used by the standalone CLI worker and by Multi DEV's
    resident-runtime thread.  DEV passes ``image_runtime_ready=True`` after it
    has already loaded NumPy/OpenCV/Pillow in the UI process, so the probe never
    spawns a second Python process just to re-import native libraries.
    """

    from kvtm_automation import AutomationContext, KVAutomation
    from kvtm_automation.errors import AutomationStopped

    if not 1 <= int(config.friend_ordinal) <= 7:
        emit_event({"event": "probe_error", "error": "Bạn bè số phải trong khoảng 1..7"})
        return 2
    if not 1 <= int(config.resale_storage_id) <= 5:
        emit_event({"event": "probe_error", "error": "Kho VP bán lại phải trong khoảng 1..5"})
        return 2
    if not 10 <= int(config.buy_quantity) <= 1000 or int(config.buy_quantity) % 10:
        emit_event({
            "event": "probe_error",
            "error": "Số lượng kế hoạch phải là bội số 10 trong khoảng 10..1000",
        })
        return 2

    auto_root = Path(config.auto_root).resolve()
    work_dir = Path(config.work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    report_path = work_dir / "report.json"
    templates_dir = work_dir / "templates"

    report_lock = threading.RLock()
    report: dict[str, object] = {
        "version": PROBE_VERSION,
        "mode": (
            "clean_read_only_inprocess_resident_probe"
            if image_runtime_ready
            else "clean_read_only_direct_dll_probe"
        ),
        "profile_id": config.profile_id,
        "profile_name": config.profile_name,
        "pid": int(config.pid),
        "friend_ordinal": int(config.friend_ordinal),
        "resale_storage_id": int(config.resale_storage_id),
        "requested_quantity": int(config.buy_quantity),
        "image_runtime_ready_before_probe": bool(image_runtime_ready),
        "started_at": time.time(),
        "checkpoints": [],
        "stages": [],
        "views": [],
    }

    def emit(event: str, **data) -> None:
        emit_event({"event": str(event), **data})

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

    def log(message: str) -> None:
        emit("probe_progress", message=str(message))

    def stage(name: str) -> None:
        emit("probe_progress", message=str(name), stage=str(name))

    context = AutomationContext(
        pid=int(config.pid),
        profile_id=str(config.profile_id),
        profile_name=str(config.profile_name),
        auto_root=auto_root,
        work_dir=work_dir,
        stop_event=stop_event,
        logger=log,
        stage_reporter=stage,
    )

    automation = None
    current_view = 1

    def save_frame(path: Path, frame) -> None:
        import cv2

        path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(path), frame):
            raise RuntimeError(f"Không lưu được ảnh probe: {path}")

    def capture(name: str, driver):
        checkpoint(f"{name}-capture-start")
        frame = driver.screenshot(format="opencv")
        height, width = frame.shape[:2]
        if (int(width), int(height)) != (1000, 1000):
            raise RuntimeError(
                f"ClientJS phải là 1000x1000; hiện tại {width}x{height}"
            )
        stages = report["stages"]
        assert isinstance(stages, list)
        path = work_dir / f"stage-{len(stages):02d}-{name}.png"
        save_frame(path, frame)
        entry = {
            "stage": str(name),
            "capture": str(path),
            "frame_size": [int(width), int(height)],
            "at": time.time(),
        }
        with report_lock:
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
        checkpoint(
            "resident-runtime-ready" if image_runtime_ready else "clean-runtime-import-required",
            image_runtime_ready=bool(image_runtime_ready),
        )
        checkpoint(
            "dll-bridge-preflight",
            pipe=rf"\\.\pipe\KVTM-Cocos-{int(config.pid)}",
            dll=str(auto_root / "bin" / "kvtm_bridge.dll"),
            loader=str(auto_root / "bin" / "kvtm_loader.exe"),
        )

        automation = KVAutomation(
            context,
            image_runtime_ready=bool(image_runtime_ready),
        )
        with report_lock:
            report["bridge_mode"] = str(automation.bridge_mode)
            report["bridge_root"] = str(automation.bridge_root)
            report["bridge_info"] = dict(getattr(automation.driver, "info", {}) or {})
            persist()
        checkpoint(
            "dll-bridge-ready",
            mode=str(automation.bridge_mode),
            pipe=str(getattr(automation.driver, "pipe_name", "")),
        )
        capture("dll-engine-ready", automation.driver)
        context.ensure_running()

        checkpoint("waiting-main-screen")
        automation.ensure_main_screen(timeout=90.0)
        capture("main-screen", automation.driver)

        checkpoint("navigating-friend", friend_ordinal=int(config.friend_ordinal))
        automation.navigation.go_to_friend(int(config.friend_ordinal))
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
            save_frame(view_path, frame)
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
            observed_physical = [int(item.physical_slot) for item in observations]
            covered.extend(new_physical)
            occupied.extend(observed_physical)
            view_entry = {
                "view": view,
                "capture": str(view_path),
                "new_local_slots": list(new_local),
                "new_physical_slots": new_physical,
                "occupied_new_physical_slots": observed_physical,
                "observations": [
                    {
                        "physical_slot": int(item.physical_slot),
                        "local_slot": int(item.local_slot),
                        "occupancy_score": round(float(item.occupancy_score), 3),
                    }
                    for item in observations
                ],
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
                    f"đã nhận {len(set(covered))}/{RENDERED_STALL_SLOTS} vị trí render"
                ),
                view=view,
                capture=str(view_path),
            )
            if view < STALL_VIEW_COUNT:
                automation.stall.next_view()

        expected = list(range(1, RENDERED_STALL_SLOTS + 1))
        if covered != expected:
            raise RuntimeError(
                f"Mapping quầy không phủ đúng {RENDERED_STALL_SLOTS} vị trí render: "
                f"{covered}"
            )

        occupied_slots = sorted(set(occupied))
        occupied_total = len(occupied_slots)
        locked_slots = [
            slot for slot in range(1, TOTAL_STALL_SLOTS + 1)
            if slot not in occupied_slots
        ]
        slot_model_valid = (
            occupied_total == EXPECTED_OPEN_OCCUPIED_SLOTS
            and locked_slots == [18, 19, 20]
        )
        with report_lock:
            report["rendered_physical_slots"] = expected
            report["locked_physical_slots"] = locked_slots
            report["slot_model_valid"] = slot_model_valid
            persist()
        if not slot_model_valid:
            raise RuntimeError(
                "Mô hình quầy 17 ô sai: "
                f"occupied={occupied_total}, locked={locked_slots}"
            )

        target_listings = int(config.buy_quantity) // 10
        planned_listings = min(occupied_total, target_listings)
        planned_quantity = planned_listings * 10
        target_reached = planned_listings == target_listings
        with report_lock:
            report["covered_physical_slots"] = covered
            report["occupied_new_physical_slots"] = occupied_slots
            report["occupied_new_total"] = occupied_total
            report["target_listings"] = target_listings
            report["planned_listings"] = planned_listings
            report["planned_quantity"] = planned_quantity
            report["target_reached"] = target_reached
            report["ok"] = True
            report["completed_at"] = time.time()
            report["last_stage"] = "completed"
            persist()
        emit(
            "probe_ok",
            profile_id=str(config.profile_id),
            report=str(report_path),
            occupied_new_total=occupied_total,
            locked_physical_slots=locked_slots,
            slot_model_valid=slot_model_valid,
            requested_quantity=int(config.buy_quantity),
            target_listings=target_listings,
            planned_listings=planned_listings,
            planned_quantity=planned_quantity,
            target_reached=target_reached,
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
        if automation is not None and not stop_event.is_set():
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
        if automation is not None and not stop_event.is_set():
            try:
                automation.stall.rewind_to_first(current_view)
            except Exception:
                pass
            try:
                automation.navigation.return_home(timeout=30.0)
            except Exception:
                pass
