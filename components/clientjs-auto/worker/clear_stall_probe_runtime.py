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
    from kvtm_automation.errors import AutomationStopped, InventoryFull, NoEmptyStallSlot
    from kvtm_automation.models import VisualFingerprint
    from kvtm_automation.workflows.clear_stall.designer_policy import (
        config_path as designer_config_path,
        load_runtime_policy,
    )

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
        designer_policy = load_runtime_policy(designer_config_path())
        automation.stall.apply_runtime_policy(designer_policy)
        checkpoint(
            "clear-stall-designer-policy-applied",
            **{
                key: getattr(designer_policy, key)
                for key in designer_policy.__dataclass_fields__
            },
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
        current_friend = initial_friend
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
        sold_quantity = 0
        collected_gold_slots = 0
        resale_evidence: list[dict[str, object]] = []
        expected_quantity = purchase_limit * 10

        class RestartFriendScanAfterInventoryFlush(Exception):
            pass
        capacity_model = "DYNAMIC_REMAINING_COUNTER"

        def buy_visible(
            eligible_observations,
            friend_index: int,
            stall_pass: int,
        ) -> int:
            """Buy available cells in the current view before any next swipe."""
            nonlocal purchased_quantity
            bought_before = purchased_quantity
            for selected, selected_item_id in sorted(
                eligible_observations, key=lambda item: int(item[0].local_slot)
            ):
                if purchased_quantity >= expected_quantity:
                    break
                confirmed = 0

                def on_purchase(_listing_count: int) -> None:
                    nonlocal confirmed
                    confirmed += 10

                try:
                    bought_listings = automation.buying.buy_from_listing(
                        selected, maximum=1, on_unit=on_purchase,
                        skip_unbuyable=(purchase_limit > 1),
                    )
                except InventoryFull:
                    if resale_batch_limit <= 0:
                        raise
                    checkpoint(
                        "gate5-inventory-full",
                        friend_ordinal=friend_index,
                        purchased_quantity=purchased_quantity,
                        pending_resale_batches=len(pending_resale_fingerprints),
                    )
                    flush_pending_inventory(
                        friend_index, reason="INVENTORY_FULL_DURING_PURCHASE",
                        return_to_friend=True,
                    )
                    raise RestartFriendScanAfterInventoryFlush
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
                    "item_id": selected_item_id,
                    "item_name": ALLOWED_ITEM_TEMPLATES[selected_item_id],
                    "capture_after": str(evidence_path),
                }
                purchase_evidence.append(evidence)
                # Freeze the exact icon that produced this verified purchase.
                # Scan templates may be overwritten by overlapping later views.
                icon_source = Path(selected.fingerprint.template_file)
                icon_target = (
                    work_dir / "purchased-icons" / f"purchase-{sequence:02d}.png"
                )
                icon_target.parent.mkdir(parents=True, exist_ok=True)
                import cv2

                listing_icon = cv2.imread(str(icon_source), cv2.IMREAD_COLOR)
                if listing_icon is None or listing_icon.size == 0:
                    raise RuntimeError(
                        "Không đọc được icon VP ngay sau giao dịch đã xác minh"
                    )
                icon_height, icon_width = listing_icon.shape[:2]
                # A friend-stall tile contains the pedestal and quantity label
                # (x10), while inventory shows another background/quantity.
                # Preserve only the upper-left item core so identity survives
                # that UI-context change.
                core = listing_icon[
                    2 : max(10, int(round(icon_height * 0.60))),
                    2 : max(10, int(round(icon_width * 0.73))),
                ].copy()
                if core.size == 0 or not cv2.imwrite(str(icon_target), core):
                    raise RuntimeError("Không lưu được lõi icon VP đã mua")
                frozen_fingerprint = VisualFingerprint.from_image(
                    core,
                    template_file=str(icon_target),
                )
                purchased_fingerprints.append(frozen_fingerprint)
                pending_resale_fingerprints.append(frozen_fingerprint)
                evidence["source_listing_sha256"] = selected.fingerprint.sha256
                evidence["fingerprint_sha256"] = frozen_fingerprint.sha256
                evidence["fingerprint_group"] = frozen_fingerprint.group_key
                evidence["fingerprint_normalization"] = "ITEM_CORE_NO_PRICE_OR_PEDESTAL"
                evidence["frozen_template"] = str(icon_target)
                checkpoint(
                    "gate2-purchase-one-pass"
                    if purchase_limit == 1
                    else f"gate3b-purchase-{sequence:02d}-pass",
                    **evidence,
                )
                emit(
                    "probe_purchase_ok",
                    profile_id=str(config.profile_id),
                    transaction_gate=transaction_gate,
                    **evidence,
                )
            return purchased_quantity - bought_before

        def flush_pending_inventory(friend_index: int, *, reason: str, return_to_friend: bool) -> None:
            """Free clone inventory by reselling only verified purchases."""
            nonlocal sold_quantity, collected_gold_slots, current_view
            if not pending_resale_fingerprints:
                raise InventoryFull(
                    "Kho clone đầy nhưng chưa có VP đã mua trong lượt để treo"
                )
            try:
                automation.stall.close_friend_stall()
            except Exception:
                pass
            checkpoint(
                "gate5-inventory-flush-start", reason=reason,
                friend_ordinal=friend_index,
                pending_batches=len(pending_resale_fingerprints),
            )
            automation.navigation.return_home(timeout=30.0)
            automation.stall.open_own_stall()
            sale_view = 1
            current_view = 1
            collected_gold_slots += automation.stall.collect_own_stall_gold(maximum=designer_policy.collect_gold_maximum)
            while pending_resale_fingerprints:
                context.ensure_running()
                try:
                    selected_resale = automation.selling.sell_one_of_exact_purchases(
                        pending_resale_fingerprints,
                        storage_id=int(config.resale_storage_id),
                    )
                except NoEmptyStallSlot:
                    if sale_view >= STALL_VIEW_COUNT:
                        raise RuntimeError("Đã kéo đến cuối quầy nhà nhưng không còn ô trống")
                    checkpoint(
                        "gate5-inventory-flush-next-view",
                        next_view=sale_view + 1, swipe_pulses=2,
                        order="TWO_SWIPES_THEN_SCAN_COLLECT_RESELL",
                    )
                    automation.stall.next_view()
                    sale_view += 1
                    current_view = sale_view
                    collected_gold_slots += automation.stall.collect_own_stall_gold(maximum=designer_policy.collect_gold_maximum)
                    continue
                index = next((
                    i for i, item in enumerate(pending_resale_fingerprints)
                    if item.sha256 == selected_resale.sha256
                ), None)
                if index is None:
                    raise RuntimeError("Không tiêu thụ được fingerprint sau khi treo")
                pending_resale_fingerprints.pop(index)
                sold_quantity += 10
                batch_index = sold_quantity // 10
                capture_path = work_dir / f"gate5-resale-{batch_index:02d}-pass.png"
                save_frame(capture_path, automation.vision.frame())
                evidence = {
                    "batch_index": batch_index, "quantity": 10,
                    "sold_quantity": sold_quantity,
                    "fingerprint_sha256": selected_resale.sha256,
                    "fingerprint_group": selected_resale.group_key,
                    "source": "VERIFIED_PURCHASE_THIS_RUN",
                    "price_changed": False, "reason": reason,
                    "capture_after": str(capture_path),
                }
                resale_evidence.append(evidence)
                checkpoint(f"gate5-resell-{batch_index:02d}-pass", **evidence)
                emit("probe_resale_ok", profile_id=str(config.profile_id),
                     transaction_gate=transaction_gate, **evidence)
                with report_lock:
                    report["resale_evidence"] = list(resale_evidence)
                    report["sold_quantity"] = sold_quantity
                    persist()
            checkpoint(
                "gate5-inventory-flush-finish", reason=reason,
                purchased_quantity=purchased_quantity, sold_quantity=sold_quantity,
                remaining_quantity=max(0, expected_quantity - purchased_quantity),
            )
            if return_to_friend and purchased_quantity < expected_quantity:
                automation.navigation.go_to_friend(friend_index)
                current_view = 1

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
                eligible_observations = []
                item_matches = {}
                for observation in observations:
                    cx, cy = observation.center
                    zone = (cx - 50, cy - 58, 100, 108)
                    matched_item_id = None
                    for item_id in allowed_item_ids:
                        if automation.vision.find(
                            item_id,
                            threshold=designer_policy.recognition_threshold,
                            zone=zone,
                            scales=(0.90, 1.0, 1.10),
                            frame=frame,
                        ) is not None:
                            matched_item_id = item_id
                            break
                    if matched_item_id is not None:
                        eligible_observations.append(
                            (observation, matched_item_id)
                        )
                        item_matches[int(observation.physical_slot)] = matched_item_id

                # ClientJS item sprites keep animating for a short time after
                # the two-swipe step. Retry only still-unmatched occupied cells
                # on two fresh frames before declaring the view ineligible.
                for recognition_retry in range(1, designer_policy.recognition_retries + 1):
                    unmatched = [
                        observation for observation in observations
                        if int(observation.physical_slot) not in item_matches
                    ]
                    if not unmatched:
                        break
                    context.ensure_running()
                    time.sleep(designer_policy.recognition_retry_wait)
                    retry_frame = automation.vision.frame()
                    newly_matched = 0
                    for observation in unmatched:
                        cx, cy = observation.center
                        zone = (cx - 50, cy - 58, 100, 108)
                        for item_id in allowed_item_ids:
                            if automation.vision.find(
                                item_id,
                                threshold=designer_policy.recognition_threshold,
                                zone=zone,
                                scales=(0.85, 0.90, 1.0, 1.10, 1.15),
                                frame=retry_frame,
                            ) is not None:
                                eligible_observations.append(
                                    (observation, item_id)
                                )
                                item_matches[int(observation.physical_slot)] = item_id
                                newly_matched += 1
                                break
                    checkpoint(
                        "stall-view-recognition-retry",
                        friend_ordinal=friend_index,
                        stall_pass=stall_pass,
                        view=view,
                        retry=recognition_retry,
                        newly_matched=newly_matched,
                        still_unmatched=len(unmatched) - newly_matched,
                    )
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
                                "allowed_item_id": item_matches.get(
                                    int(item.physical_slot)
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
                        f"view {view}/4 • {len(eligible_observations)}/"
                        f"{len(observations)} ô đúng danh sách VP"
                    ),
                    friend_ordinal=friend_index,
                    stall_pass=stall_pass,
                    view=view,
                    capture=str(view_path),
                )

                # Critical order: buy everything visible in this view first.
                # Then move exactly one swipe and immediately scan again.
                if purchase_limit > 0:
                    buy_visible(eligible_observations, friend_index, stall_pass)
                    if purchased_quantity >= expected_quantity:
                        break
                if view < STALL_VIEW_COUNT:
                    checkpoint(
                        "stall-step-start",
                        friend_ordinal=friend_index,
                        stall_pass=stall_pass,
                        from_view=view,
                        to_view=view + 1,
                        swipe_pulses=2,
                    )
                    automation.stall.next_view()
                    transition_path = (
                        work_dir / f"friend-{friend_index:02d}-pass-"
                        f"{stall_pass:02d}-after-step-{view:02d}.png"
                    )
                    save_frame(transition_path, automation.vision.frame())
                    checkpoint(
                        "stall-step-finished-scan-required",
                        friend_ordinal=friend_index,
                        stall_pass=stall_pass,
                        next_view=view + 1,
                        swipe_pulses=2,
                        capture=str(transition_path),
                    )
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

        while True:
            try:
                scan_buy_stall(initial_friend, 1, primary_report=True)
                break
            except RestartFriendScanAfterInventoryFlush:
                automation.stall.open_friend_stall()
                checkpoint(
                    "gate5-resume-purchase-after-inventory-flush",
                    friend_ordinal=initial_friend,
                    remaining_quantity=expected_quantity - purchased_quantity,
                )

        expected_slots = list(range(1, TOTAL_STALL_SLOTS + 1))
        if purchase_limit == 0 and covered != expected_slots:
            raise RuntimeError(
                f"Mapping mẫu quầy không phủ đủ 4 view: {covered}"
            )

        if purchase_limit > 1 and purchased_quantity < expected_quantity:
            # Keep cycling the configured houses until the verified x10 target
            # is reached or the user presses Stop. max_stall_passes limits one
            # visit, not the total lifetime of the job.
            automation.stall.close_friend_stall()
            current_view = 1
            current_friend = 1
            reload_round = 0
            while purchased_quantity < expected_quantity:
                context.ensure_running()
                reload_round += 1
                round_before = purchased_quantity
                checkpoint(
                    "gate3b-reload-round-start",
                    reload_round=reload_round,
                    purchased_quantity=purchased_quantity,
                    remaining_quantity=expected_quantity - purchased_quantity,
                    policy="UNTIL_TARGET_OR_STOP",
                )
                for friend_index in range(1, int(config.friend_ordinal) + 1):
                    context.ensure_running()
                    if current_friend != friend_index:
                        automation.navigation.return_home(timeout=30.0)
                        automation.navigation.go_to_friend(friend_index)
                        current_friend = friend_index
                    for local_pass in range(1, int(config.max_stall_passes) + 1):
                        context.ensure_running()
                        visit_pass = (
                            reload_round * int(config.max_stall_passes)
                            + local_pass
                        )
                        checkpoint(
                            "gate3b-stall-pass-start",
                            reload_round=reload_round,
                            friend_ordinal=friend_index,
                            stall_pass=visit_pass,
                            purchased_quantity=purchased_quantity,
                            remaining_quantity=expected_quantity - purchased_quantity,
                            navigation="REOPEN_CURRENT_STALL",
                        )
                        automation.stall.open_friend_stall()
                        while True:
                            try:
                                bought_this_pass = scan_buy_stall(
                                    friend_index, visit_pass, primary_report=False,
                                )
                                break
                            except RestartFriendScanAfterInventoryFlush:
                                automation.stall.open_friend_stall()
                                checkpoint(
                                    "gate5-resume-purchase-after-inventory-flush",
                                    friend_ordinal=friend_index,
                                    remaining_quantity=expected_quantity - purchased_quantity,
                                )
                        automation.stall.close_friend_stall()
                        current_view = 1
                        checkpoint(
                            "gate3b-stall-pass-finish",
                            reload_round=reload_round,
                            friend_ordinal=friend_index,
                            stall_pass=visit_pass,
                            bought_quantity=bought_this_pass,
                            purchased_quantity=purchased_quantity,
                            remaining_quantity=max(
                                0, expected_quantity - purchased_quantity
                            ),
                        )
                        if purchased_quantity >= expected_quantity:
                            break
                    if purchased_quantity >= expected_quantity:
                        break
                if purchased_quantity == round_before:
                    checkpoint(
                        "gate3b-waiting-for-stock",
                        reload_round=reload_round,
                        purchased_quantity=purchased_quantity,
                        remaining_quantity=expected_quantity - purchased_quantity,
                        wait_seconds=5.0,
                    )
                    for _ in range(50):
                        context.ensure_running()
                        time.sleep(0.10)

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

        if resale_batch_limit > 0:
            if len(purchased_fingerprints) < resale_batch_limit:
                raise RuntimeError("Không đủ fingerprint từ giao dịch mua đã xác minh")
            if pending_resale_fingerprints:
                flush_pending_inventory(
                    current_friend, reason="TARGET_REACHED_FINAL_RESALE",
                    return_to_friend=False,
                )
            if sold_quantity != resale_batch_limit * 10:
                raise RuntimeError("Kế toán treo lại không khớp số lô x10 đã yêu cầu")

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
