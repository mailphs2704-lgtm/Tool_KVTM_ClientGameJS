from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import threading
import time
import traceback
from typing import Callable


PROBE_VERSION = 15
STALL_VIEW_COUNT = 4
TOTAL_STALL_SLOTS = 20
ALLOWED_ITEM_TEMPLATES = {
    "nuoc_hoa_hong": "Nước hoa hồng",
    "tinh_dau_hh": "Tinh dầu hoa hồng",
    "vai_vang": "Vải vàng",
    "tao_say": "Táo sấy",
    "tra_da": "Trà đá",
}
DEFAULT_ALLOWED_ITEM_IDS = tuple(ALLOWED_ITEM_TEMPLATES)


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
    resale_batch_limit: int = 0
    allowed_item_ids: tuple[str, ...] = DEFAULT_ALLOWED_ITEM_IDS


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
    from kvtm_automation.errors import (
        AutomationStopped,
        InventoryFull,
        NoEmptyStallSlot,
    )
    from kvtm_automation.models import VisualFingerprint

    if not 1 <= int(config.friend_ordinal) <= 7:
        emit_event({"event": "probe_error", "error": "Bạn bè số phải trong khoảng 1..7"})
        return 2
    if not 1 <= int(config.resale_storage_id) <= 5:
        emit_event({"event": "probe_error", "error": "Kho VP bán lại phải trong khoảng 1..5"})
        return 2
    allowed_item_ids = tuple(dict.fromkeys(
        str(item).strip() for item in config.allowed_item_ids if str(item).strip()
    ))
    unknown_items = sorted(set(allowed_item_ids) - set(ALLOWED_ITEM_TEMPLATES))
    if not allowed_item_ids or unknown_items:
        emit_event({
            "event": "probe_error",
            "error": (
                "Danh sách VP Dọn quầy không hợp lệ"
                + (f": {unknown_items}" if unknown_items else ": chưa chọn VP")
            ),
        })
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
    resale_batch_limit = int(config.resale_batch_limit)
    if not 0 <= resale_batch_limit <= purchase_limit:
        emit_event({
            "event": "probe_error",
            "error": (
                "Giới hạn treo lại phải trong khoảng 0..số ô mua; "
                f"resale={resale_batch_limit} purchase={purchase_limit}"
            ),
        })
        return 2
    if resale_batch_limit and purchase_limit <= 1:
        emit_event({
            "event": "probe_error",
            "error": "Gate treo lại yêu cầu chạy mua target trước",
        })
        return 2
    if resale_batch_limit > 20:
        emit_event({
            "event": "probe_error",
            "error": "Một vòng chỉ được treo tối đa 20 ô quầy x10",
        })
        return 2

    transaction_gate = (
        "READ_ONLY_SCAN"
        if purchase_limit == 0
        else (
            "PURCHASE_ONE_LISTING"
            if purchase_limit == 1
            else (
                "COLLECT_GOLD_RESELL_TARGET_EXACT"
                if resale_batch_limit > 1
                else (
                    "COLLECT_GOLD_RESELL_ONE_EXACT"
                    if resale_batch_limit == 1
                    else "PURCHASE_TARGET_MULTI_HOUSE"
                )
            )
        )
    )
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
        "resale_batch_limit": int(config.resale_batch_limit),
        "allowed_item_ids": list(allowed_item_ids),
        "allowed_item_names": [ALLOWED_ITEM_TEMPLATES[item] for item in allowed_item_ids],
        "reload_policy": "UNTIL_TARGET_OR_STOP",
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
        purchased_fingerprints = []
        pending_resale_fingerprints = []
        if resale_batch_limit > 0:
            if len(purchased_fingerprints) < resale_batch_limit:
                raise RuntimeError(
                    "Không đủ fingerprint từ các giao dịch mua đã xác minh"
                )
            checkpoint(
                "gate5-final-inventory-flush",
                pending_batches=len(pending_resale_fingerprints),
                purchased_quantity=purchased_quantity,
                sold_quantity=sold_quantity,
            )
            if pending_resale_fingerprints:
                flush_pending_inventory(
                    current_friend,
                    reason="TARGET_REACHED_FINAL_RESALE",
                    return_to_friend=False,
                )
            if sold_quantity != resale_batch_limit * 10:
                raise RuntimeError(
                    "Kế toán treo lại không khớp số lô x10 đã yêu cầu"
                )

        occupied_slots = sorted(set(occupied))
        occupied_total = len(occupied_slots)

        target_listings = int(config.buy_quantity) // 10
        planned_listings = min(occupied_total, target_listings)
        planned_quantity = planned_listings * 10
        target_reached = (
            purchased_quantity == target_listings * 10
            if purchase_limit > 0
            else planned_listings == target_listings
        )
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
            report["sold_quantity"] = sold_quantity
            report["collected_gold_slots"] = collected_gold_slots
            report["transaction_gate"] = transaction_gate
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
            sold_quantity=sold_quantity,
            collected_gold_slots=collected_gold_slots,
            transaction_gate=transaction_gate,
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
