from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import threading
import time
import traceback
from typing import Callable


PROBE_VERSION = 11
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
    purchase_limit: int = 0
    max_stall_passes: int = 10


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
    purchase_limit = int(config.purchase_limit)
    target_listing_count = int(config.buy_quantity) // 10
    if purchase_limit < 0 or purchase_limit > target_listing_count:
        emit_event({
            "event": "probe_error",
            "error": (
                "Giới hạn mua Gate phải trong khoảng 0..target listings; "
                f"limit={purchase_limit} target={target_listing_count}"
            ),
        })
        return 2
    if not 1 <= int(config.max_stall_passes) <= 10:
        emit_event({
            "event": "probe_error",
            "error": "Số lượt tải lại mỗi nhà phải trong khoảng 1..10",
        })
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
        "purchase_limit": int(config.purchase_limit),
        "max_stall_passes": int(config.max_stall_passes),
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
    all_observations = []

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

        initial_friend = 1 if purchase_limit > 1 else int(config.friend_ordinal)
        checkpoint(
            "navigating-friend",
            friend_ordinal=initial_friend,
            configured_friend_count=int(config.friend_ordinal),
        )
        automation.navigation.go_to_friend(initial_friend)
        capture("friend-home", automation.driver)

        checkpoint("opening-friend-stall")
        automation.stall.open_friend_stall()
        capture("stall-open", automation.driver)

        covered: list[int] = []
        occupied: list[int] = []
        purchased_quantity = 0
        purchase_evidence = []
        expected_quantity = purchase_limit * 10
        capacity_model = "DYNAMIC_REMAINING_COUNTER"

        def buy_visible(
            observations,
            friend_index: int,
            stall_pass: int,
        ) -> int:
            """Buy available cells in the current view before any next swipe."""
            nonlocal purchased_quantity
            bought_before = purchased_quantity
            for selected in sorted(
                observations, key=lambda item: int(item.local_slot)
            ):
                if purchased_quantity >= expected_quantity:
                    break
                confirmed = 0

                def on_purchase(_listing_count: int) -> None:
                    nonlocal confirmed
                    confirmed += 10

                bought_listings = automation.buying.buy_from_listing(
                    selected,
                    maximum=1,
                    on_unit=on_purchase,
                    skip_unbuyable=(purchase_limit > 1),
                )
                if bought_listings == 0:
                    continue
                if confirmed != 10:
                    raise RuntimeError(
                        f"GATE sai bộ đếm ô {selected.physical_slot}: "
                        f"expected=10 actual={confirmed}"
                    )
                purchased_quantity += confirmed
                sequence = purchased_quantity // 10
                evidence_path = (
                    work_dir
                    / f"purchase-{sequence:02d}-friend-{friend_index:02d}-"
                    f"pass-{stall_pass:02d}-view-{int(selected.view):02d}-"
                    f"slot-{int(selected.physical_slot):02d}.png"
                )
                save_frame(evidence_path, automation.vision.frame())
                evidence = {
                    "sequence": sequence,
                    "purchased_quantity": purchased_quantity,
                    "remaining_quantity": max(
                        0, expected_quantity - purchased_quantity
                    ),
                    "friend_ordinal": int(friend_index),
                    "stall_pass": int(stall_pass),
                    "physical_slot": int(selected.physical_slot),
                    "view": int(selected.view),
                    "capture_after": str(evidence_path),
                }
                purchase_evidence.append(evidence)
                checkpoint(
                    "gate2-purchase-one-pass"
                    if purchase_limit == 1
                    else f"gate3b-purchase-{sequence:02d}-pass",
                    **evidence,
                )
                emit(
                    "probe_purchase_ok",
                    profile_id=str(config.profile_id),
                    transaction_gate=(
                        "PURCHASE_ONE_LISTING"
                        if purchase_limit == 1
                        else "PURCHASE_TARGET_MULTI_HOUSE"
                    ),
                    **evidence,
                )
            return purchased_quantity - bought_before

        def scan_buy_stall(
            friend_index: int,
            stall_pass: int,
            *,
            primary_report: bool,
        ) -> int:
            """Process one stall strictly as view1 buy, swipe, view2 buy..."""
            nonlocal current_view
            bought_before = purchased_quantity
            current_view = 1
            for view in range(1, STALL_VIEW_COUNT + 1):
                context.ensure_running()
                current_view = view
                checkpoint(
                    f"friend-{friend_index:02d}-pass-{stall_pass:02d}-"
                    f"scan-view-{view:02d}"
                )
                frame = automation.vision.frame()
                if primary_report:
                    view_path = work_dir / f"view-{view:02d}.png"
                    template_root = templates_dir
                else:
                    pass_root = (
                        work_dir
                        / f"friend-{friend_index:02d}"
                        / f"pass-{stall_pass:02d}"
                    )
                    pass_root.mkdir(parents=True, exist_ok=True)
                    view_path = pass_root / f"view-{view:02d}.png"
                    template_root = pass_root / "templates"
                save_frame(view_path, frame)
                observations = automation.stall.scan_view(
                    view,
                    template_root,
                    frame=frame,
                )
                observed_physical = [
                    int(item.physical_slot) for item in observations
                ]
                if primary_report:
                    new_local = automation.stall.new_local_slots(view)
                    new_physical = [
                        automation.stall.physical_slot(view, slot)
                        for slot in new_local
                    ]
                    covered.extend(new_physical)
                    occupied.extend(observed_physical)
                    view_entry = {
                        "view": view,
                        "capture": str(view_path),
                        "new_local_slots": list(new_local),
                        "new_physical_slots": new_physical,
                        "available_new_physical_slots": observed_physical,
                        "observations": [
                            {
                                "physical_slot": int(item.physical_slot),
                                "local_slot": int(item.local_slot),
                                "occupancy_score": round(
                                    float(item.occupancy_score), 3
                                ),
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
                        f"Nhà {friend_index} lượt {stall_pass} • "
                        f"view {view}/4 • {len(observations)} ô có thể mua"
                    ),
                    friend_ordinal=friend_index,
                    stall_pass=stall_pass,
                    view=view,
                    capture=str(view_path),
                )

                # Critical order: buy everything visible in this view first.
                # Only then move the stall by the proven two-swipe step.
                if purchase_limit > 0:
                    buy_visible(observations, friend_index, stall_pass)
                    if purchased_quantity >= expected_quantity:
                        break
                if view < STALL_VIEW_COUNT:
                    automation.stall.next_view()
            return purchased_quantity - bought_before

        if purchase_limit > 0:
            checkpoint(
                "gate2-purchase-one-start"
                if purchase_limit == 1
                else "gate3b-purchase-target-start",
                purchase_limit=purchase_limit,
                target_quantity=expected_quantity,
                friend_count=(1 if purchase_limit == 1 else int(config.friend_ordinal)),
                max_stall_passes=int(config.max_stall_passes),
                order="SCAN_BUY_THEN_SWIPE",
            )

        scan_buy_stall(initial_friend, 1, primary_report=True)

        expected_slots = list(range(1, TOTAL_STALL_SLOTS + 1))
        if purchase_limit == 0 and covered != expected_slots:
            raise RuntimeError(
                f"Mapping mẫu quầy không phủ đủ 4 view: {covered}"
            )

        if purchase_limit > 1 and purchased_quantity < expected_quantity:
            # Stay at the current friend's home while refreshing the same
            # stall. Only return home once when advancing to another friend.
            automation.stall.close_friend_stall()
            current_view = 1
            for friend_index in range(1, int(config.friend_ordinal) + 1):
                if friend_index > 1:
                    automation.navigation.return_home(timeout=30.0)
                    automation.navigation.go_to_friend(friend_index)
                first_pass = 2 if friend_index == 1 else 1
                for stall_pass in range(
                    first_pass, int(config.max_stall_passes) + 1
                ):
                    context.ensure_running()
                    checkpoint(
                        "gate3b-stall-pass-start",
                        friend_ordinal=friend_index,
                        stall_pass=stall_pass,
                        purchased_quantity=purchased_quantity,
                        remaining_quantity=(
                            expected_quantity - purchased_quantity
                        ),
                        navigation=(
                            "REOPEN_CURRENT_STALL"
                            if stall_pass > 1
                            else "ENTER_NEXT_FRIEND_ONCE"
                        ),
                    )
                    automation.stall.open_friend_stall()
                    bought_this_pass = scan_buy_stall(
                        friend_index,
                        stall_pass,
                        primary_report=False,
                    )
                    automation.stall.close_friend_stall()
                    current_view = 1
                    checkpoint(
                        "gate3b-stall-pass-finish",
                        friend_ordinal=friend_index,
                        stall_pass=stall_pass,
                        bought_quantity=bought_this_pass,
                        purchased_quantity=purchased_quantity,
                        remaining_quantity=max(
                            0, expected_quantity - purchased_quantity
                        ),
                    )
                    if purchased_quantity >= expected_quantity:
                        break
                    # Do not abandon this friend after one empty pass. Reload
                    # exactly the configured bounded number of times; a
                    # level-locked or temporarily unavailable view may yield 0.
                if purchased_quantity >= expected_quantity:
                    break

        if purchase_limit > 0 and purchased_quantity != expected_quantity:
            raise RuntimeError(
                "GATE 3B đã duyệt hết giới hạn nhưng chưa đủ target: "
                f"expected={expected_quantity} actual={purchased_quantity} "
                f"remaining={expected_quantity - purchased_quantity}"
            )

        if purchase_limit > 0:
            with report_lock:
                report["purchase_evidence"] = purchase_evidence
                report["purchase_order"] = "SCAN_BUY_THEN_SWIPE"
                report["friend_count_scanned"] = max(
                    (
                        int(item["friend_ordinal"])
                        for item in purchase_evidence
                    ),
                    default=0,
                )
                persist()

        occupied_slots = sorted(set(occupied))
        occupied_total = len(occupied_slots)


        target_listings = int(config.buy_quantity) // 10
        planned_listings = min(occupied_total, target_listings)
        planned_quantity = planned_listings * 10
        target_reached = planned_listings == target_listings
        with report_lock:
            report["covered_physical_slots"] = covered
            report["occupied_new_physical_slots"] = occupied_slots
            report["occupied_new_total"] = occupied_total
            report["capacity_model"] = capacity_model
            report["sample_hits_not_unique_inventory"] = occupied_total
            report["target_listings"] = target_listings
            report["planned_listings"] = planned_listings
            report["planned_quantity"] = planned_quantity
            report["target_reached"] = target_reached
            report["purchased_quantity"] = purchased_quantity
            report["transaction_gate"] = (
                "READ_ONLY_SCAN"
                if purchase_limit == 0
                else (
                    "PURCHASE_ONE_LISTING"
                    if purchase_limit == 1
                    else "PURCHASE_TARGET_MULTI_HOUSE"
                )
            )
            report["ok"] = True
            report["completed_at"] = time.time()
            report["last_stage"] = "completed"
            persist()
        emit(
            "probe_ok",
            profile_id=str(config.profile_id),
            report=str(report_path),
            occupied_new_total=occupied_total,
            capacity_model=capacity_model,
            sample_hits_not_unique_inventory=occupied_total,
            requested_quantity=int(config.buy_quantity),
            target_listings=target_listings,
            planned_listings=planned_listings,
            planned_quantity=planned_quantity,
            target_reached=target_reached,
            purchased_quantity=purchased_quantity,
            transaction_gate=(
                "READ_ONLY_SCAN"
                if purchase_limit == 0
                else (
                    "PURCHASE_ONE_LISTING"
                    if purchase_limit == 1
                    else "PURCHASE_TARGET_MULTI_HOUSE"
                )
            ),
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
